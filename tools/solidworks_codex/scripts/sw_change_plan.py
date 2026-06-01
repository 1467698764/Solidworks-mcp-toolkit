"""Create a flexible, evidence-first change plan for a mechanical CAD task."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_report(path: str) -> dict[str, Any]:
    return json.loads(resolve(path).read_text(encoding="utf-8-sig"))


def doc(report: dict[str, Any]) -> dict[str, Any]:
    d = report.get("active_document") or {}
    return d if isinstance(d, dict) else {}


def rows(value: Any) -> list[dict[str, Any]]:
    return [x for x in (value or []) if isinstance(x, dict)]


def name_of(item: dict[str, Any]) -> str:
    return str(item.get("name2") or item.get("full_name") or item.get("display_name") or item.get("name") or "<unnamed>")


def text_of(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(k, "")) for k in ("name2", "path", "name", "type", "full_name", "feature")).lower()


def goal_hints(goal: str) -> dict[str, bool]:
    g = goal.lower()
    return {
        "dimension": bool(re.search(r"\d+(\.\d+)?\s*(mm|毫米|cm|m)", g)) or any(w in g for w in ["厚", "长", "宽", "直径", "孔", "间隙", "pcd", "dimension", "hole"]),
        "spatial": any(w in g for w in ["空间", "位置", "距离", "装配", "可行性", "spatial", "position"]),
        "interference": any(w in g for w in ["干涉", "碰", "clearance", "interference", "间隙"]),
        "constraint": any(w in g for w in ["同心", "重合", "mate", "约束", "配合", "固定", "定位"]),
        "manufacturing": any(w in g for w in ["孔", "螺", "销", "加工", "制造", "bolt", "screw", "dowel", "pin", "hole"]),
        "export": any(w in g for w in ["导出", "step", "stl", "图纸", "交付"]),
    }


def candidate_files(doc_data: dict[str, Any], comps: list[dict[str, Any]]) -> list[str]:
    files = []
    if doc_data.get("path"):
        files.append(str(doc_data.get("path")))
    files.extend(str(c.get("path")) for c in comps if c.get("path"))
    return sorted(dict.fromkeys(files))


def make_plan(report: dict[str, Any], goal: str, session_name: str) -> dict[str, Any]:
    d = doc(report)
    comps = rows(d.get("components"))
    dims = rows(d.get("dimensions"))
    feats = rows(d.get("features"))
    files = candidate_files(d, comps)
    hints = goal_hints(goal)
    dim_candidates = [name_of(x) for x in dims]
    component_candidates = [name_of(c) for c in comps]
    feature_candidates = [name_of(f) for f in feats]

    steps: list[dict[str, Any]] = []
    candidate_actions: list[dict[str, str]] = []
    decision_points: list[dict[str, str]] = []
    optional_branches: list[dict[str, str]] = []

    def step(title: str, purpose: str, command: str | None = None, evidence: str = "") -> None:
        steps.append({"title": title, "purpose": purpose, "command": command, "evidence_to_check": evidence})

    view = "auto"
    if hints["manufacturing"]:
        view = "manufacturing-holes"
    if hints["spatial"] or hints["interference"]:
        view = "spatial-assembly"
    if hints["dimension"] and not hints["spatial"]:
        view = "dimension-edit"

    step(
        "Build task-scoped understanding",
        "Let the model reason from a compact evidence pack before committing to a workflow.",
        f".\\tools\\solidworks_codex\\swctl.ps1 model-understand -Report <inspect.json> -Target \"{goal}\" -View {view}",
        "Check relevant_objects, unknowns_and_risks, spatial_model if present, and next_queries.",
    )
    step(
        "Snapshot current state",
        "Create a reproducible baseline for comparison and handoff.",
        f".\\tools\\solidworks_codex\\swctl.ps1 session-snapshot -SessionName {session_name}-before",
        "Confirm inspect/summary/manifest exist and correspond to the current open model.",
    )
    if files:
        step(
            "Back up affected files",
            "Make the work reversible before any write/save operation.",
            f".\\tools\\solidworks_codex\\swctl.ps1 backup -Files {','.join(chr(34)+f+chr(34) for f in files[:20])}",
            "Check backup report and backup-status before editing.",
        )
    else:
        step("Identify backup scope", "The report lacks file paths; ask the model/user to identify files before writes.", None, "No write should happen until source files are known.")

    if hints["dimension"]:
        command = None
        if dim_candidates:
            command = f".\\tools\\solidworks_codex\\swctl.ps1 safe-set-dimension -Model <model> -Dimension \"{dim_candidates[0]}\" -ValueM <meters>"
        step("Consider one narrow dimension edit", "Only after evidence confirms the controlling dimension and target value.", command, "Change verification should show only intended dimension deltas.")
    if hints["constraint"]:
        step("Verify exact selected references", "Constraint changes depend on selected faces/axes/edges, not just component names.", ".\\tools\\solidworks_codex\\swctl.ps1 selection-report -Out <selection.json>", "Selection report should prove the intended references before generating/running mate macros.")
    if hints["interference"] or hints["spatial"]:
        step("Validate spatial risk", "Rough bbox reasoning is not enough for final clearance/contact decisions.", ".\\tools\\solidworks_codex\\swctl.ps1 interference -Out <interference.json>", "Interpret interference with hidden/suppressed/lightweight state in mind.")

    step("Rebuild and inspect after each accepted change", "Catch rebuild failures and collect a comparable after-state.", ".\\tools\\solidworks_codex\\swctl.ps1 rebuild; .\\tools\\solidworks_codex\\swctl.ps1 inspect -Out <after.json>", "No further changes until rebuild and inspect evidence are reviewed.")
    step("Compare and decide", "Let the strong model inspect the delta instead of blindly following a fixed checklist.", ".\\tools\\solidworks_codex\\swctl.ps1 compare -Before <before.json> -After <after.json> -JsonOut <delta.json>", "Unexpected component state, path, feature, or dimension changes should stop the workflow.")

    candidate_actions.extend([
        {"tool": "model-understand", "why": "Choose a task view and expose evidence/unknowns before deciding actions.", "command": f"swctl.ps1 model-understand -Report <inspect.json> -Target \"{goal}\" -View {view}"},
        {"tool": "backup", "why": "Required before write/save operations.", "command": "swctl.ps1 backup -Files <files>"},
        {"tool": "report-search", "why": "Find exact components/features/dimensions if the evidence pack is too broad.", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"<query>\""},
        {"tool": "compare", "why": "Review actual deltas instead of assuming the edit did only one thing.", "command": "swctl.ps1 compare -Before <before.json> -After <after.json> -JsonOut <delta.json>"},
    ])
    if hints["dimension"]:
        candidate_actions.append({"tool": "safe-set-dimension", "why": "Guarded one-dimension edit when the controlling dimension is known.", "command": "swctl.ps1 safe-set-dimension -Model <model> -Dimension <full_name> -ValueM <meters>"})
    if hints["interference"] or hints["spatial"]:
        candidate_actions.append({"tool": "interference", "why": "Validate spatial/clearance claims in SolidWorks.", "command": "swctl.ps1 interference -Out <interference.json>"})

    decision_points.extend([
        {"question": "What evidence would prove the intended design change?", "if_unknown": "Gather that evidence with report-search, selection-report, inspect, or model-understand before editing."},
        {"question": "Which files can be affected by the change?", "if_unknown": "Do not save; identify and back up file scope first."},
        {"question": "Does compare show only the intended delta?", "if_unknown": "Stop, inspect the delta, and decide whether to restore backup or continue."},
    ])
    optional_branches.extend([
        {"condition": "Need exact mate/reference geometry", "branch": "Use selection-report and review selected entity types before mate-macro."},
        {"condition": "Need manufacturing feasibility", "branch": "Use model-understand -View manufacturing-holes and inspect hole/pattern dimensions before editing."},
        {"condition": "Need spatial/layout confidence", "branch": "Use model-understand -View spatial-assembly and interference check."},
        {"condition": "Need export/delivery", "branch": "Export only after rebuild and compare are accepted."},
    ])

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "document": {"title": d.get("title"), "path": d.get("path"), "type": d.get("type")},
        "requires_backup": True,
        "candidate_files": files,
        "candidate_dimensions": dim_candidates[:80],
        "candidate_components": component_candidates[:120],
        "candidate_features": feature_candidates[:120],
        "hints": hints,
        "steps": steps,
        "candidate_actions": candidate_actions,
        "decision_points": decision_points,
        "optional_branches": optional_branches,
        "planning_principle": "Flexible evidence plan: choose branches from current evidence instead of forcing a fixed domain workflow.",
    }


def md(plan: dict[str, Any]) -> str:
    lines = ["# Mechanical CAD Change Plan", ""]
    lines += [
        f"- Goal: {plan['goal']}",
        f"- Document: `{plan['document'].get('title')}`",
        f"- Path: `{plan['document'].get('path')}`",
        f"- Principle: {plan['planning_principle']}",
        "",
        "## Candidate evidence",
        f"- Files: `{len(plan['candidate_files'])}`",
        f"- Components: `{len(plan['candidate_components'])}`",
        f"- Dimensions: `{len(plan['candidate_dimensions'])}`",
        f"- Features: `{len(plan['candidate_features'])}`",
        "",
        "## Steps",
    ]
    for i, s in enumerate(plan["steps"], 1):
        lines += [f"### {i}. {s['title']}", "", f"- Purpose: {s['purpose']}", f"- Evidence to check: {s['evidence_to_check']}"]
        if s.get("command"):
            lines += ["", "```powershell", s["command"], "```"]
        lines.append("")
    lines += ["## Decision points", ""]
    lines += [f"- {d['question']} If unknown: {d['if_unknown']}" for d in plan["decision_points"]]
    lines += ["", "## Optional branches", ""]
    lines += [f"- `{b['condition']}` → {b['branch']}" for b in plan["optional_branches"]]
    lines += ["", "## Candidate actions", ""]
    for a in plan["candidate_actions"]:
        lines.append(f"- `{a['tool']}`: {a['why']} — `{a['command']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True)
    p.add_argument("--goal", required=True)
    p.add_argument("--session-name", default="cad-change")
    p.add_argument("--out", default="tools/solidworks_codex/reports/change_plan.md")
    p.add_argument("--json-out", default="tools/solidworks_codex/reports/change_plan.json")
    args = p.parse_args()
    result = make_plan(load_report(args.report), args.goal, args.session_name)
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md(result), encoding="utf-8")
    jout.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(jout), "steps": len(result["steps"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
