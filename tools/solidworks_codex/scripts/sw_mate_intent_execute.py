"""Execute engineering-level mate intent through the mate-group executor."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from . import sw_mate_group_execute as mate_exec
except ImportError:  # pragma: no cover - direct script execution
    import sw_mate_group_execute as mate_exec  # type: ignore


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def selector(intent: dict[str, Any], name: str) -> dict[str, Any]:
    interfaces = intent.get("interfaces") if isinstance(intent.get("interfaces"), dict) else {}
    value = interfaces.get(name)
    if not isinstance(value, dict):
        raise ValueError(f"joint {intent.get('id', '<unnamed>')} missing interface '{name}'")
    return value


def optional_selector(intent: dict[str, Any], name: str) -> dict[str, Any] | None:
    interfaces = intent.get("interfaces") if isinstance(intent.get("interfaces"), dict) else {}
    value = interfaces.get(name)
    return value if isinstance(value, dict) else None


def base_macro(intent: dict[str, Any], suffix: str, mate_type: str, selectors: list[dict[str, Any]]) -> dict[str, Any]:
    joint_id = str(intent.get("id") or intent.get("joint_id") or "mate_intent")
    name = str(intent.get("name") or intent.get("expected_mate_name") or f"MI_{joint_id}_{suffix}")
    if not name.endswith(suffix):
        name = f"{name}_{suffix}"
    return {
        "group_id": joint_id,
        "intent_kind": str(intent.get("kind") or ""),
        "mate_type": mate_type,
        "expected_mate_name": name,
        "components": intent.get("components", []),
        "selection_selectors": selectors,
        "verification": ["rebuild", "mate_errors", "readback_participants"],
    }


def apply_common_parameters(macro: dict[str, Any], intent: dict[str, Any]) -> dict[str, Any]:
    for key in (
        "distance_m",
        "distance_min_m",
        "distance_max_m",
        "angle_rad",
        "angle_min_rad",
        "angle_max_rad",
        "angle_deg",
        "angle_min_deg",
        "angle_max_deg",
        "gear_ratio_numerator",
        "gear_ratio_denominator",
        "slot_constraint_type",
        "slot_distance_m",
        "slot_percent",
        "width_constraint_type",
        "width_distance_m",
        "flip",
    ):
        if key in intent:
            macro[key] = intent[key]
    return macro


def revolute_macros(intent: dict[str, Any]) -> list[dict[str, Any]]:
    macros = [
        base_macro(intent, "concentric", "concentric", [selector(intent, "shaft_axis"), selector(intent, "bore_axis")])
    ]
    axial_left = optional_selector(intent, "shaft_axial_face")
    axial_right = optional_selector(intent, "housing_axial_face") or optional_selector(intent, "bore_axial_face")
    if axial_left and axial_right:
        axial = base_macro(intent, "axial_locator", "limit_distance", [axial_left, axial_right])
        axial["distance_m"] = float(intent.get("axial_clearance_m", intent.get("distance_m", 0.0)) or 0.0)
        axial["distance_min_m"] = float(intent.get("axial_min_m", intent.get("distance_min_m", axial["distance_m"])) or 0.0)
        axial["distance_max_m"] = float(intent.get("axial_max_m", intent.get("distance_max_m", axial["distance_m"])) or 0.0)
        macros.append(axial)
    return macros


def rigid_mount_macros(intent: dict[str, Any]) -> list[dict[str, Any]]:
    macros = [
        base_macro(intent, "contact", "coincident", [selector(intent, "mount_face"), selector(intent, "host_face")])
    ]
    orient_a = optional_selector(intent, "orientation_face")
    orient_b = optional_selector(intent, "host_orientation_face")
    if orient_a and orient_b:
        macros.append(base_macro(intent, "orientation", "parallel", [orient_a, orient_b]))
    return macros


def prismatic_macros(intent: dict[str, Any]) -> list[dict[str, Any]]:
    macros = [
        base_macro(
            intent,
            "width",
            "width",
            [
                selector(intent, "guide_left_face"),
                selector(intent, "guide_right_face"),
                selector(intent, "slider_left_face"),
                selector(intent, "slider_right_face"),
            ],
        )
    ]
    travel_a = optional_selector(intent, "travel_stop_face")
    travel_b = optional_selector(intent, "travel_reference_face")
    if travel_a and travel_b:
        limit = base_macro(intent, "travel_limit", "limit_distance", [travel_a, travel_b])
        apply_common_parameters(limit, intent)
        macros.append(limit)
    return macros


def slot_pin_macros(intent: dict[str, Any]) -> list[dict[str, Any]]:
    return [apply_common_parameters(base_macro(intent, "slot", "slot", [selector(intent, "slot_path"), selector(intent, "pin_axis")]), intent)]


def gear_pair_macros(intent: dict[str, Any]) -> list[dict[str, Any]]:
    return [apply_common_parameters(base_macro(intent, "gear", "gear", [selector(intent, "driver_axis"), selector(intent, "driven_axis")]), intent)]


def direct_mate_macros(intent: dict[str, Any]) -> list[dict[str, Any]]:
    mate_type = str(intent.get("mate_type") or intent.get("kind") or "").casefold()
    selectors = intent.get("selection_selectors")
    if not isinstance(selectors, list):
        raise ValueError(f"direct mate intent {intent.get('id', '<unnamed>')} requires selection_selectors")
    return [apply_common_parameters(base_macro(intent, mate_type, mate_type, [item for item in selectors if isinstance(item, dict)]), intent)]


INTENT_EXPANDERS = {
    "revolute": revolute_macros,
    "hinge": revolute_macros,
    "rigid_mount": rigid_mount_macros,
    "fastened_mount": rigid_mount_macros,
    "prismatic": prismatic_macros,
    "linear_guide": prismatic_macros,
    "slot_pin": slot_pin_macros,
    "gear_pair": gear_pair_macros,
    "direct_mate": direct_mate_macros,
}


def expand_intent_spec(spec: dict[str, Any]) -> dict[str, Any]:
    intents = spec.get("mate_intents", spec.get("joints", []))
    if not isinstance(intents, list):
        raise ValueError("mate intent spec requires a 'mate_intents' or 'joints' list")
    macros: list[dict[str, Any]] = []
    for intent in [item for item in intents if isinstance(item, dict)]:
        kind = str(intent.get("kind") or "").casefold()
        expander = INTENT_EXPANDERS.get(kind)
        if expander is None:
            raise ValueError(f"unsupported mate intent kind: {kind}")
        macros.extend(expander(intent))
    return {
        "mode": "mate_intent_execute_manifest",
        "source_mode": spec.get("mode", "engineering_mate_intent"),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "document": spec.get("document", {}),
        "design_intent": spec.get("design_intent", {}),
        "macros": macros,
    }


def dry_run_intent(spec: dict[str, Any]) -> dict[str, Any]:
    manifest = expand_intent_spec(spec)
    result = mate_exec.dry_run_manifest(manifest)
    result["mode"] = "mate_intent_execute"
    result["expanded_manifest"] = manifest
    result["intent_counts"] = {
        "mate_intents": len(spec.get("mate_intents", spec.get("joints", [])) or []),
        "expanded_mates": len(manifest["macros"]),
    }
    return result


def execute_intent(spec: dict[str, Any], assembly: Any) -> dict[str, Any]:
    manifest = expand_intent_spec(spec)
    result = mate_exec.execute_manifest(manifest, assembly)
    result["mode"] = "mate_intent_execute"
    result["expanded_manifest"] = manifest
    result["intent_counts"] = {
        "mate_intents": len(spec.get("mate_intents", spec.get("joints", [])) or []),
        "expanded_mates": len(manifest["macros"]),
    }
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Execute engineering mate intent in a live SolidWorks assembly")
    parser.add_argument("--intent-spec", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    spec = load_json(Path(args.intent_spec))
    result = dry_run_intent(spec) if args.dry_run else execute_intent(spec, mate_exec.attach_active_assembly())
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "execution_ok": result["ok"], "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
