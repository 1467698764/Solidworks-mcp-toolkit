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


def mate_participants(mate_name: str, diagnosis: dict[str, Any]) -> list[str]:
    for edge in diagnosis.get("mates", {}).get("edges", []):
        if str(edge.get("mate")) == mate_name:
            return [str(item) for item in edge.get("components", []) if item]
    return []


def affected_components(actions: list[dict[str, Any]], diagnosis: dict[str, Any]) -> list[str]:
    found: list[str] = []
    for action in actions:
        if action.get("kind") == "resolve_bad_mate":
            found.extend(mate_participants(str(action.get("target")), diagnosis))
        else:
            target = action.get("target")
            if target:
                found.append(str(target))
        if action.get("suggested_host"):
            found.append(str(action["suggested_host"]))
    result: list[str] = []
    seen: set[str] = set()
    for name in found:
        if name not in seen:
            seen.add(name)
            result.append(name)
    return sorted(result)


def quote_arg(value: str) -> str:
    return f"'{value}'"


def rollback_plan(actions: list[dict[str, Any]], diagnosis: dict[str, Any]) -> dict[str, Any]:
    paths = diagnosis.get("inventory", {}).get("component_paths", {})
    components = affected_components(actions, diagnosis)
    affected_files = sorted({str(paths[name]) for name in components if paths.get(name)})
    backup_report = "tools/solidworks_codex/reports/repair_plan_backup.json"
    return {
        "artifact": "rollback_plan",
        "affected_components": components,
        "affected_files": affected_files,
        "backup_report": backup_report,
        "backup_command": (
            "swctl.ps1 backup -Files "
            + ",".join(quote_arg(path) for path in affected_files)
            + f" -Out {backup_report}"
        ) if affected_files else "blocked: no affected native file paths found in diagnosis",
        "backup_status_command": f"swctl.ps1 backup-status -Report {backup_report}",
        "restore_command": f"swctl.ps1 restore-backup -Report {backup_report} -Apply",
        "blocks_mutation_without_backup": True,
        "missing_component_paths": sorted(name for name in components if not paths.get(name)),
    }


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
    rollback = rollback_plan(actions, diagnosis)
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": "read_only_plan",
        "ok": True,
        "document": diagnosis.get("document", {}),
        "source_diagnosis_ok": diagnosis.get("ok"),
        "actions": actions,
        "rollback_plan": rollback,
        "finding_counts": {key: len(value) for key, value in findings.items() if isinstance(value, list)},
        "operator_notes": [
            "do_not_apply_blindly",
            "prefer_local_repair_over_rebuild_when_geometry_and_interfaces_are_recoverable",
            "rollback_report_paths_are_required_before_mutation",
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
    rollback = plan.get("rollback_plan") or {}
    lines += ["", "## Rollback Plan"]
    lines.append(f"- Affected files: {', '.join(f'`{item}`' for item in rollback.get('affected_files', [])) or '`<none>`'}")
    lines.append(f"- Backup command: `{rollback.get('backup_command', '')}`")
    lines.append(f"- Restore command: `{rollback.get('restore_command', '')}`")
    lines.append(f"- Blocks mutation without backup: `{rollback.get('blocks_mutation_without_backup')}`")
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
