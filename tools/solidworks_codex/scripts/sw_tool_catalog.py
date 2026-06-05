"""Generate a catalog of the local SolidWorks Codex MCP tools."""
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

GROUP_RULES = {
    "read_only": ["probe", "inspect", "summary", "selection", "mass"],
    "write_guarded": ["backup", "set_dimension", "component_state", "component_insert", "feature_state", "metadata_execute", "rebuild", "mate_group_execute", "motion_sweep"],
    "export_verify": ["export", "interference", "compare", "preflight", "audit", "finalize"],
    "analysis": ["issue", "design_review", "change_plan", "report_search", "report_context", "model_understand", "diagnose", "mate_selection_check"],
    "handoff": ["worklog", "handoff"],
    "macro_generation": ["template_macro", "mate_macro", "mate_group_macro"],
    "live_protocol": ["mate_group_live_protocol"],
    "external_reference": ["existing_mcp"],
}


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def extract_tool_schemas_text() -> str:
    text = SERVER.read_text(encoding="utf-8-sig")
    match = re.search(r"const toolSchemas = \[(.*?)]\s*;", text, re.S)
    if not match:
        raise RuntimeError("Cannot find toolSchemas in server.cjs")
    return "[" + match.group(1) + "]"


def list_tools_via_node() -> list[dict[str, Any]]:
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
    data = json.loads(proc.stdout)
    return [x for x in data if isinstance(x, dict)]


def group_for(name: str) -> str:
    short = name.replace("solidworks_", "")
    for group, keys in GROUP_RULES.items():
        if any(k in short for k in keys):
            return group
    return "other"


def build_catalog() -> dict[str, Any]:
    tools = []
    groups: dict[str, list[str]] = {}
    for tool in sorted(list_tools_via_node(), key=lambda t: t.get("name", "")):
        name = str(tool.get("name", ""))
        group = group_for(name)
        groups.setdefault(group, []).append(name)
        schema = tool.get("inputSchema") or {}
        props = sorted((schema.get("properties") or {}).keys()) if isinstance(schema, dict) else []
        tools.append({
            "name": name,
            "group": group,
            "description": tool.get("description", ""),
            "required": schema.get("required", []) if isinstance(schema, dict) else [],
            "properties": props,
        })
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "count": len(tools),
        "tools": tools,
        "groups": groups,
        "operator_notes": [
            "Do not blindly replay templates: inspect the current report, context, worklog, and handoff artifacts before choosing a tool.",
            "Before write operations, create a backup; change one variable at a time; then rebuild, inspect, and compare.",
            "Use handoff-bundle for pauses, session changes, and review handoff; use audit/finalize as release gates.",
        ],
    }


def markdown(cat: dict[str, Any]) -> str:
    lines = ["# SolidWorks MCP Tool Catalog", ""]
    lines += [f"- Timestamp: `{cat['timestamp']}`", f"- Tool count: `{cat['count']}`", ""]
    lines += ["## Operator notes"]
    lines += [f"- {note}" for note in cat["operator_notes"]]
    lines.append("")
    lines.append("## Groups")
    for group, names in sorted(cat["groups"].items()):
        lines.append(f"- `{group}`: {', '.join(f'`{n}`' for n in names)}")
    lines.append("")
    lines.append("## Tools")
    for tool in cat["tools"]:
        req = ", ".join(tool["required"]) if tool["required"] else "<none>"
        props = ", ".join(tool["properties"]) if tool["properties"] else "<none>"
        lines += [
            f"### `{tool['name']}`",
            "",
            f"- Group: `{tool['group']}`",
            f"- Description: {tool['description']}",
            f"- Required: `{req}`",
            f"- Properties: `{props}`",
            "",
        ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/tool_catalog.md")
    parser.add_argument("--json-out", default="tools/solidworks_codex/reports/tool_catalog.json")
    args = parser.parse_args()
    cat = build_catalog()
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(cat), encoding="utf-8")
    jout.write_text(json.dumps(cat, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "count": cat["count"], "out": str(out), "json_out": str(jout)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
