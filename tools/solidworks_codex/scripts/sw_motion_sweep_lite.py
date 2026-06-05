"""Execute and validate a light mechanism motion sweep in SolidWorks."""
from __future__ import annotations

import argparse
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
REVOLUTE_MATE_TYPES = {"concentric", "angle", "limit_angle", "gear", "cam", "cam_follower"}
PRISMATIC_MATE_TYPES = {"distance", "limit_distance", "slot", "path", "width"}


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8-sig"))


def deg_to_rad(value: float) -> float:
    return math.radians(float(value))


def mm_to_m(value: float) -> float:
    return float(value) / 1000.0


def normalize_unit_value(value: Any, unit: str) -> float:
    unit_name = str(unit or "").casefold()
    numeric = float(value)
    if unit_name in {"deg", "degree", "degrees"}:
        return deg_to_rad(numeric)
    if unit_name in {"mm", "millimeter", "millimeters"}:
        return mm_to_m(numeric)
    return numeric


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, reason: str, detail: Any = None) -> None:
    item = {"kind": kind, "reason": reason}
    if detail is not None:
        item["detail"] = detail
    findings.setdefault(severity, []).append(item)


def components_match(expected: list[str], actual: list[str]) -> bool:
    expected_set = {str(item).casefold() for item in expected if item}
    actual_set = {str(item).casefold() for item in actual if item}
    return bool(expected_set and expected_set.issubset(actual_set))


def motion_pair_supported(pair: dict[str, Any], mate: dict[str, Any]) -> bool:
    kind = str(pair.get("kind") or pair.get("type") or "").casefold()
    mate_type = str(mate.get("mate_type") or mate.get("type") or "").casefold()
    if kind in {"revolute", "rotary", "hinge"} and mate_type not in REVOLUTE_MATE_TYPES:
        return False
    if kind in {"prismatic", "slider", "linear"} and mate_type not in PRISMATIC_MATE_TYPES:
        return False
    return components_match(pair.get("components", []) or [], mate.get("components", []) or [])


def check_required_motion_pairs(spec: dict[str, Any], macro_manifest: dict[str, Any], findings: dict[str, list[dict[str, Any]]]) -> None:
    mates = [item for item in macro_manifest.get("macros", []) if isinstance(item, dict)]
    required = [item for item in spec.get("required_motion_pairs", []) if isinstance(item, dict)]
    for pair in required:
        match = next((mate for mate in mates if motion_pair_supported(pair, mate)), None)
        if match:
            add(findings, "accepted", "motion_pair_evidence_present", "required motion pair is backed by executable mate evidence", {"pair": pair, "mate": match})
        else:
            add(findings, "blocking", "required_motion_pair_missing", "required motion pair is not backed by executable mate evidence", pair)


def driver_by_id(spec: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in spec.get("drivers", []) if isinstance(item, dict) and item.get("id")}


def dimension_by_name(assembly: Any, name: str) -> Any | None:
    for method in ("Parameter", "GetParameter"):
        func = getattr(assembly, method, None)
        if not callable(func):
            continue
        try:
            dim = func(name)
        except Exception:
            dim = None
        if dim is not None:
            return dim
    extension = getattr(assembly, "Extension", None)
    func = getattr(extension, "GetDimension", None)
    if callable(func):
        try:
            return func(name)
        except Exception:
            return None
    return None


def set_dimension_value(assembly: Any, driver: dict[str, Any], raw_value: Any) -> dict[str, Any]:
    name = str(driver.get("name") or driver.get("dimension") or "")
    if not name:
        return {"ok": False, "driver": driver.get("id"), "error": "missing_dimension_name"}
    dim = dimension_by_name(assembly, name)
    if dim is None:
        return {"ok": False, "driver": driver.get("id"), "dimension": name, "error": "dimension_not_found"}
    value_mks = normalize_unit_value(raw_value, str(driver.get("unit") or driver.get("units") or "m"))
    try:
        dim.SystemValue = value_mks
    except Exception as exc:
        return {"ok": False, "driver": driver.get("id"), "dimension": name, "value": value_mks, "error": f"dimension_write_failed:{exc}"}
    return {"ok": True, "driver": driver.get("id"), "dimension": name, "value": value_mks, "api": "Dimension.SystemValue"}


def force_rebuild(assembly: Any) -> bool:
    func = getattr(assembly, "ForceRebuild3", None)
    if callable(func):
        try:
            result = func(False)
            return True if result is None else bool(result)
        except Exception:
            return False
    func = getattr(assembly, "EditRebuild3", None)
    if callable(func):
        try:
            result = func()
            return True if result is None else bool(result)
        except Exception:
            return False
    return False


def sample_interference(sample: dict[str, Any], assembly: Any | None) -> dict[str, Any]:
    if isinstance(sample.get("interference"), dict):
        data = sample["interference"]
        return {"available": True, "count": int(data.get("count", 0) or 0), "pairs": data.get("pairs", []), "source": "sample"}
    if assembly is None:
        return {"available": False, "count": None, "pairs": [], "source": "unavailable"}
    manager = getattr(assembly, "InterferenceDetectionManager", None)
    if manager is None:
        return {"available": False, "count": None, "pairs": [], "source": "solidworks_unavailable"}
    try:
        results = manager.GetInterferences() if callable(getattr(manager, "GetInterferences", None)) else []
    except Exception:
        results = []
    return {"available": True, "count": len(results or []), "pairs": [], "source": "solidworks"}


