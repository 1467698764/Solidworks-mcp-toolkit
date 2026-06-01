"""Build a freeform handoff/context pack from a SolidWorks Codex inspect report.

This is intentionally not a geometry template or domain-specific workflow. It
gives the next Codex turn compact evidence, risks, anchors, gaps, and flexible
query options so a strong model can reason about the current CAD state instead
of replaying a fixed template.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_report(path: str) -> dict[str, Any]:
    return json.loads(resolve(path).read_text(encoding="utf-8-sig"))


def active_doc(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document") or {}
    return doc if isinstance(doc, dict) else {}


def rows(value: Any) -> list[dict[str, Any]]:
    return [x for x in (value or []) if isinstance(x, dict)]


def name_of(item: dict[str, Any]) -> str:
    return str(item.get("name2") or item.get("full_name") or item.get("display_name") or item.get("name") or "<unnamed>")


def build_context(report: dict[str, Any], focus: str) -> dict[str, Any]:
    doc = active_doc(report)
    components = rows(doc.get("components"))
    dimensions = rows(doc.get("dimensions"))
    features = rows(doc.get("features"))

    risks: list[dict[str, Any]] = []
    for c in components:
        n = name_of(c)
        if c.get("suppressed") is True:
            risks.append({"kind": "suppressed_component", "name": n, "why": "suppressed components can hide missing geometry, mates, or interference."})
        if c.get("hidden") is True:
            risks.append({"kind": "hidden_component", "name": n, "why": "hidden components may be skipped during visual review."})
        if not c.get("path"):
            risks.append({"kind": "missing_component_path", "name": n, "why": "empty component paths make backup and provenance weaker."})
        if c.get("fixed") is False and c.get("suppressed") is not True:
            risks.append({"kind": "floating_component", "name": n, "why": "floating components may indicate unconstrained assembly intent."})

    for d in dimensions:
        value = d.get("system_value_m")
        if value in (0, 0.0, None):
            risks.append({"kind": "suspicious_dimension", "name": name_of(d), "why": "zero or missing dimension value should be checked before modification."})

    mate_like = [f for f in features if "mate" in str(f.get("type", "")).lower() or "mate" in str(f.get("name", "")).lower()]
    if mate_like:
        risks.append({"kind": "mate_chain_present", "name": ", ".join(name_of(f) for f in mate_like[:5]), "why": "mate state is often decisive for assembly intent, spatial freedom, and downstream edits."})

    anchors: list[dict[str, Any]] = []
    for c in components[:20]:
        anchors.append({"kind": "component", "name": name_of(c), "path": c.get("path"), "state": {"suppressed": c.get("suppressed"), "hidden": c.get("hidden"), "fixed": c.get("fixed")}})
    for d in dimensions[:30]:
        anchors.append({"kind": "dimension", "name": name_of(d), "value_m": d.get("system_value_m"), "feature": d.get("feature")})
    for f in features[:30]:
        anchors.append({"kind": "feature", "name": name_of(f), "type": f.get("type"), "suppressed": f.get("suppressed")})

    has_bbox = any(isinstance(c.get("bbox_m"), list) and len(c.get("bbox_m") or []) == 6 for c in components)
    has_holes = any("hole" in (str(f.get("type", "")) + " " + str(f.get("name", ""))).lower() for f in features)
    has_mates = bool(mate_like)

    evidence_gaps: list[dict[str, Any]] = []
    if not has_bbox:
        evidence_gaps.append({"kind": "spatial_evidence", "why": "No component bounding boxes are present; spatial adjacency, stack order, and clearance reasoning will be weak."})
    if not has_mates:
        evidence_gaps.append({"kind": "constraint_evidence", "why": "No mate-like features were reported; assembly degrees of freedom and design intent need live verification."})
    if not has_holes:
        evidence_gaps.append({"kind": "manufacturing_evidence", "why": "No obvious hole/manufacturing features were reported; hole series, access, and process assumptions need targeted inspection."})
    else:
        evidence_gaps.append({"kind": "manufacturing_evidence", "why": "Manufacturing-like features exist, but inspect data does not prove tool access, tolerances, thread specs, or process feasibility."})
    if any(c.get("fixed") is False for c in components):
        evidence_gaps.append({"kind": "constraint_evidence", "why": "Floating components exist; confirm whether this is intended motion, incomplete mating, or stale assembly state."})

    next_queries = [
        {"kind": "spatial_understanding", "command": "swctl.ps1 model-understand -Report <inspect.json> -View spatial-assembly -Target \"<current concern>\"", "why": "Build a task-aware spatial evidence model before deciding what to edit."},
        {"kind": "object_search", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"<component feature dimension concern>\"", "why": "Pull only the objects relevant to the current question instead of flooding the model with unrelated report data."},
        {"kind": "evidence_review", "command": "swctl.ps1 design-review -Report <inspect.json> -Target \"<current mechanical concern>\"", "why": "Summarize verifiable risks, open questions, and candidate actions without forcing a fixed workflow."},
        {"kind": "change_planning", "command": "swctl.ps1 change-plan -Report <inspect.json> -Target \"<specific modification goal>\"", "why": "Plan a reversible one-variable-at-a-time edit only after the evidence is sufficient."},
    ]

    commands = [q["command"] for q in next_queries] + [
        "swctl.ps1 backup -Files <assembly-and-parts-before-write>",
        "swctl.ps1 rebuild; swctl.ps1 interference; swctl.ps1 compare after each narrow change",
    ]

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "focus": focus,
        "document": {"title": doc.get("title"), "path": doc.get("path"), "type": doc.get("type")},
        "inventory": {
            "component_count": len(components),
            "dimension_count": len(dimensions),
            "feature_count": len(features),
            "suppressed_components": [name_of(c) for c in components if c.get("suppressed") is True],
            "hidden_components": [name_of(c) for c in components if c.get("hidden") is True],
            "floating_components": [name_of(c) for c in components if c.get("fixed") is False and c.get("suppressed") is not True],
        },
        "risks": risks,
        "anchors": anchors,
        "evidence_gaps": evidence_gaps,
        "next_queries": next_queries,
        "recommended_commands": commands,
        "handoff_note": "Do not blindly replay templates or force a fixed output shape: use live evidence, targeted queries, reversible edits, and verification so the model can reason flexibly from the actual CAD state.",
    }


def markdown(ctx: dict[str, Any]) -> str:
    lines = ["# SolidWorks Codex Context Pack", ""]
    lines += [
        f"- Focus: `{ctx['focus'] or '<none>'}`",
        f"- Document: `{ctx['document'].get('title')}`",
        f"- Path: `{ctx['document'].get('path')}`",
        f"- Type: `{ctx['document'].get('type')}`",
        "",
        "## Handoff principle",
        ctx["handoff_note"],
        "",
        "## Inventory",
    ]
    inv = ctx["inventory"]
    lines += [
        f"- Components: `{inv['component_count']}`",
        f"- Dimensions: `{inv['dimension_count']}`",
        f"- Features: `{inv['feature_count']}`",
        f"- Suppressed components: `{', '.join(inv['suppressed_components']) or '<none>'}`",
        f"- Hidden components: `{', '.join(inv['hidden_components']) or '<none>'}`",
        f"- Floating components: `{', '.join(inv['floating_components']) or '<none>'}`",
        "",
        "## Risks / things to verify",
    ]
    if ctx["risks"]:
        for r in ctx["risks"]:
            lines.append(f"- `{r['kind']}` `{r['name']}` — {r['why']}")
    else:
        lines.append("- No obvious report-level risks found; still verify live SolidWorks state.")
    lines += ["", "## Evidence gaps"]
    if ctx.get("evidence_gaps"):
        for g in ctx["evidence_gaps"]:
            lines.append(f"- `{g['kind']}` - {g['why']}")
    else:
        lines.append("- No obvious report-level evidence gaps found; still verify live SolidWorks state.")
    lines += ["", "## Useful anchors"]
    for a in ctx["anchors"]:
        if a["kind"] == "dimension":
            lines.append(f"- dimension `{a['name']}` value_m=`{a.get('value_m')}` feature=`{a.get('feature')}`")
        elif a["kind"] == "component":
            state = a.get("state") or {}
            lines.append(f"- component `{a['name']}` path=`{a.get('path')}` suppressed=`{state.get('suppressed')}` hidden=`{state.get('hidden')}` fixed=`{state.get('fixed')}`")
        else:
            lines.append(f"- feature `{a['name']}` type=`{a.get('type')}` suppressed=`{a.get('suppressed')}`")
    lines += ["", "## Flexible next queries"]
    for q in ctx.get("next_queries", []):
        lines.append(f"- `{q['kind']}`: `{q['command']}` - {q['why']}")
    lines += ["", "## Suggested next commands"]
    lines += [f"- `{cmd}`" for cmd in ctx["recommended_commands"]]
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--focus", default="")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/report_context.md")
    parser.add_argument("--json-out", default="tools/solidworks_codex/reports/report_context.json")
    args = parser.parse_args()
    ctx = build_context(load_report(args.report), args.focus)
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(ctx), encoding="utf-8")
    jout.write_text(json.dumps(ctx, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(jout), "risks": len(ctx["risks"]), "anchors": len(ctx["anchors"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
