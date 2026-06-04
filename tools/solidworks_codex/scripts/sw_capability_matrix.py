"""Generate a CLI/MCP capability matrix for SolidWorks Codex."""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SERVER = ROOT / "tools" / "solidworks_codex" / "mcp" / "server.cjs"
SWCTL = ROOT / "tools" / "solidworks_codex" / "swctl.ps1"

WORKFLOW_BY_CLI = {
    "probe": "discover",
    "start-probe": "discover",
    "inspect": "discover",
    "start-inspect": "discover",
    "summary": "discover",
    "selection-report": "discover",
    "start-selection-report": "discover",
    "mass": "discover",
    "start-mass": "discover",
    "backup": "guarded_edit",
    "backup-status": "guarded_edit",
    "restore-backup": "guarded_edit",
    "set-dimension": "guarded_edit",
    "safe-set-dimension": "guarded_edit",
    "component-state": "guarded_edit",
    "component-insert": "guarded_edit",
    "start-component-insert": "guarded_edit",
    "feature-state": "guarded_edit",
    "part-feature-execute": "guarded_edit",
    "start-part-feature-execute": "guarded_edit",
    "mate-group-execute": "guarded_edit",
    "start-component-state": "guarded_edit",
    "start-feature-state": "guarded_edit",
    "rebuild": "guarded_edit",
    "start-rebuild": "guarded_edit",
    "export": "verify_export",
    "compare": "verify_export",
    "change-verify": "verify_export",
    "assembly-contract": "verify_export",
    "mate-group-execution-check": "verify_export",
    "interference": "verify_export",
    "start-interference": "verify_export",
    "preflight": "release_gate",
    "audit": "release_gate",
    "finalize": "release_gate",
    "live-gate": "release_gate",
    "github-readiness": "release_gate",
    "repo-health": "release_gate",
    "release-tree": "release_gate",
    "capability-matrix": "release_gate",
    "public-copy-guard": "release_gate",
    "issue-report": "analysis",
    "design-review": "analysis",
    "change-plan": "analysis",
    "workflow-plan": "analysis",
    "report-search": "analysis",
    "report-context": "analysis",
    "model-understand": "analysis",
    "assembly-diagnose": "analysis",
    "assembly-repair-plan": "analysis",
    "interface-index": "analysis",
    "mate-group-plan": "analysis",
    "mate-group-validate": "analysis",
    "mate-selection-check": "analysis",
    "mate-group-live-protocol": "analysis",
    "assembly-review-pipeline": "analysis",
    "session-snapshot": "handoff",
    "start-session-snapshot": "handoff",
    "worklog": "handoff",
    "handoff-bundle": "handoff",
    "tool-catalog": "handoff",
    "offline-demo": "handoff",
    "template-macro": "macro_generation",
    "mate-macro": "macro_generation",
    "mate-group-macro": "macro_generation",
    "mcp-tools": "external_reference",
}

SAFETY_BY_WORKFLOW = {
    "discover": "read_only",
    "analysis": "read_only",
    "handoff": "offline_or_read_only",
    "verify_export": "verification_or_export",
    "release_gate": "offline_gate",
    "external_reference": "offline_reference",
    "macro_generation": "generated_reviewable_artifact",
    "guarded_edit": "guarded_write",
}

SOLIDWORKS_NOT_REQUIRED = {
    "summary", "compare", "issue-report", "design-review", "change-plan", "workflow-plan", "report-search", "report-context", "model-understand", "assembly-diagnose", "assembly-repair-plan", "interface-index", "mate-group-plan", "mate-group-validate", "mate-selection-check", "mate-group-live-protocol", "assembly-review-pipeline",
    "worklog", "handoff-bundle", "tool-catalog", "offline-demo", "preflight", "audit", "finalize",
    "github-readiness", "repo-health", "release-tree", "public-copy-guard", "template-macro", "mate-macro", "mate-group-macro",
    "mcp-tools", "session-snapshot", "capability-matrix", "backup", "backup-status", "restore-backup", "change-verify", "assembly-contract", "mate-group-execution-check",
}

