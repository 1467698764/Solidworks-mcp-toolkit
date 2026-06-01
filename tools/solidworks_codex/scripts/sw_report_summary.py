"""Summarize SolidWorks Codex JSON inspection reports into Markdown.

Accepts reports produced by sw_com_probe.py or sw_assembly_inspect.py. It is safe for
empty/no-active-document reports and focuses on the fields useful for planning edits.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def as_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def fmt_bool(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    return str(value)


def table(headers: list[str], rows: list[list[Any]]) -> list[str]:
    if not rows:
        return []
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(c).replace("\n", " ") for c in row) + " |")
    return out


def summarize(report: dict[str, Any], source: str, component_limit: int, dimension_limit: int, feature_limit: int) -> str:
    lines: list[str] = []
    lines.append(f"# SolidWorks Inspect Summary")
    lines.append("")
    lines.append(f"Source: `{source}`")
    lines.append(f"Timestamp: `{report.get('timestamp', '')}`")
    lines.append(f"Connected: `{report.get('connected')}`")
    lines.append(f"Started by probe: `{report.get('started_by_probe')}`")
    lines.append(f"Revision: `{report.get('revision_number')}`")
    lines.append(f"Visible: `{report.get('visible')}`")

    doc = report.get("active_document")
    if not isinstance(doc, dict):
        lines.append("")
        lines.append("## Active document")
        lines.append("")
        lines.append(report.get("note") or "No active document information found.")
        return "\n".join(lines) + "\n"

    lines.append("")
    lines.append("## Active document")
    lines.append("")
    lines.extend(
        [
            f"- Title: `{doc.get('title')}`",
            f"- Path: `{doc.get('path')}`",
            f"- Type: `{doc.get('type')}` (`{doc.get('type_code')}`)",
            f"- Configuration: `{doc.get('configuration')}`",
        ]
    )

    comps = as_list(doc.get("components"))
    if comps:
        lines.append("")
        lines.append(f"## Components ({len(comps)} sampled)")
        rows = []
        for c in comps[:component_limit]:
            rows.append([
                c.get("name2"),
                c.get("referenced_configuration"),
                fmt_bool(c.get("suppressed")),
                fmt_bool(c.get("hidden")),
                fmt_bool(c.get("fixed")),
                c.get("path"),
            ])
        lines.extend(table(["Name2", "Config", "Suppressed", "Hidden", "Fixed", "Path"], rows))

        path_counter = Counter(Path(str(c.get("path") or "")).suffix.lower() for c in comps)
        lines.append("")
        lines.append("Component file types: " + ", ".join(f"`{k or '<none>'}`={v}" for k, v in path_counter.items()))

    dims = as_list(doc.get("dimensions"))
    if dims:
        lines.append("")
        lines.append(f"## Dimensions ({len(dims)} sampled)")
        rows = []
        for d in dims[:dimension_limit]:
            rows.append([
                d.get("full_name") or d.get("name") or d.get("display_name"),
                d.get("system_value_m"),
                d.get("feature"),
            ])
        lines.extend(table(["Full/name", "SystemValue m", "Feature"], rows))

    features = as_list(doc.get("features"))
    if features:
        lines.append("")
        lines.append(f"## Feature type counts ({len(features)} sampled)")
        counts = Counter(str(f.get("type")) for f in features)
        for name, count in counts.most_common(25):
            lines.append(f"- `{name}`: {count}")

        lines.append("")
        lines.append("## Feature sample")
        rows = []
        for f in features[:feature_limit]:
            rows.append([f.get("name"), f.get("type"), f.get("suppressed")])
        lines.extend(table(["Name", "Type", "Suppressed"], rows))

    mates = as_list(doc.get("mate_like_features"))
    if mates:
        lines.append("")
        lines.append(f"## Mate-like features ({len(mates)} sampled)")
        rows = [[m.get("name"), m.get("type"), m.get("suppressed")] for m in mates[:feature_limit]]
        lines.extend(table(["Name", "Type", "Suppressed"], rows))

    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("report", help="JSON report path")
    parser.add_argument("--out", default="", help="Markdown output path; default prints only")
    parser.add_argument("--component-limit", type=int, default=80)
    parser.add_argument("--dimension-limit", type=int, default=120)
    parser.add_argument("--feature-limit", type=int, default=80)
    args = parser.parse_args()

    src = Path(args.report)
    report = json.loads(src.read_text(encoding="utf-8-sig"))
    md = summarize(report, str(src), args.component_limit, args.dimension_limit, args.feature_limit)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(md, encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
