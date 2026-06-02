#!/usr/bin/env python3
"""Unified live SolidWorks validation gate.

This is an explicit opt-in gate for local machines that have SolidWorks + pywin32.
Downstream checks import pythoncom/win32com.client; keep those names in this header so swctl selects a pywin32-capable Python before launching the gate.
It runs the focused capability suite and the native bullhead shaper fixture in one
serialized process, then validates the emitted JSON reports instead of trusting
only process exit codes.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class LiveCheck:
    name: str
    command: tuple[str, ...]
    report_json: str
    purpose: str


@dataclass(frozen=True)
class GateContract:
    name: str
    checks: tuple[LiveCheck, ...]
    output_json: str
    notes: tuple[str, ...]


@dataclass(frozen=True)
class ReportExpectation:
    name: str
    path: Path
    required_truthy_paths: tuple[str, ...]
    strict_checks: tuple[str, ...] = ()
    source_paths: tuple[Path, ...] = ()
    generated_after: float | None = None


def _script(name: str) -> str:
    return str((ROOT / "tools" / "solidworks_codex" / "scripts" / name).resolve())


def build_gate_contract() -> GateContract:
    py = sys.executable or "python"
    suite_report = "tools/solidworks_codex/reports/live_capability_suite/live_capability_suite.json"
    shaper_report = "tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json"
    return GateContract(
        name="solidworks_live_validation_gate",
        output_json="tools/solidworks_codex/reports/live_validation_gate.json",
        checks=(
            LiveCheck(
                name="live_session_smoke",
                command=(
                    py,
                    _script("sw_live_session_smoke.py"),
                    "--force",
                    "--out-dir",
                    "tools/solidworks_codex/live_fixture/live_session_smoke",
                    "--reports-dir",
                    "tools/solidworks_codex/reports/live_session_smoke",
                ),
                report_json="tools/solidworks_codex/reports/live_session_smoke/live_session_smoke.json",
                purpose="prove one hidden single SolidWorks session can create, inspect current model without a second session, close, exit, and release locks",
            ),
            LiveCheck(
                name="live_capability_suite",
                command=(
                    py,
                    _script("sw_live_capability_suite.py"),
                    "--force",
                    "--out-dir",
                    "tools/solidworks_codex/live_fixture/live_capability_suite",
                    "--reports-dir",
                    "tools/solidworks_codex/reports/live_capability_suite",
                    "--export-dir",
                    "tools/solidworks_codex/exports/live_capability_suite",
                ),
                report_json=suite_report,
                purpose="prove extrude/cut/revolve/revolve-cut/sketch edit/read-modify-rebuild/assembly insert/mates/callbacks/native artifacts/cleanup",
            ),
            LiveCheck(
                name="complete_shaper_v5",
                command=(
                    py,
                    _script("sw_create_complete_shaper_fixture.py"),
                    "--force",
                    "--out-dir",
                    "tools/solidworks_codex/live_fixture/shaper_machine_v5",
                    "--reports-dir",
                    "tools/solidworks_codex/reports/shaper_machine_v5",
                ),
                report_json=shaper_report,
                purpose="prove display-grade native bullhead shaper assembly with strict component/mate/mass/interference/cleanup evidence",
            ),
        ),
        notes=(
            "Runs checks serially to avoid multiple SolidWorks COM sessions/windows.",
            "Native .SLDASM/.SLDPRT files are primary evidence; STEP export is optional smoke only.",
            "Generated live_fixture/reports/exports are runtime artifacts and are git-ignored.",
        ),
    )





def live_session_smoke_strict_checks() -> tuple[str, ...]:
    return ("single_session_smoke",)


def capability_suite_strict_checks() -> tuple[str, ...]:
    return (
        "native_solidworks_artifacts",
        "assembly_mates_persisted",
        "open_existing_modify_reopen",
        "operation_context_guards",
        "interference_callback",
        "mass_callback",
        "post_cleanup_single_session",
    )


def shaper_v5_strict_checks() -> tuple[str, ...]:
    return (
        "part_count",
        "component_count",
        "mass_callback",
        "interference_clearance",
        "mate_semantics",
        "inspect_model_understand",
        "post_cleanup_single_session",
    )


def _expected_inspect_mates() -> dict[str, tuple[str, list[str]]]:
    return {
        "Bed_Column_Distance_Mate": ("MateDistanceDim", ["cast_bed_with_t_slots", "column_frame_with_window"]),
        "BullGear_CrankShaft_Concentric_Mate": ("MateConcentric", ["bull_gear_crank_disk", "crank_center_shaft"]),
        "Crank_Link_Concentric_Mate": ("MateConcentric", ["eccentric_crank_pin", "ram_drive_link"]),
        "Rocker_Pivot_Concentric_Mate": ("MateConcentric", ["slotted_rocker_arm", "rocker_pivot_shaft"]),
    }


def _component_pair_matches(component_names: Any, semantic_pair: list[str]) -> bool:
    if not isinstance(component_names, list) or len(component_names) < 2:
        return False
    text = "\n".join(str(item) for item in component_names)
    return all(name in text for name in semantic_pair)


def _strict_check_failed(data: dict[str, Any], check: str) -> bool:
    if check == "single_session_smoke":
        part_doc = (data.get("part_inspect") or data.get("inspect") or {}).get("active_document", {}) if isinstance(data.get("part_inspect") or data.get("inspect"), dict) else {}
        asm_doc = (data.get("assembly_inspect") or {}).get("active_document", {}) if isinstance(data.get("assembly_inspect"), dict) else {}
        inter = (data.get("callbacks") or {}).get("interference", {}) if isinstance(data.get("callbacks"), dict) else {}
        post = data.get("post_cleanup", {})
        smoke_mates = {
            str(mate.get("name", "")): mate
            for mate in asm_doc.get("mate_like_features", [])
            if isinstance(mate, dict)
        }
        smoke_mate = smoke_mates.get("Smoke_Distance_Mate", {})
        return (
            data.get("ok") is not True
            or data.get("started_second_session") is not False
            or part_doc.get("type") != "part"
            or asm_doc.get("type") != "assembly"
            or int(asm_doc.get("component_count_sampled", 0) or 0) < 2
            or not asm_doc.get("mate_like_features")
            or not _component_pair_matches(smoke_mate.get("components"), ["session_smoke_left", "session_smoke_right"])
            or inter.get("available") is not True
            or inter.get("count") != 0
            or "post_cleanup" not in data
            or bool(post.get("locked_files"))
            or bool(post.get("lock_files"))
        )
    if check == "native_solidworks_artifacts":
        native = data.get("native_artifacts", {})
        return not native.get("assembly_exists") or int(native.get("part_count", 0) or 0) < 4 or not native.get("primary")
    if check == "assembly_mates_persisted":
        names = {str(item.get("name", "")) for item in data.get("assembly_features", []) if isinstance(item, dict)}
        return not {"Concentric_Mate", "Distance_Mate"}.issubset(names)
    if check == "open_existing_modify_reopen":
        reopen = data.get("reopen_modify", {})
        save = reopen.get("save", {}) if isinstance(reopen, dict) else {}
        return (
            reopen.get("dimension") != "D1@Edited_Sketch_Dimension"
            or reopen.get("persisted") is not True
            or abs(float(reopen.get("after_reopen_m", 0) or 0) - 0.028) > 1e-6
            or save.get("ok") is not True
            or int(save.get("errors", 0) or 0) != 0
        )
    if check == "operation_context_guards":
        context = data.get("operation_context", {})
        expected = {
            "extrude": {"document": "extrude_cut_plate.SLDPRT", "operations": {"Body_Plate": {"profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"}, "Round_Through_Hole": {"profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"}, "Rectangular_Window_Cut": {"profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"}}},
            "revolve": {"document": "revolve_boss_part.SLDPRT", "operations": {"Revolve_Boss_Profile": {"profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"}}},
            "revolve_cut": {"document": "revolve_cut_part.SLDPRT", "operations": {"Revolve_Boss_Profile": {"profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"}, "Revolve_Cut_Bore": {"profile": "closed_cut_profile_with_centerline", "geometry": {"lines": 4, "circles": 0, "centerlines": 1}, "feature_type": "RevCut", "api": "FeatureRevolveCut2"}}},
            "editable": {"document": "editable_dimension_plate.SLDPRT", "operations": {"Body_Editable_Plate": {"profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"}, "Edited_Sketch_Dimension": {"profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3", "dimension": "D1@Edited_Sketch_Dimension"}}},
        }
        for part_key, part_expected in expected.items():
            part_actual = context.get(part_key, {}) if isinstance(context, dict) else {}
            if part_actual.get("document") != part_expected["document"]:
                return True
            if not part_actual.get("active_title"):
                return True
            if Path(str(part_actual.get("saved_path", ""))).name != part_expected["document"]:
                return True
            operations = part_actual.get("operations", {})
            for op_name, op_expected in part_expected["operations"].items():
                op_actual = operations.get(op_name, {})
                if not op_actual.get("sketch"):
                    return True
                for field, expected_value in op_expected.items():
                    if op_actual.get(field) != expected_value:
                        return True
                readback = op_actual.get("readback", {})
                if not readback:
                    return True
                if readback.get("source") != "reopened_feature_tree":
                    return True
                if readback.get("sketch") != op_actual.get("sketch"):
                    return True
                if readback.get("feature_type") != op_expected.get("feature_type"):
                    return True
                if readback.get("geometry") != op_expected.get("geometry"):
                    return True
        return False
    if check == "interference_callback":
        inter = data.get("callbacks", {}).get("interference", {})
        return not inter.get("available") or inter.get("count") is None
    if check == "interference_clearance":
        inter = data.get("callbacks", {}).get("interference", {})
        return not inter.get("available") or inter.get("count") != 0
    if check == "mass_callback":
        mass = data.get("callbacks", {}).get("mass", {})
        return not mass.get("available") or float(mass.get("mass_kg", 0) or 0) <= 0
    if check == "post_cleanup_single_session":
        post = data.get("post_cleanup", {})
        return "post_cleanup" not in data or bool(post.get("locked_files")) or bool(post.get("lock_files"))
    if check == "part_count":
        return int(data.get("part_count", 0) or 0) != 24
    if check == "component_count":
        return int(data.get("component_count", 0) or 0) != 58
    if check == "mate_semantics":
        mates = data.get("mates", [])
        required = {
            "Bed_Column_Distance_Mate": ("distance", ["cast_bed_with_t_slots", "column_frame_with_window"]),
            "BullGear_CrankShaft_Concentric_Mate": ("concentric", ["bull_gear_crank_disk", "crank_center_shaft"]),
            "Crank_Link_Concentric_Mate": ("concentric", ["eccentric_crank_pin", "ram_drive_link"]),
            "Rocker_Pivot_Concentric_Mate": ("concentric", ["slotted_rocker_arm", "rocker_pivot_shaft"]),
        }
        by_name = {m.get("name"): m for m in mates if isinstance(m, dict)}
        for name, (kind, pair) in required.items():
            mate = by_name.get(name)
            if not mate or not mate.get("ok") or mate.get("kind") != kind or mate.get("semantic_pair") != pair:
                return True
        return False
    if check == "inspect_model_understand":
        inspect = data.get("inspect", {})
        doc = inspect.get("active_document", {}) if isinstance(inspect, dict) else {}
        if doc.get("type") != "assembly" or int(doc.get("component_count_sampled", 0) or 0) < 58:
            return True
        mate_by_name = {str(m.get("name", "")): m for m in doc.get("mate_like_features", []) if isinstance(m, dict)}
        expected_mates = _expected_inspect_mates()
        if not set(expected_mates).issubset(set(mate_by_name)):
            return True
        for mate_name, (mate_type, pair) in expected_mates.items():
            mate = mate_by_name.get(mate_name, {})
            if mate.get("type") != mate_type:
                return True
            if mate.get("suppressed") is True:
                return True
            if not _component_pair_matches(mate.get("components"), pair):
                return True
        understanding = data.get("model_understanding", {})
        inv = ((understanding.get("baseline") or {}).get("inventory") or {}) if isinstance(understanding, dict) else {}
        spatial = (((understanding.get("cad_evidence_graph") or {}).get("spatial_evidence") or {}) if isinstance(understanding, dict) else {})
        if int(inv.get("component_count", 0) or 0) < 58:
            return True
        relations = spatial.get("near_or_overlap_pairs") or []
        return not relations
    return True

def _read_path(data: dict[str, Any], dotted: str) -> Any:
    value: Any = data
    for segment in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(segment)
    return value


def _report_failed_validation(data: dict[str, Any]) -> list[str]:
    validation = data.get("validation")
    if not isinstance(validation, dict):
        return ["validation_missing"]
    if validation.get("ok") is not True:
        failed = validation.get("failed_capabilities", validation.get("failed", []))
        if isinstance(failed, list):
            return [str(item) for item in failed] or ["validation_not_ok"]
        return [str(failed)]
    return []


def validate_gate_reports(expectations: Iterable[ReportExpectation]) -> dict[str, Any]:
    failed: list[str] = []
    reports: dict[str, Any] = {}
    for expectation in expectations:
        path = expectation.path
        if not path.exists():
            failed.append(f"missing_report:{expectation.name}")
            reports[expectation.name] = {"path": str(path), "error": "missing"}
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            failed.append(f"invalid_json:{expectation.name}")
            reports[expectation.name] = {"path": str(path), "error": str(exc)}
            continue
        if expectation.source_paths:
            try:
                report_mtime = path.stat().st_mtime
                newest_source = max(source.stat().st_mtime for source in expectation.source_paths if source.exists())
                if report_mtime < newest_source:
                    failed.append(f"stale_report:{expectation.name}")
            except ValueError:
                failed.append(f"missing_source_for_freshness:{expectation.name}")
        if expectation.generated_after is not None:
            try:
                if path.stat().st_mtime < expectation.generated_after:
                    failed.append(f"stale_run_report:{expectation.name}")
            except OSError:
                failed.append(f"missing_report_stat:{expectation.name}")
        reports[expectation.name] = data
        if data.get("ok") is not True:
            failed.append(f"report_not_ok:{expectation.name}")
        for dotted in expectation.required_truthy_paths:
            if _read_path(data, dotted) is not True:
                failed.append(f"missing_truthy:{expectation.name}:{dotted}")
        for check in expectation.strict_checks:
            if _strict_check_failed(data, check):
                failed.append(f"strict:{expectation.name}:{check}")
        for item in _report_failed_validation(data):
            failed.append(f"validation:{expectation.name}:{item}")

    return {"ok": not failed, "failed": failed, "reports": reports}



def validation_for_gate_state(lockfile_preflight: dict[str, Any], validate_only: bool, expectations: Iterable[ReportExpectation]) -> dict[str, Any]:
    if not validate_only and lockfile_preflight.get("ok") is not True:
        return {"ok": False, "failed": ["skipped_due_to_generated_lock_files"], "reports": {}}
    return validate_gate_reports(expectations)

def report_expectations(contract: GateContract, executions: Iterable[dict[str, Any]] = ()) -> tuple[ReportExpectation, ...]:
    by_name = {check.name: check for check in contract.checks}
    generated_after = {str(item.get("name")): item.get("started_at_epoch") for item in executions if item.get("started_at_epoch") is not None}
    return (
        ReportExpectation(
            "live_session_smoke",
            ROOT / by_name["live_session_smoke"].report_json,
            ("ok",),
            live_session_smoke_strict_checks(),
            (
                Path(by_name["live_session_smoke"].command[1]),
                ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_inspect.py",
                ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_create_complete_shaper_fixture.py",
            ),
            generated_after.get("live_session_smoke"),
        ),
        ReportExpectation(
            "live_capability_suite",
            ROOT / by_name["live_capability_suite"].report_json,
            ("ok", "native_artifacts.primary"),
            capability_suite_strict_checks(),
            (Path(by_name["live_capability_suite"].command[1]), ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_inspect.py"),
            generated_after.get("live_capability_suite"),
        ),
        ReportExpectation(
            "complete_shaper_v5",
            ROOT / by_name["complete_shaper_v5"].report_json,
            ("ok",),
            shaper_v5_strict_checks(),
            (
                Path(by_name["complete_shaper_v5"].command[1]),
                ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_inspect.py",
                ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_model_understand.py",
            ),
            generated_after.get("complete_shaper_v5"),
        ),
    )


def solidworks_process_snapshots() -> list[dict[str, Any]]:
    script = (
        "Get-Process SLDWORKS -ErrorAction SilentlyContinue | "
        "Select-Object Id,Responding,PrivateMemorySize64 | ConvertTo-Json -Compress"
    )
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", script],
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except subprocess.TimeoutExpired:
        return []
    if not proc.stdout.strip():
        return []
    data = json.loads(proc.stdout)
    if isinstance(data, dict):
        data = [data]
    return [
        {
            "id": int(item.get("Id", 0) or 0),
            "responding": bool(item.get("Responding")),
            "private_memory_bytes": int(item.get("PrivateMemorySize64", 0) or 0),
        }
        for item in data
        if isinstance(item, dict)
    ]


def terminate_process(pid: int) -> None:
    subprocess.run(
        ["powershell", "-NoProfile", "-Command", f"Stop-Process -Id {int(pid)} -Force -ErrorAction SilentlyContinue"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
        timeout=10,
    )


def cleanup_solidworks_after_timeout(
    check: LiveCheck | None = None,
    process_snapshots: list[dict[str, Any]] | None = None,
    terminator: Any = terminate_process,
    max_private_memory_bytes: int = 1_900_000_000,
) -> dict[str, Any]:
    snapshots = process_snapshots if process_snapshots is not None else solidworks_process_snapshots()
    terminated: list[int] = []
    for item in snapshots:
        pid = int(item.get("id", 0) or 0)
        unhealthy = item.get("responding") is False or int(item.get("private_memory_bytes", 0) or 0) > max_private_memory_bytes
        if pid and unhealthy:
            terminator(pid)
            terminated.append(pid)
    return {
        "check": check.name if check else None,
        "processes": snapshots,
        "terminated_pids": terminated,
    }


def run_check(check: LiveCheck, timeout_seconds: int = 900, timeout_cleanup: Any = cleanup_solidworks_after_timeout) -> dict[str, Any]:
    try:
        proc = subprocess.run(
            check.command,
            cwd=ROOT,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as exc:
        cleanup_requested = False
        if timeout_cleanup is not None:
            timeout_cleanup(check)
            cleanup_requested = True
        return {
            "name": check.name,
            "returncode": 124,
            "stdout_tail": str(exc.stdout or "")[-6000:],
            "stderr_tail": f"timeout_after_{timeout_seconds}s",
            "command": list(check.command),
            "timeout_seconds": timeout_seconds,
            "timeout_cleanup_requested": cleanup_requested,
        }
    return {
        "name": check.name,
        "returncode": proc.returncode,
        "stdout_tail": proc.stdout[-6000:],
        "stderr_tail": proc.stderr[-6000:],
        "command": list(check.command),
    }


def default_stale_fixture_dirs() -> tuple[Path, ...]:
    base = ROOT / "tools" / "solidworks_codex" / "live_fixture"
    return tuple(base / name for name in ("shaper_machine", "shaper_machine_v2", "shaper_machine_v3", "shaper_machine_v4"))


def is_safe_stale_fixture_dir(path: Path) -> bool:
    try:
        resolved = path.resolve()
        base = (ROOT / "tools" / "solidworks_codex" / "live_fixture").resolve()
        current = (base / "shaper_machine_v5").resolve()
        suite = (base / "live_capability_suite").resolve()
    except OSError:
        return False
    if resolved in {current, suite, base}:
        return False
    if base not in resolved.parents:
        return False
    return resolved.name in {"shaper_machine", "shaper_machine_v2", "shaper_machine_v3", "shaper_machine_v4"}


def cleanup_stale_fixtures(remove: bool) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    for path in default_stale_fixture_dirs():
        entry: dict[str, Any] = {"path": str(path), "exists": path.exists(), "safe": is_safe_stale_fixture_dir(path), "removed": False}
        if remove and entry["exists"] and entry["safe"]:
            try:
                shutil.rmtree(path)
                entry["removed"] = True
            except OSError as exc:
                entry["error"] = f"{type(exc).__name__}: {exc}"
        entries.append(entry)
    return {"remove_requested": remove, "entries": entries}



def generated_lockfile_preflight(root: Path = ROOT) -> dict[str, Any]:
    """Detect stale SolidWorks lock files anywhere under generated live fixtures.

    A live gate run must not start another SolidWorks session if a previous crash
    left ~$ files behind. Those files are direct evidence that cleanup/lifecycle is
    unhealthy and continuing would make the next failure ambiguous.
    """
    live_fixture = root / "tools" / "solidworks_codex" / "live_fixture"
    lock_files: list[str] = []
    if live_fixture.exists():
        lock_files = [str(path) for path in sorted(live_fixture.rglob("~$*")) if path.is_file()]
    failed = ["solidworks_generated_lock_files"] if lock_files else []
    return {"ok": not lock_files, "failed": failed, "lock_files": lock_files, "scope": str(live_fixture)}


def execute_checks_with_lock_preflight(
    checks: Iterable[LiveCheck],
    root: Path = ROOT,
    runner: Any = run_check,
    lock_probe: Any = generated_lockfile_preflight,
    clock: Any = time.time,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    executions: list[dict[str, Any]] = []
    preflights: list[dict[str, Any]] = []
    for check in checks:
        before = lock_probe(root)
        preflights.append(before)
        if before.get("ok") is not True:
            break
        started_at_epoch = float(clock())
        result = runner(check)
        result.setdefault("started_at_epoch", started_at_epoch)
        executions.append(result)
        after = lock_probe(root)
        preflights.append(after)
        if result.get("returncode") != 0 or after.get("ok") is not True:
            break
    return executions, preflights

def write_gate_report(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--contract-only", action="store_true")
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--cleanup-stale", action="store_true", help="remove only known stale shaper_machine/v2/v3/v4 generated fixture dirs")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/live_validation_gate.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    contract = build_gate_contract()
    out = ROOT / args.out
    if args.contract_only:
        payload = {"ok": True, "contract": asdict(contract), "stale_fixture_cleanup": cleanup_stale_fixtures(False)}
        write_gate_report(out, payload)
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    executions: list[dict[str, Any]] = []
    lockfile_preflight = generated_lockfile_preflight(ROOT)
    inter_check_lockfile_preflights: list[dict[str, Any]] = []
    if not args.validate_only and lockfile_preflight["ok"]:
        executions, inter_check_lockfile_preflights = execute_checks_with_lock_preflight(contract.checks, ROOT)
        if inter_check_lockfile_preflights:
            lockfile_preflight = inter_check_lockfile_preflights[-1]

    validation = validation_for_gate_state(lockfile_preflight, args.validate_only, report_expectations(contract, executions))
    cleanup = cleanup_stale_fixtures(args.cleanup_stale)
    failed = list(validation["failed"])
    if not args.validate_only and not lockfile_preflight["ok"]:
        failed.extend(str(item) for item in lockfile_preflight.get("failed", []))
    failed.extend(f"process:{item['name']}:{item['returncode']}" for item in executions if item.get("returncode") != 0)
    payload = {
        "ok": not failed,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "contract": asdict(contract),
        "executions": executions,
        "validation": validation,
        "generated_lockfile_preflight": lockfile_preflight,
        "inter_check_lockfile_preflights": inter_check_lockfile_preflights,
        "stale_fixture_cleanup": cleanup,
        "failed": failed,
    }
    write_gate_report(out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
