"""Validate read-only mate group plans before macro/live execution."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_MATES = {"coincident", "concentric", "distance", "angle", "parallel", "perpendicular", "recreate_from_current_interfaces"}
REQUIRED_VERIFICATION = {"rebuild", "mate_errors"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, group_id: str, detail: Any, reason: str) -> None:
    findings.setdefault(severity, []).append({
        "kind": kind,
        "group_id": group_id,
        "detail": detail,
        "reason": reason,
    })


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

        if mates and len(components) < 2:
            add(findings, "blocking", "mate_group_component_count", group_id, components, "actionable mate groups need at least two components")
        for mate in mates:
            mate_type = str(mate.get("type", "")).casefold()
            if mate_type not in SUPPORTED_MATES:
                add(findings, "blocking", "unsupported_mate_type", group_id, mate_type, "mate type is not supported by current macro/live planning")
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
