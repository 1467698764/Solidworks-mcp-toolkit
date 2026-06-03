"""Build a read-only local assembly repair plan from an assembly diagnosis JSON.

This is intentionally not an auto-fix tool. It converts evidence into ordered,
reviewable repair actions so a model can be resumed and patched locally instead
of being rebuilt from scratch.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def nearest_host(component: str, diagnosis: dict[str, Any]) -> str | None:
    candidates: list[tuple[float, str]] = []
    for pair in diagnosis.get("spatial", {}).get("near_or_touching_pairs", []):
        a = str(pair.get("a", ""))
        b = str(pair.get("b", ""))
        if component not in {a, b}:
            continue
        other = b if a == component else a
        if not other:
            continue
        try:
            gap = float(pair.get("gap_m", 0.0))
        except (TypeError, ValueError):
            gap = 0.0
        candidates.append((gap, other))
    if not candidates:
        return None
    return sorted(candidates, key=lambda item: (item[0], item[1]))[0][1]


def build_plan(diagnosis: dict[str, Any]) -> dict[str, Any]:
    actions: list[dict[str, Any]] = []
    bad_mates = list(diagnosis.get("mates", {}).get("bad_mates", []))
    hostless = list(diagnosis.get("standard_parts", {}).get("hostless", []))
    isolated = list(diagnosis.get("mate_graph", {}).get("isolated_components", []))

    for mate in bad_mates:
        actions.append({
            "kind": "resolve_bad_mate",
            "target": mate,
            "priority": "P0",
            "strategy": "suppress_or_delete_stale_mate_then_recreate_from_current_interface_evidence",
            "requires_live_solidworks": True,
        })

    for name in hostless:
        actions.append({
            "kind": "attach_hostless_standard_part",
            "target": name,
            "suggested_host": nearest_host(name, diagnosis),
            "priority": "P1",
            "strategy": "identify hole/axis/contact faces before adding concentric/coincident/lock rotation mates",
            "requires_live_solidworks": True,
        })

    hostless_set = set(hostless)
    for name in isolated:
        if name in hostless_set:
            continue
        actions.append({
            "kind": "classify_isolated_component",
            "target": name,
            "priority": "P2",
            "strategy": "classify as functional/reference/envelope/optional before adding or removing mates",
            "requires_live_solidworks": False,
        })

    findings = diagnosis.get("findings", {})
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": "read_only_plan",
        "ok": True,
        "document": diagnosis.get("document", {}),
        "source_diagnosis_ok": diagnosis.get("ok"),
        "actions": actions,
        "finding_counts": {key: len(value) for key, value in findings.items() if isinstance(value, list)},
        "operator_notes": [
            "do_not_apply_blindly",
            "prefer_local_repair_over_rebuild_when_geometry_and_interfaces_are_recoverable",
            "verify_rebuild_mates_interference_and_visual_state_after_each_applied_group",
        ],
    }


def markdown(plan: dict[str, Any]) -> str:
    lines = [
        "# Assembly Repair Plan",
        "",
        f"- Mode: `{plan['mode']}`",
        f"- Document: `{plan.get('document', {}).get('title', '')}`",
        f"- Source diagnosis ok: `{plan.get('source_diagnosis_ok')}`",
        "",
        "## Actions",
    ]
    if not plan.get("actions"):
        lines.append("- No repair actions proposed from current diagnosis evidence.")
    for i, action in enumerate(plan.get("actions", []), start=1):
        lines.append(
            f"{i}. **{action['kind']}** `{action['target']}` "
            f"priority=`{action['priority']}` strategy=`{action['strategy']}`"
        )
        if action.get("suggested_host"):
            lines.append(f"   - Suggested host: `{action['suggested_host']}`")
    lines += ["", "## Operator notes"]
    for note in plan.get("operator_notes", []):
        lines.append(f"- {note}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a read-only assembly repair plan from assembly diagnosis JSON")
    parser.add_argument("--diagnosis", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", default="")
    args = parser.parse_args()

    plan = build_plan(load_json(Path(args.diagnosis)))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(markdown(plan), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "action_count": len(plan["actions"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
