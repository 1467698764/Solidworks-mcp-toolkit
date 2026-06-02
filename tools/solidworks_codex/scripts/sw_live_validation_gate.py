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



def capability_suite_strict_checks() -> tuple[str, ...]:
    return (
        "native_solidworks_artifacts",
        "assembly_mates_persisted",
        "open_existing_modify_reopen",
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
        "post_cleanup_single_session",
    )


def _strict_check_failed(data: dict[str, Any], check: str) -> bool:
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
        if not mates:
            return True
        for mate in mates:
            if mate.get("name") == "Shaper_Distance_Mate" and mate.get("semantic_pair") == ["cast_bed_with_t_slots", "column_frame_with_window"] and mate.get("ok"):
                return False
        return True
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


def report_expectations(contract: GateContract) -> tuple[ReportExpectation, ...]:
    by_name = {check.name: check for check in contract.checks}
    return (
        ReportExpectation(
            "live_capability_suite",
            ROOT / by_name["live_capability_suite"].report_json,
            ("ok", "native_artifacts.primary"),
            capability_suite_strict_checks(),
        ),
        ReportExpectation(
            "complete_shaper_v5",
            ROOT / by_name["complete_shaper_v5"].report_json,
            ("ok",),
            shaper_v5_strict_checks(),
        ),
    )


def run_check(check: LiveCheck) -> dict[str, Any]:
    proc = subprocess.run(
        check.command,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
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
    if not args.validate_only:
        for check in contract.checks:
            result = run_check(check)
            executions.append(result)
            if result["returncode"] != 0:
                break

    validation = validate_gate_reports(report_expectations(contract))
    cleanup = cleanup_stale_fixtures(args.cleanup_stale)
    failed = list(validation["failed"])
    failed.extend(f"process:{item['name']}:{item['returncode']}" for item in executions if item.get("returncode") != 0)
    payload = {
        "ok": not failed,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "contract": asdict(contract),
        "executions": executions,
        "validation": validation,
        "stale_fixture_cleanup": cleanup,
        "failed": failed,
    }
    write_gate_report(out, payload)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0 if payload["ok"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