MCP_TO_CLI = {
    "solidworks_probe": "probe",
    "solidworks_start_probe": "start-probe",
    "solidworks_inspect": "inspect",
    "solidworks_start_inspect": "start-inspect",
    "solidworks_backup": "backup",
    "solidworks_backup_status": "backup-status",
    "solidworks_restore_backup": "restore-backup",
    "solidworks_set_dimension": "set-dimension",
    "solidworks_safe_set_dimension": "safe-set-dimension",
    "solidworks_rebuild": "rebuild",
    "solidworks_export": "export",
    "solidworks_mass_properties": "mass",
    "solidworks_compare_reports": "compare",
    "solidworks_change_verify": "change-verify",
    "solidworks_component_state": "component-state",
    "solidworks_component_insert": "component-insert",
    "solidworks_feature_state": "feature-state",
    "solidworks_part_feature_execute": "part-feature-execute",
    "solidworks_interference_check": "interference",
    "solidworks_template_macro": "template-macro",
    "solidworks_issue_report": "issue-report",
    "solidworks_mate_macro": "mate-macro",
    "solidworks_mate_group_macro": "mate-group-macro",
    "solidworks_mate_group_execute": "mate-group-execute",
    "solidworks_selection_report": "selection-report",
    "solidworks_session_snapshot": "session-snapshot",
    "solidworks_report_summary": "summary",
    "solidworks_design_review": "design-review",
    "solidworks_change_plan": "change-plan",
    "solidworks_report_search": "report-search",
    "solidworks_report_context": "report-context",
    "solidworks_model_understand": "model-understand",
    "solidworks_assembly_diagnose": "assembly-diagnose",
    "solidworks_assembly_repair_plan": "assembly-repair-plan",
    "solidworks_interface_index": "interface-index",
    "solidworks_mate_group_plan": "mate-group-plan",
    "solidworks_mate_group_validate": "mate-group-validate",
    "solidworks_mate_selection_check": "mate-selection-check",
    "solidworks_mate_group_execution_check": "mate-group-execution-check",
    "solidworks_mate_group_live_protocol": "mate-group-live-protocol",
    "solidworks_assembly_review_pipeline": "assembly-review-pipeline",
    "solidworks_worklog": "worklog",
    "solidworks_handoff_bundle": "handoff-bundle",
    "solidworks_tool_catalog": "tool-catalog",
    "solidworks_offline_demo": "offline-demo",
    "solidworks_preflight": "preflight",
    "solidworks_audit": "audit",
    "solidworks_finalize": "finalize",
    "solidworks_existing_mcp_tools": "mcp-tools",
}

CLI_ONLY_REQUIRED = {
    "workflow-plan": ["Target"],
}


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def list_mcp_tools() -> list[dict[str, Any]]:
    js = f"""
const fs = require('node:fs');
const text = fs.readFileSync({json.dumps(str(SERVER))}, 'utf8');
const m = text.match(/const toolSchemas = \\[(.*?)\\]\\s*;/s);
if (!m) throw new Error('toolSchemas not found');
const schemas = Function('return [' + m[1] + ']')();
process.stdout.write(JSON.stringify(schemas));
"""
    proc = subprocess.run(["node", "-e", js], cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout)
    return [x for x in json.loads(proc.stdout) if isinstance(x, dict)]


def list_swctl_commands() -> list[str]:
    text = SWCTL.read_text(encoding="utf-8-sig")
    match = re.search(r"\[ValidateSet\((.*?)\)\]", text, re.S)
    if not match:
        raise RuntimeError("Cannot find swctl ValidateSet")
    return re.findall(r"'([^']+)'", match.group(1))