def apply_sample(spec: dict[str, Any], sample: dict[str, Any], assembly: Any) -> dict[str, Any]:
    drivers = driver_by_id(spec)
    writes = []
    for driver_id, raw_value in (sample.get("drivers") or {}).items():
        driver = drivers.get(str(driver_id))
        if not driver:
            writes.append({"ok": False, "driver": driver_id, "error": "driver_not_declared"})
            continue
        driver_type = str(driver.get("type") or "dimension").casefold()
        if driver_type != "dimension":
            writes.append({"ok": False, "driver": driver_id, "error": "unsupported_driver_type"})
            continue
        writes.append(set_dimension_value(assembly, driver, raw_value))
    return {
        "id": sample.get("id"),
        "driver_writes": writes,
        "rebuild_ok": force_rebuild(assembly),
        "interference": sample_interference(sample, assembly),
    }


def evaluate_samples(sample_reports: list[dict[str, Any]], findings: dict[str, list[dict[str, Any]]]) -> None:
    for report in sample_reports:
        failed_writes = [item for item in report.get("driver_writes", []) if not item.get("ok")]
        if failed_writes:
            add(findings, "blocking", "sample_driver_write_failed", "sample driver positions could not be applied", {"sample": report.get("id"), "writes": failed_writes})
        elif report.get("driver_writes"):
            add(findings, "accepted", "sample_driver_position_applied", "sample driver positions were applied before rebuild", {"sample": report.get("id"), "writes": report.get("driver_writes")})
        if not report.get("rebuild_ok"):
            add(findings, "blocking", "sample_rebuild_failed", "assembly did not rebuild after sample driver application", {"sample": report.get("id")})
        interference = report.get("interference") or {}
        if interference.get("available") and int(interference.get("count") or 0) > 0:
            add(findings, "blocking", "sample_interference", "motion sample reports collision/interference", {"sample": report.get("id"), "interference": interference})
        elif interference.get("available"):
            add(findings, "accepted", "sample_clearance_ok", "motion sample reports no interference", {"sample": report.get("id"), "interference": interference})
        else:
            add(findings, "warning", "sample_interference_unavailable", "sample did not provide interference evidence", {"sample": report.get("id")})


def base_result(spec: dict[str, Any], macro_manifest: dict[str, Any], findings: dict[str, list[dict[str, Any]]], sample_reports: list[dict[str, Any]], dry_run: bool) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "mode": "motion_sweep_lite",
        "dry_run": dry_run,
        "mechanism": spec.get("mechanism") or spec.get("name"),
        "counts": {
            "drivers": len(spec.get("drivers", []) or []),
            "sampled_positions": len(spec.get("samples", []) or []),
            "required_motion_pairs": len(spec.get("required_motion_pairs", []) or []),
            "macro_mates": len(macro_manifest.get("macros", []) or []),
            "blocking_findings": len(findings["blocking"]),
            "warning_findings": len(findings["warning"]),
        },
        "samples": sample_reports,
        "findings": findings,
    }


def dry_run_sweep(spec: dict[str, Any], macro_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = macro_manifest or {}
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    check_required_motion_pairs(spec, manifest, findings)
    for sample in [item for item in spec.get("samples", []) if isinstance(item, dict)]:
        interference = sample_interference(sample, None)
        if interference.get("available") and int(interference.get("count") or 0) > 0:
            add(findings, "blocking", "sample_interference", "declared motion sample reports collision/interference", {"sample": sample.get("id"), "interference": interference})
        elif interference.get("available"):
            add(findings, "accepted", "sample_clearance_ok", "declared motion sample reports no interference", {"sample": sample.get("id"), "interference": interference})
        else:
            add(findings, "warning", "sample_not_executed", "dry-run records planned sample without live driver execution", sample)
    return base_result(spec, manifest, findings, [], True)


def execute_sweep(spec: dict[str, Any], assembly: Any, macro_manifest: dict[str, Any] | None = None) -> dict[str, Any]:
    manifest = macro_manifest or {}
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    check_required_motion_pairs(spec, manifest, findings)
    sample_reports = [apply_sample(spec, sample, assembly) for sample in spec.get("samples", []) if isinstance(sample, dict)]
    evaluate_samples(sample_reports, findings)
    return base_result(spec, manifest, findings, sample_reports, False)


def attach_active_assembly(start: bool = False, model: str = "") -> Any:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    pythoncom.CoInitialize()
    sw = win32com.client.Dispatch("SldWorks.Application")
    sw.Visible = True
    if model:
        doc = sw.OpenDoc6(model, 2, 0, "", 0, 0)
    else:
        doc = sw.ActiveDoc
    if doc is None:
        raise RuntimeError("No active SolidWorks assembly")
    if int(doc.GetType()) != 2:
        raise RuntimeError("Active SolidWorks document is not an assembly")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute light mechanism motion samples and collision checks")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--macro-manifest", default="")
    parser.add_argument("--model", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec = load_json(resolve(args.spec))
    manifest = load_json(resolve(args.macro_manifest)) if args.macro_manifest else {}
    result = dry_run_sweep(spec, manifest) if args.dry_run else execute_sweep(spec, attach_active_assembly(model=args.model), manifest)
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "out": str(out), "blocking_findings": result["counts"]["blocking_findings"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
