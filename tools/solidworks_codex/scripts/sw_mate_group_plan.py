"""Build reviewable mate groups from repair and interface evidence.

The output is a read-only plan. It groups candidate mates by local repair intent
so later live SolidWorks steps can select real faces/axes and apply them one
group at a time with rebuild/interference checks between groups.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def component_index(interface_index: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("component")): item for item in interface_index.get("components", [])}


def group_id(prefix: str, target: str) -> str:
    return f"{prefix}_{target}".replace(" ", "_")


def standard_mates(component: str, host: str | None) -> list[dict[str, Any]]:
    if not host:
        return []
    return [
        {
            "type": "concentric",
            "selection_intent": "component cylindrical axis to host hole or boss axis",
            "lock_rotation": True,
        },
        {
            "type": "coincident",
            "selection_intent": "component seating face to host seating/contact face",
        },
    ]


def build_plan(repair_plan: dict[str, Any], interface_index: dict[str, Any]) -> dict[str, Any]:
    components = component_index(interface_index)
    groups: list[dict[str, Any]] = []

    for action in repair_plan.get("actions", []):
        kind = action.get("kind")
        target = str(action.get("target", ""))
        if kind == "resolve_bad_mate":
            groups.append(
                {
                    "group_id": group_id("repair", target),
                    "source_action": kind,
                    "priority": action.get("priority", "P0"),
                    "components": [],
                    "suggested_mates": [
                        {
                            "type": "recreate_from_current_interfaces",
                            "selection_intent": "inspect stale mate participants, delete or suppress invalid reference, then recreate with live selected entities",
                        }
                    ],
                    "evidence": {"bad_mate": target},
                    "verification": ["rebuild", "mate_errors", "local_interference"],
                }
            )
        elif kind == "attach_hostless_standard_part":
            host = action.get("suggested_host") or components.get(target, {}).get("nearest_component")
            groups.append(
                {
                    "group_id": group_id("standard", target),
                    "source_action": kind,
                    "priority": action.get("priority", "P1"),
                    "components": [target, host] if host else [target],
                    "suggested_mates": standard_mates(target, host),
                    "evidence": {
                        "suggested_host": host,
                        "target_role_hints": components.get(target, {}).get("role_hints", []),
                    },
                    "verification": ["rebuild", "mate_errors", "minimum_clearance"],
                }
            )
        elif kind == "classify_isolated_component":
            groups.append(
                {
                    "group_id": group_id("classify", target),
                    "source_action": kind,
                    "priority": action.get("priority", "P2"),
                    "components": [target],
                    "suggested_mates": [],
                    "evidence": {"nearest_component": components.get(target, {}).get("nearest_component")},
                    "verification": ["design_intent_confirmed_before_mating"],
                }
            )

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": True,
        "mode": "read_only_mate_group_plan",
        "document": repair_plan.get("document") or interface_index.get("document") or {},
        "mate_groups": groups,
        "operator_notes": [
            "requires_live_selection",
            "apply_one_group_then_rebuild_and_validate",
            "do_not_convert_bbox_candidates_directly_into_mates",
        ],
    }


def markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Mate Group Plan",
        "",
        f"- Mode: `{plan['mode']}`",
        f"- Document: `{plan.get('document', {}).get('title', '')}`",
        "",
        "## Groups",
    ]
    if not plan.get("mate_groups"):
        lines.append("- No mate groups proposed from current evidence.")
    for group in plan.get("mate_groups", []):
        lines.append(f"- `{group['group_id']}` priority=`{group['priority']}` source=`{group['source_action']}`")
        lines.append(f"  - Components: `{', '.join(str(c) for c in group.get('components', []))}`")
        if group.get("suggested_mates"):
            mates = ", ".join(str(mate.get("type")) for mate in group["suggested_mates"])
            lines.append(f"  - Suggested mates: `{mates}`")
        else:
            lines.append("  - Suggested mates: `<none until design intent is confirmed>`")
    lines += ["", "## Operator Notes"]
    for note in plan.get("operator_notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a read-only mate group plan from repair and interface evidence")
    parser.add_argument("--repair-plan", required=True)
    parser.add_argument("--interface-index", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", default="")
    args = parser.parse_args()

    plan = build_plan(load_json(Path(args.repair_plan)), load_json(Path(args.interface_index)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(markdown(plan), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "group_count": len(plan["mate_groups"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
