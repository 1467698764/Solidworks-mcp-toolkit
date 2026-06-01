"""Compare two SolidWorks Codex JSON reports and emit Markdown/JSON deltas."""
from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def active(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document")
    return doc if isinstance(doc, dict) else {}


def key_component(c: dict[str, Any]) -> str:
    return str(c.get("name2") or c.get("path") or "<unnamed>")


def key_dimension(d: dict[str, Any]) -> str:
    return str(d.get("full_name") or d.get("name") or d.get("display_name") or "<unnamed>")


def by_key(items: Any, key_fn) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    if isinstance(items, list):
        for item in items:
            if isinstance(item, dict):
                result[key_fn(item)] = item
    return result


def feature_counts(doc: dict[str, Any]) -> Counter[str]:
    counts: Counter[str] = Counter()
    for f in doc.get("features") or []:
        if isinstance(f, dict):
            counts[str(f.get("type") or "<unknown>")] += 1
    return counts


def compare(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    bdoc = active(before)
    adoc = active(after)
    delta: dict[str, Any] = {
        "document": {
            "before_title": bdoc.get("title"),
            "after_title": adoc.get("title"),
            "before_path": bdoc.get("path"),
            "after_path": adoc.get("path"),
        },
        "components": {"added": [], "removed": [], "changed": []},
        "dimensions": {"added": [], "removed": [], "changed": []},
        "features": {"before_counts": {}, "after_counts": {}, "count_changes": []},
    }

    bcomps = by_key(bdoc.get("components"), key_component)
    acomps = by_key(adoc.get("components"), key_component)
    for key in sorted(acomps.keys() - bcomps.keys()):
        delta["components"]["added"].append(acomps[key])
    for key in sorted(bcomps.keys() - acomps.keys()):
        delta["components"]["removed"].append(bcomps[key])
    for key in sorted(bcomps.keys() & acomps.keys()):
        changes = {}
        for field in ("path", "referenced_configuration", "suppressed", "hidden", "fixed", "lightweight"):
            if bcomps[key].get(field) != acomps[key].get(field):
                changes[field] = {"before": bcomps[key].get(field), "after": acomps[key].get(field)}
        if changes:
            delta["components"]["changed"].append({"key": key, "changes": changes})

    bdims = by_key(bdoc.get("dimensions"), key_dimension)
    adims = by_key(adoc.get("dimensions"), key_dimension)
    for key in sorted(adims.keys() - bdims.keys()):
        delta["dimensions"]["added"].append(adims[key])
    for key in sorted(bdims.keys() - adims.keys()):
        delta["dimensions"]["removed"].append(bdims[key])
    for key in sorted(bdims.keys() & adims.keys()):
        before_val = bdims[key].get("system_value_m")
        after_val = adims[key].get("system_value_m")
        if before_val != after_val:
            delta["dimensions"]["changed"].append({"key": key, "before_m": before_val, "after_m": after_val})

    bcounts = feature_counts(bdoc)
    acounts = feature_counts(adoc)
    delta["features"]["before_counts"] = dict(sorted(bcounts.items()))
    delta["features"]["after_counts"] = dict(sorted(acounts.items()))
    for key in sorted(set(bcounts) | set(acounts)):
        if bcounts.get(key, 0) != acounts.get(key, 0):
            delta["features"]["count_changes"].append({"type": key, "before": bcounts.get(key, 0), "after": acounts.get(key, 0)})
    return delta


def md_list(items: list[Any], formatter) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- {formatter(item)}" for item in items]


def to_markdown(delta: dict[str, Any]) -> str:
    lines = ["# SolidWorks Report Delta", ""]
    doc = delta["document"]
    lines += [
        "## Document",
        f"- Before: `{doc.get('before_title')}` — `{doc.get('before_path')}`",
        f"- After: `{doc.get('after_title')}` — `{doc.get('after_path')}`",
        "",
        "## Component changes",
        "### Added",
    ]
    lines += md_list(delta["components"]["added"], lambda c: f"`{c.get('name2')}` path=`{c.get('path')}`")
    lines += ["", "### Removed"]
    lines += md_list(delta["components"]["removed"], lambda c: f"`{c.get('name2')}` path=`{c.get('path')}`")
    lines += ["", "### Changed"]
    lines += md_list(delta["components"]["changed"], lambda c: f"`{c.get('key')}` {json.dumps(c.get('changes'), ensure_ascii=False)}")
    lines += ["", "## Dimension changes"]
    lines += md_list(delta["dimensions"]["changed"], lambda d: f"`{d.get('key')}` {d.get('before_m')} m → {d.get('after_m')} m")
    if delta["dimensions"]["added"]:
        lines += ["", "### Added dimensions"]
        lines += md_list(delta["dimensions"]["added"], lambda d: f"`{key_dimension(d)}` = {d.get('system_value_m')} m")
    if delta["dimensions"]["removed"]:
        lines += ["", "### Removed dimensions"]
        lines += md_list(delta["dimensions"]["removed"], lambda d: f"`{key_dimension(d)}`")
    lines += ["", "## Feature type count changes"]
    lines += md_list(delta["features"]["count_changes"], lambda f: f"`{f.get('type')}` {f.get('before')} → {f.get('after')}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--before", required=True)
    parser.add_argument("--after", required=True)
    parser.add_argument("--out", default="tools/solidworks_codex/reports/report_delta.md")
    parser.add_argument("--json-out", default="")
    args = parser.parse_args()

    delta = compare(load(args.before), load(args.after))
    md = to_markdown(delta)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md, encoding="utf-8")
    if args.json_out:
        jout = Path(args.json_out)
        jout.parent.mkdir(parents=True, exist_ok=True)
        jout.write_text(json.dumps(delta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
