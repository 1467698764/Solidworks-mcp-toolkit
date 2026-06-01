"""Generate a practical issue report from SolidWorks Codex inspect JSON."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def doc(report: dict[str, Any]) -> dict[str, Any]:
    value = report.get("active_document")
    return value if isinstance(value, dict) else {}


def rows_table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return ["_None_", ""]
    lines = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        lines.append("| " + " | ".join(str(x).replace("\n", " ") for x in row) + " |")
    lines.append("")
    return lines


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    d = doc(report)
    comps = [c for c in d.get("components") or [] if isinstance(c, dict)]
    dims = [x for x in d.get("dimensions") or [] if isinstance(x, dict)]
    feats = [f for f in d.get("features") or [] if isinstance(f, dict)]
    mates = [m for m in d.get("mate_like_features") or [] if isinstance(m, dict)]

    suppressed = [c for c in comps if c.get("suppressed") is True]
    hidden = [c for c in comps if c.get("hidden") is True]
    fixed = [c for c in comps if c.get("fixed") is True]
    missing_path = [c for c in comps if not c.get("path")]
    lightweight = [c for c in comps if c.get("lightweight") is True]
    zero_dims = [x for x in dims if x.get("system_value_m") in (0, 0.0)]
    unnamed_dims = [x for x in dims if not (x.get("full_name") or x.get("name") or x.get("display_name"))]
    feature_counts = Counter(str(f.get("type") or "<unknown>") for f in feats)

    recommendations = []
    if missing_path:
        recommendations.append("Some components have empty paths; verify virtual components or missing references before batch edits.")
    if suppressed:
        recommendations.append("Suppressed components exist; confirm they are intentionally excluded before mass/interference/export checks.")
    if hidden:
        recommendations.append("Hidden components exist; include visibility state in screenshots and review before diagnosing clearances.")
    if fixed:
        recommendations.append("Fixed components exist; for mate troubleshooting, check whether fixed state hides under-defined relationships.")
    if lightweight:
        recommendations.append("Lightweight components exist; resolve them before detailed geometry/mate/interference checks if results look incomplete.")
    if zero_dims:
        recommendations.append("Zero-valued dimensions found; inspect whether they are construction dimensions, suppressed features, or modeling mistakes.")
    if not mates and d.get("type") == "assembly":
        recommendations.append("No mate-like features sampled; inspect feature traversal limits or mate folder state before assuming no mates.")
    if not recommendations:
        recommendations.append("No obvious structural issue was detected by offline heuristics; proceed with targeted inspect, rebuild, and interference checks.")

    return {
        "title": d.get("title"),
        "path": d.get("path"),
        "type": d.get("type"),
        "component_count": len(comps),
        "dimension_count": len(dims),
        "feature_count": len(feats),
        "mate_like_count": len(mates),
        "suppressed": suppressed,
        "hidden": hidden,
        "fixed": fixed,
        "missing_path": missing_path,
        "lightweight": lightweight,
        "zero_dims": zero_dims,
        "unnamed_dims": unnamed_dims,
        "feature_counts": dict(feature_counts.most_common(30)),
        "recommendations": recommendations,
    }


def md(analysis: dict[str, Any]) -> str:
    lines = ["# SolidWorks Issue Report", ""]
    lines += [
        f"- Title: `{analysis.get('title')}`",
        f"- Path: `{analysis.get('path')}`",
        f"- Type: `{analysis.get('type')}`",
        f"- Components sampled: `{analysis.get('component_count')}`",
        f"- Dimensions sampled: `{analysis.get('dimension_count')}`",
        f"- Features sampled: `{analysis.get('feature_count')}`",
        f"- Mate-like features sampled: `{analysis.get('mate_like_count')}`",
        "",
    ]
    for key, title in [("missing_path", "Components with empty paths"), ("suppressed", "Suppressed components"), ("hidden", "Hidden components"), ("fixed", "Fixed components"), ("lightweight", "Lightweight components")]:
        lines += [f"## {title}"]
        rows = [[c.get("name2"), c.get("path"), c.get("suppressed"), c.get("hidden"), c.get("fixed")] for c in analysis.get(key, [])[:100]]
        lines += rows_table(["Name2", "Path", "Suppressed", "Hidden", "Fixed"], rows)
    lines += ["## Zero-valued dimensions"]
    lines += rows_table(["Name", "Value m", "Feature"], [[d.get("full_name") or d.get("name"), d.get("system_value_m"), d.get("feature")] for d in analysis.get("zero_dims", [])[:100]])
    lines += ["## Feature type counts"]
    for name, count in analysis.get("feature_counts", {}).items():
        lines.append(f"- `{name}`: {count}")
    lines += ["", "## Recommendations"]
    for item in analysis.get("recommendations", []):
        lines.append(f"- {item}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", default="tools/solidworks_codex/reports/issue_report.md")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()
    analysis = analyze(load(args.report))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md(analysis), encoding="utf-8")
    if args.json_out:
        jout = Path(args.json_out)
        jout.parent.mkdir(parents=True, exist_ok=True)
        jout.write_text(json.dumps(analysis, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md(analysis))


if __name__ == "__main__":
    main()
