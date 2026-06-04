"""Validate read-only mate group plans before macro/live execution."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_MATES = {"coincident", "concentric", "tangent", "distance", "limit_distance", "angle", "limit_angle", "parallel", "perpendicular", "symmetry", "cam", "cam_follower", "gear", "width", "path", "slot", "recreate_from_current_interfaces"}
REQUIRED_VERIFICATION = {"rebuild", "mate_errors"}
AXIAL_LOCATOR_MATES = {"coincident", "distance"}
AXIAL_LOCATOR_ROLES = {"axial_seating_locator", "axial_offset_locator"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, group_id: str, detail: Any, reason: str) -> None:
    findings.setdefault(severity, []).append({
        "kind": kind,
        "group_id": group_id,
        "detail": detail,
        "reason": reason,
    })


def finite_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def validate(plan: dict[str, Any]) -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "not_applicable": []}
    groups = [item for item in plan.get("mate_groups", []) if isinstance(item, dict)]

    if plan.get("mode") != "read_only_mate_group_plan":
        add(findings, "warning", "unexpected_plan_mode", "<plan>", plan.get("mode"), "expected a read_only_mate_group_plan")

    for group in groups:
        group_id = str(group.get("group_id") or "<unnamed>")
        components = [str(c) for c in group.get("components", []) if c]
        mates = [m for m in group.get("suggested_mates", []) if isinstance(m, dict)]
        verification = {str(v) for v in group.get("verification", [])}
        dof = group.get("dof_expectation") if isinstance(group.get("dof_expectation"), dict) else {}
        mate_types = {str(mate.get("type", "")).casefold() for mate in mates}
        mate_roles = {str(mate.get("dof_role", "")).casefold() for mate in mates if mate.get("dof_role")}

        if mates and len(components) < 2:
            add(findings, "blocking", "mate_group_component_count", group_id, components, "actionable mate groups need at least two components")
        for mate in mates:
            mate_type = str(mate.get("type", "")).casefold()
            if mate_type not in SUPPORTED_MATES:
                add(findings, "blocking", "unsupported_mate_type", group_id, mate_type, "mate type is not supported by current macro/live planning")
            selectors = [item for item in mate.get("selection_selectors", []) if isinstance(item, dict)]
            if mate_type == "width" and selectors and len(selectors) != 4:
                add(findings, "blocking", "width_selector_count", group_id, {"count": len(selectors), "selectors": selectors}, "width mates require four reviewed face selectors: two width faces and two tab faces")
            if mate_type == "slot":
                if selectors and len(selectors) != 2:
                    add(findings, "blocking", "slot_selector_count", group_id, {"count": len(selectors), "selectors": selectors}, "slot mates require two reviewed selectors: a slot path entity and a mating pin/edge/axis entity")
                constraint = finite_float(mate.get("slot_constraint_type", mate.get("constraint_type", 0)))
                if constraint is None or not constraint.is_integer() or int(constraint) not in {0, 1, 2, 3}:
                    add(findings, "blocking", "slot_constraint_type", group_id, mate.get("slot_constraint_type", mate.get("constraint_type")), "slot constraint type must be 0 free, 1 center, 2 distance, or 3 percent")
                elif int(constraint) == 2:
                    distance_m = finite_float(mate.get("slot_distance_m"))
                    if distance_m is None or distance_m < 0:
                        add(findings, "blocking", "slot_distance_required", group_id, mate.get("slot_distance_m"), "distance slot mates require a non-negative slot_distance_m")
                elif int(constraint) == 3:
                    percent = finite_float(mate.get("slot_percent"))
                    if percent is None or percent < 0 or percent > 100:
                        add(findings, "blocking", "slot_percent_range", group_id, mate.get("slot_percent"), "percent slot mates require slot_percent between 0 and 100")
            if mate_type == "path" and selectors and len(selectors) != 2:
                add(findings, "blocking", "path_selector_count", group_id, {"count": len(selectors), "selectors": selectors}, "path mates require two reviewed selectors: a moving point/vertex and a continuous path curve/edge/sketch entity")
            if mate_type == "symmetry" and selectors and len(selectors) != 3:
                add(findings, "blocking", "symmetry_selector_count", group_id, {"count": len(selectors), "selectors": selectors}, "symmetry mates require three reviewed selectors: two symmetric entities and one symmetry plane")
            if mate_type == "gear":
                numerator = mate.get("gear_ratio_numerator")
                denominator = mate.get("gear_ratio_denominator")
                if selectors and len(selectors) != 2:
                    add(findings, "blocking", "gear_selector_count", group_id, {"count": len(selectors), "selectors": selectors}, "gear mates require two reviewed cylindrical/axis selectors")
                try:
                    ratio_ok = float(numerator) > 0 and float(denominator) > 0
                except (TypeError, ValueError):
                    ratio_ok = False
                if not ratio_ok:
                    add(findings, "blocking", "gear_ratio_required", group_id, {"gear_ratio_numerator": numerator, "gear_ratio_denominator": denominator}, "gear mates require positive gear_ratio_numerator and gear_ratio_denominator")
            if mate_type in {"cam", "cam_follower"} and selectors and len(selectors) != 2:
                add(findings, "blocking", "cam_selector_count", group_id, {"count": len(selectors), "selectors": selectors}, "cam follower mates require two reviewed face/edge selectors")
        if mates and not dof:
            add(findings, "blocking", "missing_dof_expectation", group_id, {}, "actionable mate groups must state intended remaining degrees of freedom")
        if dof:
            remaining = dof.get("remaining_dof", [])
            if not isinstance(remaining, list):
                add(findings, "blocking", "invalid_dof_expectation", group_id, dof, "remaining_dof must be a list")
            if not dof.get("intent"):
                add(findings, "blocking", "invalid_dof_expectation", group_id, dof, "dof expectation must name the connection intent")
        if "concentric" in mate_types:
            has_axial_locator = bool(mate_types & AXIAL_LOCATOR_MATES) or bool(mate_roles & AXIAL_LOCATOR_ROLES)
            intended_rotation = str(dof.get("rotation_about_axis", "")).casefold() in {"free", "intended_free"}
            if not has_axial_locator and not intended_rotation:
                add(
                    findings,
                    "blocking",
                    "concentric_without_axial_locator",
                    group_id,
                    {"mate_types": sorted(mate_types), "dof_expectation": dof},
                    "concentric mates need axial locator evidence unless axial rotation/freedom is the stated mechanism intent",
                )
        if mates and not REQUIRED_VERIFICATION.issubset(verification):
            add(findings, "blocking", "missing_group_verification", group_id, sorted(verification), "actionable mate groups must require rebuild and mate error checks")
        if not mates and not any(v.startswith("design_intent") for v in verification):
            add(findings, "warning", "non_actionable_group_without_intent_gate", group_id, sorted(verification), "non-actionable groups should carry an intent confirmation gate")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "document": plan.get("document", {}),
        "counts": {
            "groups": len(groups),
            "actionable_groups": sum(1 for group in groups if group.get("suggested_mates")),
            "suggested_mates": sum(len(group.get("suggested_mates", []) or []) for group in groups),
        },
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate a read-only mate group plan")
    parser.add_argument("--mate-group-plan", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = validate(load_json(Path(args.mate_group_plan)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "validation_ok": result["ok"], "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
