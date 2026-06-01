"""Search SolidWorks Codex inspect reports for unnamed/poorly named assembly work."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[3]
KINDS = {"all", "components", "dimensions", "features"}
STATES = {"any", "suppressed", "unsuppressed", "hidden", "shown", "fixed", "floating", "lightweight"}


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


def tokens(query: str) -> list[str]:
    return [t.lower() for t in query.replace(";", " ").replace(",", " ").split() if t.strip()]


def haystack(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in item.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            parts.append(f"{key}:{value}")
        elif isinstance(value, list):
            parts.append(f"{key}:{' '.join(map(str, value[:20]))}")
    return " ".join(parts).lower()


def matches_query(item: dict[str, Any], qs: list[str]) -> bool:
    if not qs:
        return True
    h = haystack(item)
    return any(q in h for q in qs)


def matches_state_component(item: dict[str, Any], state: str) -> bool:
    if state == "any":
        return True
    if state == "suppressed":
        return item.get("suppressed") is True
    if state == "unsuppressed":
        return item.get("suppressed") is False
    if state == "hidden":
        return item.get("hidden") is True
    if state == "shown":
        return item.get("hidden") is False
    if state == "fixed":
        return item.get("fixed") is True
    if state == "floating":
        return item.get("fixed") is False and item.get("suppressed") is not True
    if state == "lightweight":
        return item.get("lightweight") is True
    return True


def rank_items(items: Iterable[dict[str, Any]], qs: list[str]) -> list[dict[str, Any]]:
    ranked = []
    for item in items:
        h = haystack(item)
        score = sum(h.count(q) for q in qs) if qs else 1
        copy = dict(item)
        copy["_score"] = score
        ranked.append(copy)
    return sorted(ranked, key=lambda x: (-x.get("_score", 0), str(x.get("name2") or x.get("full_name") or x.get("name") or "")))


def search(report: dict[str, Any], query: str, kind: str, state: str, limit: int) -> dict[str, Any]:
    doc = active_doc(report)
    qs = tokens(query)
    include_components = kind in {"all", "components"}
    include_dimensions = kind in {"all", "dimensions"}
    include_features = kind in {"all", "features"}

    comps = []
    if include_components:
        comps = [c for c in rows(doc.get("components")) if matches_query(c, qs) and matches_state_component(c, state)]
        comps = rank_items(comps, qs)[:limit]

    dims = []
    if include_dimensions and state == "any":
        dims = [d for d in rows(doc.get("dimensions")) if matches_query(d, qs)]
        dims = rank_items(dims, qs)[:limit]

    feats = []
    if include_features and state == "any":
        feats = [f for f in rows(doc.get("features")) if matches_query(f, qs)]
        feats = rank_items(feats, qs)[:limit]

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "query": query,
        "kind": kind,
        "state": state,
        "document": {"title": doc.get("title"), "path": doc.get("path"), "type": doc.get("type")},
        "counts": {"components": len(comps), "dimensions": len(dims), "features": len(feats)},
        "components": comps,
        "dimensions": dims,
        "features": feats,
    }


def md(result: dict[str, Any]) -> str:
    lines = ["# SolidWorks Report Search", ""]
    lines += [f"- Query: `{result['query'] or '<empty>'}`", f"- Kind: `{result['kind']}`", f"- State: `{result['state']}`", f"- Document: `{result['document'].get('title')}`", ""]
    lines.append("## Components")
    if result["components"]:
        for c in result["components"]:
            lines.append(f"- `{c.get('name2')}` path=`{c.get('path')}` suppressed=`{c.get('suppressed')}` hidden=`{c.get('hidden')}` fixed=`{c.get('fixed')}` score=`{c.get('_score')}`")
    else:
        lines.append("- No component matches.")
    lines += ["", "## Dimensions"]
    if result["dimensions"]:
        for d in result["dimensions"]:
            lines.append(f"- `{d.get('full_name') or d.get('display_name') or d.get('name')}` value_m=`{d.get('system_value_m')}` feature=`{d.get('feature')}` score=`{d.get('_score')}`")
    else:
        lines.append("- No dimension matches.")
    lines += ["", "## Features"]
    if result["features"]:
        for f in result["features"]:
            lines.append(f"- `{f.get('name')}` type=`{f.get('type')}` suppressed=`{f.get('suppressed')}` score=`{f.get('_score')}`")
    else:
        lines.append("- No feature matches.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--report", required=True)
    p.add_argument("--query", default="")
    p.add_argument("--kind", choices=sorted(KINDS), default="all")
    p.add_argument("--state", choices=sorted(STATES), default="any")
    p.add_argument("--limit", type=int, default=50)
    p.add_argument("--out", default="tools/solidworks_codex/reports/report_search.md")
    p.add_argument("--json-out", default="tools/solidworks_codex/reports/report_search.json")
    args = p.parse_args()
    result = search(load_report(args.report), args.query, args.kind, args.state, args.limit)
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(md(result), encoding="utf-8")
    jout.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(jout), "counts": result["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