def build_matrix() -> dict[str, Any]:
    tools = list_mcp_tools()
    mcp_by_cli: dict[str, dict[str, Any]] = {}
    for tool in tools:
        name = str(tool.get("name", ""))
        cli = MCP_TO_CLI.get(name, "")
        if cli:
            mcp_by_cli[cli] = tool

    capabilities = []
    for cli in sorted(list_swctl_commands()):
        workflow = WORKFLOW_BY_CLI.get(cli, "other")
        safety = SAFETY_BY_WORKFLOW.get(workflow, "unknown")
        mcp_tool = mcp_by_cli.get(cli)
        schema = (mcp_tool or {}).get("inputSchema") or {}
        props = sorted((schema.get("properties") or {}).keys()) if isinstance(schema, dict) else []
        required = schema.get("required", []) if isinstance(schema, dict) else []
        if not required:
            required = CLI_ONLY_REQUIRED.get(cli, [])
        capabilities.append({
            "cli": cli,
            "mcp": (mcp_tool or {}).get("name"),
            "workflow": workflow,
            "safety": safety,
            "solidworks_required": cli not in SOLIDWORKS_NOT_REQUIRED,
            "required": required,
            "properties": props,
            "description": (mcp_tool or {}).get("description", "CLI-only support command."),
        })

    mcp_names = {str(tool.get("name", "")) for tool in tools}
    mapped_mcp_names = {item["mcp"] for item in capabilities if item.get("mcp")}
    coverage = {
        "cli_commands": len(capabilities),
        "mcp_tools": len(tools),
        "mapped_mcp_tools": len(mapped_mcp_names),
        "has_cli_for_every_local_mcp": mcp_names == mapped_mcp_names,
        "has_safety_for_every_capability": all(item["safety"] != "unknown" for item in capabilities),
        "has_workflow_for_every_capability": all(item["workflow"] != "other" for item in capabilities),
        "mcp_without_cli": sorted(mcp_names - mapped_mcp_names),
    }
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "count": len(capabilities),
        "capabilities": capabilities,
        "coverage": coverage,
        "operator_notes": [
            "Prefer read-only discovery before guarded edits.",
            "Use backup before write commands and compare after rebuild/inspect.",
            "Use handoff artifacts when a task spans multiple Codex turns.",
        ],
    }


def markdown(data: dict[str, Any]) -> str:
    lines = ["# SolidWorks Codex Capability Matrix", ""]
    lines += [f"- Timestamp: `{data['timestamp']}`", f"- Capability count: `{data['count']}`", ""]
    c = data["coverage"]
    lines += [
        "## Coverage",
        "",
        f"- CLI commands: `{c['cli_commands']}`",
        f"- MCP tools: `{c['mcp_tools']}`",
        f"- MCP tools mapped to CLI: `{c['mapped_mcp_tools']}`",
        f"- CLI for every local MCP tool: `{c['has_cli_for_every_local_mcp']}`",
        f"- Safety label for every capability: `{c['has_safety_for_every_capability']}`",
        f"- Workflow label for every capability: `{c['has_workflow_for_every_capability']}`",
        "",
        "## Operator notes",
        "",
    ]
    lines += [f"- {note}" for note in data["operator_notes"]]
    lines += ["", "## Matrix", "", "| CLI | MCP | Workflow | Safety | SolidWorks required | Required args |", "| --- | --- | --- | --- | --- | --- |"]
    for item in data["capabilities"]:
        required = ", ".join(item["required"]) if item["required"] else "-"
        mcp = item["mcp"] or "-"
        lines.append(f"| `{item['cli']}` | `{mcp}` | `{item['workflow']}` | `{item['safety']}` | `{item['solidworks_required']}` | `{required}` |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/capability-matrix.md")
    parser.add_argument("--json-out", default="docs/capability-matrix.json")
    args = parser.parse_args()
    data = build_matrix()
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(data), encoding="utf-8")
    jout.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": data["coverage"]["has_cli_for_every_local_mcp"], "count": data["count"], "out": str(out), "json_out": str(jout)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
