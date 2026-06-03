"""Generate a controlled live SolidWorks protocol for mate group macros.

The output is intentionally an execution work order, not an automatic blind
executor.  It makes each group explicit, inserts checkbacks after every group,
and blocks when the upstream mate-group validation report is not clean.
"""
from __future__ import annotations

import argparse
import json
from collections import OrderedDict
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def macro_items(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    return [item for item in manifest.get("macros", []) if isinstance(item, dict)]


def group_macros(macros: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]]]]:
    grouped: "OrderedDict[str, list[dict[str, Any]]]" = OrderedDict()
    for item in macros:
        gid = str(item.get("group_id") or "ungrouped")
        grouped.setdefault(gid, []).append(item)
    return list(grouped.items())


def validation_blockers(validation: dict[str, Any] | None) -> list[dict[str, Any]]:
    if not validation:
        return []
    findings = validation.get("findings") if isinstance(validation, dict) else {}
    blocking = findings.get("blocking", []) if isinstance(findings, dict) else []
    if validation.get("ok") is False or blocking:
        return [{
            "kind": "validation_not_ok",
            "reason": "mate group validation report contains blocking findings",
            "detail": blocking,
        }]
    return []


def components_for(items: list[dict[str, Any]]) -> list[str]:
    seen: list[str] = []
    for item in items:
        for comp in item.get("components", []) or []:
            name = str(comp)
            if name and name not in seen:
                seen.append(name)
    return seen


def expected_names(items: list[dict[str, Any]]) -> list[str]:
    return [str(item.get("expected_mate_name")) for item in items if item.get("expected_mate_name")]


def build_group_steps(group_id: str, items: list[dict[str, Any]], model: str) -> list[dict[str, Any]]:
    names = expected_names(items)
    macros = [str(item.get("macro") or item.get("path") or "") for item in items]
    return [
        {
            "action": "backup_native_files",
            "tool": "solidworks_backup",
            "reason": "preserve rollback point before mutating mates",
            "inputs": {"model": model, "components": components_for(items)},
            "blocking_if": ["backup_missing", "backup_status_not_ok"],
        },
        {
            "action": "capture_before_snapshot",
            "tool": "solidworks_session_snapshot + solidworks_inspect",
            "reason": "record document/process/window state before this mate group",
            "outputs": [f"{group_id}_before_snapshot.json", f"{group_id}_before_inspect.json"],
        },
        {
            "action": "select_live_entities_for_macro",
            "tool": "solidworks_selection_report",
            "reason": "macro drafts require two reviewed SolidWorks selections; never infer live faces from bbox only",
            "expected_components": components_for(items),
            "expected_mates": names,
            "blocking_if": ["wrong_document", "selection_component_mismatch", "selection_entity_type_mismatch"],
        },
        {
            "action": "run_reviewed_macro",
            "tool": "SolidWorks macro runner/manual reviewed macro",
            "reason": "apply exactly one reviewed mate macro at a time, preserving the expected mate name",
            "macros": macros,
            "expected_mates": names,
            "blocking_if": ["macro_error", "unexpected_document_switch"],
        },
        {
            "action": "rebuild",
            "tool": "solidworks_rebuild",
            "reason": "force solver/rebuild state immediately after the group",
            "blocking_if": ["rebuild_error"],
        },
        {
            "action": "inspect_after_group",
            "tool": "solidworks_inspect",
            "reason": "read back actual mate names, components, suppression, and solver status",
            "outputs": [f"{group_id}_after_inspect.json"],
        },
        {
            "action": "mate_group_execution_check",
            "tool": "solidworks_mate_group_execution_check",
            "reason": "verify expected named mates exist and report no solver/API errors",
            "expected_mates": names,
            "blocking_if": ["mate_missing", "mate_error"],
        },
        {
            "action": "interference_check",
            "tool": "solidworks_interference_check",
            "reason": "catch newly introduced physical clashes before continuing",
            "blocking_if": ["unexpected_interference"],
        },
        {
            "action": "cleanup_locks_and_windows",
            "tool": "solidworks_session_snapshot",
            "reason": "avoid stale lock files, extra windows, and memory drift before the next group",
            "blocking_if": ["generated_lock_leftover", "memory_budget_exceeded"],
        },
    ]


