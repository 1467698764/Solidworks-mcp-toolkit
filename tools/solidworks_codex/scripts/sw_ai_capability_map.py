"""Generate an AI-facing capability map for SolidWorks Codex MCP orchestration."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import sw_tool_catalog

ROOT = Path(__file__).resolve().parents[3]

STAGES = [
    {
        "stage": "intent",
        "purpose": "Turn user language into design intent, validation profile, editable parameters, interfaces, and non-goals.",
        "preferred_tools": ["solidworks_workflow_plan", "solidworks_change_plan", "solidworks_design_review"],
        "mcp_value": "Keeps the reasoning model from jumping straight into native API calls before scope, evidence, and acceptance weight are explicit.",
        "native_api_policy": "Do not call native SolidWorks APIs here; this stage is reasoning and artifact generation.",
        "upper_limit": "Cannot invent missing engineering constraints; assumptions must be recorded and later verified.",
    },
    {
        "stage": "readback",
        "purpose": "Read active or specified native files into compact, searchable evidence.",
        "preferred_tools": ["solidworks_inspect", "solidworks_report_search", "solidworks_model_understand", "solidworks_report_context"],
        "mcp_value": "Compresses raw COM state into task-focused facts the AI can reason over without rereading the whole model.",
        "native_api_policy": "Use native COM only through inspect/probe wrappers unless a missing readback field is being added to the project.",
        "upper_limit": "Only proves what SolidWorks exposes through readback; weak selectors need live identity evidence.",
    },
    {
        "stage": "interface_graph",
        "purpose": "Name candidate faces, axes, slots, datums, component roles, proximity, and attachment evidence.",
        "preferred_tools": ["solidworks_interface_index", "solidworks_assembly_diagnose", "solidworks_assembly_review_pipeline"],
        "mcp_value": "Turns geometry into an engineering interface graph instead of relying on visual closeness.",
        "native_api_policy": "Use direct API capture when stable native identity is unavailable or selector confidence blocks execution.",
        "upper_limit": "BBox-only candidates are review evidence, not permission to create final mates.",
    },
    {
        "stage": "execution_plan",
        "purpose": "Convert intent and interfaces into part feature specs, component specs, mate intents, and validation gates.",
        "preferred_tools": ["solidworks_mate_group_plan", "solidworks_mate_group_validate", "solidworks_standard_part_resolve"],
        "mcp_value": "Groups operations by engineering intent, DOF, affected files, rollback scope, and verification sequence.",
        "native_api_policy": "Direct API is acceptable for faster spec execution only after the MCP artifact names selectors and expected readback.",
        "upper_limit": "A plan cannot compensate for absent face/axis identity or contradictory mechanism intent.",
    },
    {
        "stage": "native_execution",
        "purpose": "Mutate SolidWorks files through guarded APIs: features, components, metadata, mate intent, and motion drivers.",
        "preferred_tools": ["solidworks_part_feature_execute", "solidworks_component_insert", "solidworks_mate_intent_execute", "solidworks_mate_group_execute", "solidworks_motion_sweep_lite"],
        "mcp_value": "Provides structured specs, dry-run checks, evidence reports, and error surfaces around native SolidWorks calls.",
        "native_api_policy": "Use direct SolidWorks API when it is materially faster or more reliable, but return the same evidence contract.",
        "upper_limit": "Requires SolidWorks, reviewed selectors, and rollback discipline; cannot accept guessed attachment geometry.",
    },
    {
        "stage": "validation",
        "purpose": "Prove the native result matches the selected profile and can be resumed or repaired.",
        "preferred_tools": ["solidworks_rebuild", "solidworks_compare_reports", "solidworks_change_verify", "solidworks_interference_check", "solidworks_part_geometry_validate", "solidworks_visual_validate", "solidworks_engineering_lite"],
        "mcp_value": "Separates visual recognizability, mate health, clearance, geometry, BOM, and handoff evidence.",
        "native_api_policy": "Direct API checks are welcome when they add evidence; they do not replace report artifacts.",
        "upper_limit": "Offline validation cannot prove live motion or screenshots; live profile must say what remains unproven.",
    },
    {
        "stage": "handoff",
        "purpose": "Record progress, artifacts, assumptions, and next actions for interrupted multi-turn CAD work.",
        "preferred_tools": ["solidworks_worklog", "solidworks_handoff_bundle", "solidworks_tool_catalog", "solidworks_ai_capability_map"],
        "mcp_value": "Makes the next AI turn start from evidence instead of memory.",
        "native_api_policy": "No native API needed unless generating fresh readback before packaging.",
        "upper_limit": "Handoff quality depends on consistently logging decisions and artifact paths.",
    },
]

DIRECT_API_RULES = [
    "Use MCP reasoning tools to decide what should happen; use native SolidWorks APIs to do the smallest reliable set of live CAD calls.",
    "Prefer direct native API for high-volume geometry creation, batch mate insertion, or readback fields not yet wrapped, but emit the same MCP evidence schema.",
    "Never let direct API bypass design intent, selector confidence, backup, rebuild, inspect, and validation artifacts.",
    "When a native call fails, route the failure back through diagnosis tools instead of retrying blindly.",
]


def resolve(path: str) -> Path:
    candidate = Path(path)
    return candidate if candidate.is_absolute() else ROOT / candidate


def _role_for_tool(name: str, group: str) -> str:
    short = name.replace("solidworks_", "")
    if short in {"workflow_plan", "change_plan", "design_review"}:
        return "intent_planning"
    if short in {"inspect", "start_inspect", "probe", "start_probe", "report_search", "report_context", "model_understand"}:
        return "evidence_readback"
    if "interface" in short or "diagnose" in short or "review_pipeline" in short:
        return "interface_graph"
    if "mate_group_plan" in short or "validate" in short or "standard_part_resolve" in short:
        return "execution_planning"
    if group == "write_guarded":
        return "native_execution"
    if group == "export_verify":
        return "validation"
    if group == "handoff":
        return "handoff"
    return group


def build_map() -> dict[str, Any]:
    catalog = sw_tool_catalog.build_catalog()
    tool_index = []
    for tool in catalog["tools"]:
        required = list(tool.get("required") or [])
        properties = list(tool.get("properties") or [])
        optional = [item for item in properties if item not in required]
        tool_index.append({
            "name": tool["name"],
            "reasoning_role": _role_for_tool(tool["name"], tool["group"]),
            "mcp_group": tool["group"],
            "required": required,
            "optional": optional,
            "capability": tool.get("description", ""),
        })

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mission": "AI design reasoning -> engineering interface graph -> guarded SolidWorks execution -> validation evidence.",
        "tool_count": catalog["count"],
        "stages": STAGES,
        "direct_native_api_policy": DIRECT_API_RULES,
        "decision_rules": [
            "For new assemblies, create design intent and interface graph before adding mates.",
            "For existing assemblies, inspect, diagnose, index interfaces, then repair affected subgraphs.",
            "For mechanisms, declare intended DOF before accepting revolute, prismatic, slot, cam, gear, or limit mates.",
            "For generated parts, prefer semantic features and named interfaces over anonymous bodies.",
            "For every accepted change, rebuild, inspect, compare or validate profile evidence, and log handoff artifacts.",
        ],
        "tool_decision_index": tool_index,
    }


def markdown(data: dict[str, Any]) -> str:
    lines = [
        "# SolidWorks Codex AI Capability Map",
        "",
        f"- Timestamp: `{data['timestamp']}`",
        f"- Tool count: `{data['tool_count']}`",
        f"- Mission: {data['mission']}",
        "",
        "## Direct Native API Policy",
        "",
    ]
    lines.extend(f"- {rule}" for rule in data["direct_native_api_policy"])
    lines.extend(["", "## Reasoning Stages", ""])
    lines.append("| Stage | Purpose | Preferred MCP tools | Native API policy | Upper limit |")
    lines.append("| --- | --- | --- | --- | --- |")
    for stage in data["stages"]:
        tools = ", ".join(f"`{tool}`" for tool in stage["preferred_tools"])
        lines.append(f"| `{stage['stage']}` | {stage['purpose']} | {tools} | {stage['native_api_policy']} | {stage['upper_limit']} |")
    lines.extend(["", "## Decision Rules", ""])
    lines.extend(f"- {rule}" for rule in data["decision_rules"])
    lines.extend(["", "## Tool Decision Index", ""])
    lines.append("| Tool | Reasoning role | Required | Optional |")
    lines.append("| --- | --- | --- | --- |")
    for tool in data["tool_decision_index"]:
        required = ", ".join(f"`{item}`" for item in tool["required"]) if tool["required"] else "-"
        optional = ", ".join(f"`{item}`" for item in tool["optional"]) if tool["optional"] else "-"
        lines.append(f"| `{tool['name']}` | `{tool['reasoning_role']}` | {required} | {optional} |")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/ai_capability_map.md")
    parser.add_argument("--json-out", default="tools/solidworks_codex/reports/ai_capability_map.json")
    args = parser.parse_args()
    data = build_map()
    out = resolve(args.out)
    json_out = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(data), encoding="utf-8")
    json_out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "tool_count": data["tool_count"], "out": str(out), "json_out": str(json_out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
