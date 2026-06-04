"""Execute reviewed mate group selectors in a live SolidWorks assembly."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

MATE_TYPES = {
    "coincident": 0,
    "concentric": 1,
    "perpendicular": 2,
    "parallel": 3,
    "distance": 5,
    "angle": 6,
}

FALLBACK_SELECT_TYPES = {
    "bbox_planar_face": "FACE",
    "cylindrical_axis": "AXIS",
    "slot_centerline": "EDGE",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def selector_origin(selector: dict[str, Any]) -> list[float]:
    fallback = selector.get("fallback") if isinstance(selector.get("fallback"), dict) else {}
    origin = fallback.get("origin_m")
    if not isinstance(origin, list):
        centerline = fallback.get("centerline_m") if isinstance(fallback.get("centerline_m"), dict) else {}
        start = centerline.get("start")
        end = centerline.get("end")
        if isinstance(start, list) and isinstance(end, list) and len(start) == 3 and len(end) == 3:
            origin = [(float(start[i]) + float(end[i])) / 2.0 for i in range(3)]
    if not isinstance(origin, list) or len(origin) != 3:
        return [0.0, 0.0, 0.0]
    return [float(value) for value in origin]


def selection_action(selector: dict[str, Any], append: bool) -> dict[str, Any]:
    fallback = selector.get("fallback") if isinstance(selector.get("fallback"), dict) else {}
    fallback_type = str(fallback.get("type") or "")
    origin = selector_origin(selector)
    return {
        "stable_id": selector.get("stable_id"),
        "component": selector.get("component"),
        "type": FALLBACK_SELECT_TYPES.get(fallback_type, "FACE"),
        "xyz_m": origin,
        "append": append,
        "strategy": selector.get("strategy"),
        "fallback_type": fallback_type,
    }


def planned_mate(item: dict[str, Any]) -> dict[str, Any]:
    selectors = [selector for selector in item.get("selection_selectors", []) if isinstance(selector, dict)]
    return {
        "group_id": item.get("group_id"),
        "mate_type": str(item.get("mate_type", "")).casefold(),
        "expected_mate_name": item.get("expected_mate_name"),
        "components": item.get("components", []),
        "selection_actions": [selection_action(selector, append=index > 0) for index, selector in enumerate(selectors)],
    }


def select_with_action(assembly: Any, action: dict[str, Any]) -> bool:
    x, y, z = action["xyz_m"]
    callout = None
    try:
        return bool(assembly.Extension.SelectByID2("", action["type"], x, y, z, bool(action["append"]), 0, callout, 0))
    except TypeError:
        return bool(assembly.Extension.SelectByID2("", action["type"], x, y, z, bool(action["append"]), 0, None, 0))


def selected_count(assembly: Any) -> int:
    try:
        return int(assembly.SelectionManager.GetSelectedObjectCount2(-1))
    except Exception:
        return 0


def add_selected_mate(assembly: Any, item: dict[str, Any]) -> dict[str, Any]:
    mate_type = str(item.get("mate_type", "")).casefold()
    if mate_type not in MATE_TYPES:
        return {"ok": False, "error": "unsupported_mate_type", "mate_type": mate_type}
    distance = float(item.get("distance_m", 0.0) or 0.0)
    angle = float(item.get("angle_rad", 0.0) or 0.0)
    mate_error = 0
    feature = assembly.AddMate5(
        MATE_TYPES[mate_type],
        -1,
        bool(item.get("flip", False)),
        distance,
        distance,
        distance,
        angle,
        angle,
        angle,
        0,
        0,
        0,
        False,
        False,
        0,
        mate_error,
    )
    if feature is not None and item.get("expected_mate_name"):
        try:
            feature.Name = str(item["expected_mate_name"])
        except Exception:
            pass
    return {
        "ok": feature is not None,
        "api": "AddMate5",
        "mate_type": mate_type,
        "expected_mate_name": item.get("expected_mate_name"),
        "mate_error": mate_error,
    }


def execute_manifest(manifest: dict[str, Any], assembly: Any) -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    executed: list[dict[str, Any]] = []
    for item in [macro for macro in manifest.get("macros", []) if isinstance(macro, dict)]:
        plan = planned_mate(item)
        if len(plan["selection_actions"]) != 2:
            findings["blocking"].append({
                "kind": "selector_count",
                "mate": item.get("expected_mate_name"),
                "reason": "live mate execution requires exactly two reviewed selection selectors",
                "detail": plan,
            })
            continue
        if hasattr(assembly, "ClearSelection2"):
            assembly.ClearSelection2(True)
        select_results = [select_with_action(assembly, action) for action in plan["selection_actions"]]
        count = selected_count(assembly)
        guard = {
            "cleared_selection_count": 0,
            "selection_count_before_mate": count,
            "component_pair": item.get("components", []),
            "select_by_id_calls": plan["selection_actions"],
            "select_results": select_results,
        }
        if count != 2 or not all(select_results):
            findings["blocking"].append({
                "kind": "selection_failed",
                "mate": item.get("expected_mate_name"),
                "reason": "selector execution did not produce exactly two selected entities",
                "detail": guard,
            })
            continue
        mate_result = add_selected_mate(assembly, item)
        mate_result["selection_guard"] = guard
        mate_result["selected_entities"] = count
        if mate_result["ok"]:
            if hasattr(assembly, "ForceRebuild3"):
                assembly.ForceRebuild3(False)
            findings["accepted"].append({
                "kind": "mate_executed",
                "mate": item.get("expected_mate_name"),
                "reason": "selected entities were mated with AddMate5 and rebuild was requested",
            })
        else:
            findings["blocking"].append({
                "kind": "addmate_failed",
                "mate": item.get("expected_mate_name"),
                "reason": mate_result.get("error", "AddMate5 did not return a feature"),
                "detail": mate_result,
            })
        executed.append(mate_result)
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "mode": "mate_group_live_execute",
        "document": manifest.get("document", {}),
        "counts": {
            "planned_mates": len([m for m in manifest.get("macros", []) if isinstance(m, dict)]),
            "executed_mates": len([m for m in executed if m.get("ok")]),
            "blocking_findings": len(findings["blocking"]),
        },
        "executed_mates": executed,
        "findings": findings,
    }


def dry_run_manifest(manifest: dict[str, Any]) -> dict[str, Any]:
    planned = [planned_mate(item) for item in manifest.get("macros", []) if isinstance(item, dict)]
    blockers = []
    for item in planned:
        if len(item["selection_actions"]) != 2:
            blockers.append({
                "kind": "selector_count",
                "mate": item.get("expected_mate_name"),
                "reason": "dry-run found a mate without exactly two executable selectors",
                "detail": item,
            })
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not blockers,
        "mode": "mate_group_live_execute",
        "dry_run": True,
        "document": manifest.get("document", {}),
        "counts": {
            "planned_mates": len(planned),
            "executable_mates": len(planned) - len(blockers),
            "blocking_findings": len(blockers),
        },
        "planned_mates": planned,
        "findings": {"blocking": blockers, "warning": [], "accepted": []},
    }


def attach_active_assembly() -> Any:
    import pythoncom  # type: ignore
    import win32com.client  # type: ignore

    pythoncom.CoInitialize()
    sw = win32com.client.Dispatch("SldWorks.Application")
    doc = sw.ActiveDoc
    if doc is None:
        raise RuntimeError("No active SolidWorks document")
    if int(doc.GetType()) != 2:
        raise RuntimeError("Active SolidWorks document is not an assembly")
    return doc


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute reviewed mate group selectors in a live SolidWorks assembly")
    parser.add_argument("--macro-manifest", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    manifest = load_json(Path(args.macro_manifest))
    result = dry_run_manifest(manifest) if args.dry_run else execute_manifest(manifest, attach_active_assembly())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "execution_ok": result["ok"], "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
