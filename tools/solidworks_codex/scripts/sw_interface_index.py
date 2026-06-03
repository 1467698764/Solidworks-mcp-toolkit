"""Build a heuristic component/interface index from a SolidWorks inspect report.

The index is deliberately evidence-scoped: it records bbox-derived proximity and
role hints, not exact CAD face/axis identities. Live face/edge selection should
refine these candidates before applying mates.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from itertools import combinations
from pathlib import Path
from typing import Any


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    return report.get("active_document") or report.get("document") or report


def component_name(item: dict[str, Any]) -> str:
    return str(item.get("name2") or item.get("name") or item.get("component") or item.get("path") or "<unnamed>")


def bbox(item: dict[str, Any]) -> list[float] | None:
    raw = item.get("bbox_m") or item.get("bbox") or item.get("bounding_box_m")
    if not isinstance(raw, list) or len(raw) != 6:
        return None
    try:
        return [float(v) for v in raw]
    except (TypeError, ValueError):
        return None


def bbox_gap(a: list[float], b: list[float]) -> float:
    gaps = []
    for axis in range(3):
        amin, amax = a[axis], a[axis + 3]
        bmin, bmax = b[axis], b[axis + 3]
        if amax < bmin:
            gaps.append(bmin - amax)
        elif bmax < amin:
            gaps.append(amin - bmax)
        else:
            gaps.append(0.0)
    return sum(g * g for g in gaps) ** 0.5


def size_from_bbox(box: list[float] | None) -> list[float] | None:
    if box is None:
        return None
    return [max(0.0, box[i + 3] - box[i]) for i in range(3)]


def role_hints(component: dict[str, Any], standard_re: re.Pattern[str]) -> list[str]:
    name = component_name(component)
    path = str(component.get("path", ""))
    hints: list[str] = []
    if component.get("fixed") is True:
        hints.append("fixed_root")
    if component.get("suppressed") is True:
        hints.append("suppressed")
    if component.get("hidden") is True:
        hints.append("hidden")
    if standard_re.search(f"{name} {path}"):
        hints.append("standard_part")
    return hints


def build_index(report: dict[str, Any], *, near_tolerance_m: float, standard_part_regex: str) -> dict[str, Any]:
    doc = active_document(report)
    components = list(doc.get("components") or [])
    standard_re = re.compile(standard_part_regex, re.IGNORECASE)
    boxes = {component_name(c): bbox(c) for c in components}

    interfaces: list[dict[str, Any]] = []
    nearest: dict[str, tuple[str | None, float | None]] = {component_name(c): (None, None) for c in components}
    for a, b in combinations([component_name(c) for c in components], 2):
        box_a = boxes.get(a)
        box_b = boxes.get(b)
        if box_a is None or box_b is None:
            continue
        gap = bbox_gap(box_a, box_b)
        for src, dst in [(a, b), (b, a)]:
            old_name, old_gap = nearest[src]
            if old_gap is None or gap < old_gap or (gap == old_gap and dst < (old_name or "")):
                nearest[src] = (dst, gap)
        if gap <= near_tolerance_m:
            interfaces.append({
                "a": min(a, b),
                "b": max(a, b),
                "gap_m": gap,
                "relation": "touching_or_overlapping_bbox" if gap == 0 else "near_bbox",
                "evidence": "axis_aligned_bbox_gap",
            })

    indexed_components = []
    for c in components:
        name = component_name(c)
        near_name, near_gap = nearest.get(name, (None, None))
        indexed_components.append({
            "component": name,
            "path": c.get("path"),
            "bbox_m": boxes.get(name),
            "size_m": size_from_bbox(boxes.get(name)),
            "role_hints": role_hints(c, standard_re),
            "nearest_component": near_name,
            "nearest_gap_m": near_gap,
        })

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": True,
        "document": {"type": doc.get("type"), "title": doc.get("title") or doc.get("name")},
        "components": sorted(indexed_components, key=lambda item: item["component"]),
        "interfaces": sorted(interfaces, key=lambda item: (item["gap_m"], item["a"], item["b"])),
        "parameters": {"near_tolerance_m": near_tolerance_m, "standard_part_regex": standard_part_regex},
        "operator_notes": [
            "heuristic_bbox_only",
            "use_live_face_axis_selection_before_applying_mates",
            "standard_part_role_is_name_based_and_may_require_confirmation",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a heuristic interface index from a SolidWorks inspect JSON report")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--near-tolerance-m", type=float, default=0.002)
    parser.add_argument("--standard-part-regex", default=r"bolt|washer|nut|screw|pin|bearing|key|retaining|oil")
    args = parser.parse_args()

    result = build_index(
        json.loads(Path(args.report).read_text(encoding="utf-8-sig")),
        near_tolerance_m=args.near_tolerance_m,
        standard_part_regex=args.standard_part_regex,
    )
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "component_count": len(result["components"]), "interface_count": len(result["interfaces"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