def build_protocol(manifest: dict[str, Any], validation: dict[str, Any] | None, model: str) -> dict[str, Any]:
    blockers = validation_blockers(validation)
    macros = macro_items(manifest)
    findings = {"blocking": blockers, "warning": [], "accepted": []}
    if blockers:
        return {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "ok": False,
            "mode": "mate_group_live_protocol",
            "model": model,
            "policy": policy(),
            "counts": {"groups": 0, "macros": len(macros), "expected_mates": len(expected_names(macros))},
            "groups": [],
            "findings": findings,
        }

    groups = []
    for gid, items in group_macros(macros):
        groups.append({
            "group_id": gid,
            "components": components_for(items),
            "expected_mates": expected_names(items),
            "mate_types": [str(item.get("mate_type")) for item in items if item.get("mate_type")],
            "steps": build_group_steps(gid, items, model),
        })
    findings["accepted"].append({
        "kind": "protocol_ready",
        "reason": "validation is clean and live steps are grouped with per-group checkbacks",
    })
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": True,
        "mode": "mate_group_live_protocol",
        "model": model,
        "policy": policy(),
        "counts": {"groups": len(groups), "macros": len(macros), "expected_mates": len(expected_names(macros))},
        "groups": groups,
        "findings": findings,
    }


def policy() -> dict[str, Any]:
    return {
        "one_group_at_a_time": True,
        "stop_on_blocker": True,
        "no_bbox_to_live_mate_without_selection_evidence": True,
        "require_backup_before_write": True,
        "require_rebuild_inspect_execution_check_after_each_group": True,
        "require_interference_check_after_each_group": True,
        "cleanup_generated_locks_and_extra_windows": True,
    }


def markdown(protocol: dict[str, Any]) -> str:
    lines = ["# Mate Group Live Protocol", ""]
    lines += [
        f"- Timestamp: `{protocol['timestamp']}`",
        f"- OK: `{protocol['ok']}`",
        f"- Model: `{protocol.get('model') or '<active SolidWorks document>'}`",
        f"- Groups: `{protocol['counts']['groups']}`",
        f"- Expected mates: `{protocol['counts']['expected_mates']}`",
        "",
        "## Policy",
        "",
    ]
    for key, value in protocol["policy"].items():
        lines.append(f"- `{key}`: `{value}`")
    lines += ["", "## Blocking findings", ""]
    blockers = protocol["findings"]["blocking"]
    if blockers:
        for item in blockers:
            lines.append(f"- `{item['kind']}`: {item['reason']}")
    else:
        lines.append("- <none>")
    lines += ["", "## Groups", ""]
    for group in protocol["groups"]:
        lines += [
            f"### `{group['group_id']}`",
            "",
            f"- Components: {', '.join(group['components']) or '<none>'}",
            f"- Expected mates: {', '.join(group['expected_mates']) or '<none>'}",
            "",
        ]
        for i, step in enumerate(group["steps"], 1):
            lines.append(f"{i}. `{step['action']}` via `{step['tool']}` — {step['reason']}")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a controlled live protocol for mate group macro execution")
    parser.add_argument("--macro-manifest", required=True)
    parser.add_argument("--validation-report", required=True)
    parser.add_argument("--model", default="")
    parser.add_argument("--out", required=True)
    parser.add_argument("--markdown-out", default="")
    args = parser.parse_args()

    protocol = build_protocol(load_json(Path(args.macro_manifest)), load_json(Path(args.validation_report)), args.model)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(protocol, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_out:
        md = Path(args.markdown_out)
        md.parent.mkdir(parents=True, exist_ok=True)
        md.write_text(markdown(protocol), encoding="utf-8")
    print(json.dumps({"ok": True, "protocol_ok": protocol["ok"], "out": str(out), "markdown_out": args.markdown_out}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
