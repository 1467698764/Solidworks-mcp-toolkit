"""Generate a generic evidence-first mechanical CAD review from an inspect report."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

DOMAIN_KEYWORDS = {
    "rotating_support": ("bearing", "bushing", "shaft", "sleeve", "spacer", "retainer", "轴承", "轴"),
    "drive_or_actuator_interface": ("motor", "servo", "actuator", "gearbox", "drive", "mount", "adapter", "电机"),
    "sensor_or_reference_alignment": ("encoder", "sensor", "probe", "reader", "datum", "magnet", "编码", "基准"),
    "plate_shell_interface": ("plate", "cover", "housing", "base", "flange", "case", "bracket", "盖板", "底板", "壳", "法兰"),
    "locating_fastening": ("bolt", "screw", "pin", "dowel", "m3", "m4", "m5", "m6", "螺", "销", "定位"),
    "manufacturing_features": ("hole", "cut", "extrude", "pattern", "pcd", "slot", "pocket", "孔", "加工", "制造"),
}


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


def text_of(item: dict[str, Any]) -> str:
    return " ".join(str(item.get(k, "")) for k in ("name2", "path", "name", "type", "full_name", "feature")).lower()


def find_domain_objects(items: list[dict[str, Any]], domain: str) -> list[str]:
    keys = DOMAIN_KEYWORDS[domain]
    result = []
    for item in items:
        text = text_of(item)
        if any(k.lower() in text for k in keys):
            result.append(name_of(item))
    return result


def finding(category: str, severity: str, title: str, evidence: list[str], interpretation: str, candidate_actions: list[str]) -> dict[str, Any]:
    return {
        "category": category,
        "severity": severity,
        "title": title,
        "evidence": evidence,
        "interpretation": interpretation,
        "candidate_actions": candidate_actions,
    }


def review(report: dict[str, Any], intent: str = "") -> dict[str, Any]:
    doc = active_doc(report)
    comps = rows(doc.get("components"))
    dims = rows(doc.get("dimensions"))
    feats = rows(doc.get("features"))
    all_objects = comps + dims + feats
    findings: list[dict[str, Any]] = []
    open_questions: list[dict[str, str]] = []
    candidate_actions: list[dict[str, str]] = []

    suppressed = [name_of(c) for c in comps if c.get("suppressed") is True]
    hidden = [name_of(c) for c in comps if c.get("hidden") is True]
    floating = [name_of(c) for c in comps if c.get("fixed") is False and c.get("suppressed") is not True]
    missing_path = [name_of(c) for c in comps if not c.get("path")]
    with_bbox = [name_of(c) for c in comps if isinstance(c.get("bbox_m"), list) and len(c.get("bbox_m")) == 6]

    if floating or suppressed or hidden:
        evidence = []
        evidence += [f"floating:{x}" for x in floating[:20]]
        evidence += [f"suppressed:{x}" for x in suppressed[:20]]
        evidence += [f"hidden:{x}" for x in hidden[:20]]
        findings.append(finding(
            "assembly_state", "medium", "Assembly state needs interpretation before edits",
            evidence,
            "Fixed/suppressed/hidden state changes what geometry and constraints are actually meaningful. Treat these as evidence, not automatic defects.",
            ["Use selection-report or live SolidWorks review to confirm intended datums and intentionally hidden/suppressed parts."],
        ))
    if missing_path:
        findings.append(finding(
            "references", "high", "Some components lack external file paths",
            missing_path[:20],
            "Missing paths may mean virtual components or unresolved references; backup/export/reproduction scope is weaker.",
            ["Resolve whether pathless components are intentional virtual parts before save/export or batch edits."],
        ))

    for domain in DOMAIN_KEYWORDS:
        evidence = find_domain_objects(all_objects, domain)
        if evidence:
            severity = "info" if domain not in {"locating_fastening", "manufacturing_features"} else "medium"
            findings.append(finding(
                domain,
                severity,
                f"Evidence found for {domain.replace('_', ' ')}",
                evidence[:30],
                "These objects are task-relevant anchors. A strong model should reason from their names, states, dimensions, features, and spatial evidence rather than from a fixed template.",
                [f"Run model-understand with a focused task or report-search for {domain.replace('_', ' ')} if more detail is needed."],
            ))

    dim_names = [name_of(d) for d in dims]
    if dim_names:
        findings.append(finding(
            "dimension_index", "info", "Editable dimension candidates are available",
            dim_names[:40],
            "Dimension names are handles for controlled changes; they do not by themselves prove design intent.",
            ["Before editing, pair the dimension with owning feature/component context and use safe-set-dimension for guarded changes."],
        ))
    if with_bbox:
        findings.append(finding(
            "spatial_evidence", "info", "Component bounding boxes are available for spatial reasoning",
            with_bbox[:30],
            "Bounding boxes can support rough proximity, stack, containment, and overlap reasoning, but exact contact/interference needs SolidWorks verification.",
            ["Use model-understand -View spatial-assembly, then interference or section-view validation for decisive geometry questions."],
        ))
    else:
        open_questions.append({"topic": "spatial_evidence", "question": "No component bounding boxes were sampled. Do not infer distances, containment, or accessibility until inspect provides bbox/transform evidence."})

    feature_counts = Counter(str(f.get("type") or "<unknown>") for f in feats)
    if feats:
        findings.append(finding(
            "feature_inventory", "info", "Feature type inventory is available",
            [f"{k}:{v}" for k, v in sorted(feature_counts.items())],
            "Feature counts can hint at modeling strategy, but detailed feature order/sketch references may still be needed.",
            ["Use report-search for feature names tied to the current task, especially holes, patterns, cuts, sketches, or mates."],
        ))

    if not any("mate" in text_of(f) for f in feats):
        open_questions.append({"topic": "constraints", "question": "No mate-like feature was sampled. Verify whether the report omitted mates, traversal limit was too low, or the model is under-constrained."})
    if intent:
        open_questions.append({"topic": "intent", "question": "Which evidence would change the decision for this intent? Ask for that evidence instead of forcing a fixed review checklist."})

    candidate_actions.extend([
        {"tool": "model-understand", "why": "Build a task-scoped context pack and let the AI reason from evidence.", "command": "swctl.ps1 model-understand -Report <inspect.json> -Target \"<task>\" -View auto"},
        {"tool": "report-search", "why": "Pull a narrower object set when names/features are noisy.", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"<query>\""},
        {"tool": "interference", "why": "Validate suspected spatial overlap or clearance risk in SolidWorks.", "command": "swctl.ps1 interference -Out <interference.json>"},
        {"tool": "backup", "why": "Create reversible state before any write/save operation.", "command": "swctl.ps1 backup -Files <files>"},
    ])

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "intent": intent,
        "document": {"title": doc.get("title"), "path": doc.get("path"), "type": doc.get("type")},
        "counts": {"components": len(comps), "dimensions": len(dims), "features": len(feats)},
        "findings": findings,
        "open_questions": open_questions,
        "candidate_actions": candidate_actions,
        "review_principle": "Evidence first; avoid fixed domain templates. Use this as context for a strong model, not as a closed checklist.",
    }


def md(data: dict[str, Any]) -> str:
    lines = ["# Mechanical CAD Evidence Review", ""]
    doc = data["document"]
    lines += [
        f"- Intent: `{data.get('intent') or '<unspecified>'}`",
        f"- Document: `{doc.get('title')}`",
        f"- Path: `{doc.get('path')}`",
        f"- Type: `{doc.get('type')}`",
        f"- Counts: `{data['counts']}`",
        f"- Principle: {data['review_principle']}",
        "",
        "## Findings",
    ]
    if data["findings"]:
        for i, f in enumerate(data["findings"], 1):
            lines += [f"### {i}. [{f['severity']}] {f['title']}", "", f"- Category: `{f['category']}`", f"- Interpretation: {f['interpretation']}"]
            if f.get("evidence"):
                lines.append("- Evidence:")
                lines += [f"  - `{e}`" for e in f["evidence"]]
            if f.get("candidate_actions"):
                lines.append("- Candidate actions:")
                lines += [f"  - {a}" for a in f["candidate_actions"]]
            lines.append("")
    else:
        lines.append("- No findings from current heuristics; gather more evidence or ask a more specific task question.")
    lines += ["## Open questions", ""]
    lines += [f"- `{q['topic']}`: {q['question']}" for q in data["open_questions"]] or ["- None from current report."]
    lines += ["", "## Candidate actions", ""]
    for a in data["candidate_actions"]:
        lines.append(f"- `{a['tool']}`: {a['why']} — `{a['command']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True)
    p.add_argument("--intent", default="")
    p.add_argument("--out", default="tools/solidworks_codex/reports/design_review.md")
    p.add_argument("--json-out", default="tools/solidworks_codex/reports/design_review.json")
    args = p.parse_args()
    result = review(load_report(args.report), args.intent)
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    jout.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    out.write_text(md(result), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(jout), "findings": len(result["findings"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
