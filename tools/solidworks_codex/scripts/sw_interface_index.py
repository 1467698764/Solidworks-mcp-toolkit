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


def planar_selector(component: str, component_path: str | None, interface_id: str, face_name: str, face: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_id": interface_id,
        "component": component,
        "component_path": component_path,
        "strategy": "stable_id_then_bbox_fallback",
        "fallback": {
            "type": "bbox_planar_face",
            "face": face_name,
            "origin_m": face["local_frame"]["origin_m"],
            "normal": face["normal"],
            "source": face["source"],
        },
        "tags": ["reopen_repair_selector", "review_before_live_selection"],
    }


def planar_face(component: str, component_path: str | None, box: list[float], axis: int, side: str) -> dict[str, Any]:
    axis_names = ("x", "y", "z")
    sign = -1.0 if side == "min" else 1.0
    center = [(box[i] + box[i + 3]) / 2.0 for i in range(3)]
    center[axis] = box[axis] if side == "min" else box[axis + 3]
    normal = [0.0, 0.0, 0.0]
    normal[axis] = sign
    tangent_axes = [i for i in range(3) if i != axis]
    u_axis = [0.0, 0.0, 0.0]
    v_axis = [0.0, 0.0, 0.0]
    u_axis[tangent_axes[0]] = 1.0
    v_axis[tangent_axes[1]] = 1.0
    face_name = f"{axis_names[axis]}_{side}"
    interface_id = f"{component}:plane:{face_name}"
    face = {
        "interface_id": f"{component}:plane:{face_name}",
        "component": component,
        "kind": "planar",
        "role": "datum_face",
        "face": face_name,
        "normal": normal,
        "local_frame": {
            "origin_m": center,
            "normal": normal,
            "u_axis": u_axis,
            "v_axis": v_axis,
        },
        "confidence": 0.45,
        "source": "axis_aligned_bbox_face",
    }
    face["selector"] = planar_selector(component, component_path, interface_id, face_name, face)
    return face


def planar_faces_for_component(component: str, component_path: str | None, box: list[float] | None) -> list[dict[str, Any]]:
    if box is None:
        return []
    return [
        planar_face(component, component_path, box, axis, side)
        for axis in range(3)
        for side in ("min", "max")
    ]


def coordinate_system_selector(component: str, component_path: str | None, coordinate_system: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_id": coordinate_system["coordinate_system_id"],
        "component": component,
        "component_path": component_path,
        "strategy": "stable_id_then_bbox_fallback",
        "fallback": {
            "type": "bbox_center_coordinate_system",
            "origin_m": coordinate_system["origin_m"],
            "axes": coordinate_system["axes"],
            "source": coordinate_system["source"],
        },
        "tags": ["reopen_repair_selector", "review_before_live_selection"],
    }


def coordinate_system_for_component(component: str, component_path: str | None, box: list[float] | None, roles: list[str]) -> dict[str, Any] | None:
    if box is None:
        return None
    size = size_from_bbox(box) or [0.0, 0.0, 0.0]
    coordinate_system = {
        "coordinate_system_id": f"{component}:csys:bbox_center",
        "component": component,
        "origin_role": "fixed_root_reference" if "fixed_root" in roles else "component_bbox_center",
        "origin_m": [(box[i] + box[i + 3]) / 2.0 for i in range(3)],
        "axes": {
            "x": [1.0, 0.0, 0.0],
            "y": [0.0, 1.0, 0.0],
            "z": [0.0, 0.0, 1.0],
        },
        "size_m": size,
        "confidence": 0.5 if "fixed_root" in roles else 0.4,
        "source": "axis_aligned_bbox",
    }
    coordinate_system["selector"] = coordinate_system_selector(component, component_path, coordinate_system)
    return coordinate_system


def overlapping_on_other_axes(a: list[float], b: list[float], axis: int) -> bool:
    for other in range(3):
        if other == axis:
            continue
        if a[other + 3] < b[other] or b[other + 3] < a[other]:
            return False
    return True


def contact_planar_interface_ids(a: str, box_a: list[float], b: str, box_b: list[float], tolerance: float) -> dict[str, str] | None:
    for axis, axis_name in enumerate(("x", "y", "z")):
        if not overlapping_on_other_axes(box_a, box_b, axis):
            continue
        if abs(box_a[axis + 3] - box_b[axis]) <= tolerance:
            return {"a": f"{a}:plane:{axis_name}_max", "b": f"{b}:plane:{axis_name}_min"}
        if abs(box_b[axis + 3] - box_a[axis]) <= tolerance:
            return {"a": f"{a}:plane:{axis_name}_min", "b": f"{b}:plane:{axis_name}_max"}
    return None


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
    contact_plane_ids: set[str] = set()
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
            item = {
                "a": min(a, b),
                "b": max(a, b),
                "gap_m": gap,
                "relation": "touching_or_overlapping_bbox" if gap == 0 else "near_bbox",
                "evidence": "axis_aligned_bbox_gap",
            }
            planar_ids = contact_planar_interface_ids(a, box_a, b, box_b, near_tolerance_m)
            if planar_ids is not None:
                item["planar_interface_ids"] = planar_ids
                item["selector_refs"] = dict(planar_ids)
                contact_plane_ids.update(planar_ids.values())
            interfaces.append(item)

    indexed_components = []
    planar_interfaces: list[dict[str, Any]] = []
    coordinate_systems: list[dict[str, Any]] = []
    for c in components:
        name = component_name(c)
        near_name, near_gap = nearest.get(name, (None, None))
        component_roles = role_hints(c, standard_re)
        component_path = c.get("path")
        coordinate_system = coordinate_system_for_component(name, component_path, boxes.get(name), component_roles)
        if coordinate_system is not None:
            coordinate_systems.append(coordinate_system)
        for face in planar_faces_for_component(name, component_path, boxes.get(name)):
            if face["interface_id"] in contact_plane_ids:
                face["role"] = "contact_face"
                face["confidence"] = 0.7
            elif "fixed_root" in component_roles and face["face"] == "z_min":
                face["role"] = "mounting_face"
                face["confidence"] = 0.6
            planar_interfaces.append(face)
        indexed_components.append({
            "component": name,
            "path": c.get("path"),
            "bbox_m": boxes.get(name),
            "size_m": size_from_bbox(boxes.get(name)),
            "role_hints": component_roles,
            "nearest_component": near_name,
            "nearest_gap_m": near_gap,
        })

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": True,
        "document": {"type": doc.get("type"), "title": doc.get("title") or doc.get("name")},
        "components": sorted(indexed_components, key=lambda item: item["component"]),
        "coordinate_systems": sorted(coordinate_systems, key=lambda item: item["coordinate_system_id"]),
        "planar_interfaces": sorted(planar_interfaces, key=lambda item: item["interface_id"]),
        "interfaces": sorted(interfaces, key=lambda item: (item["gap_m"], item["a"], item["b"])),
        "parameters": {"near_tolerance_m": near_tolerance_m, "standard_part_regex": standard_part_regex},
        "operator_notes": [
            "heuristic_bbox_only",
            "use_live_face_axis_selection_before_applying_mates",
        "standard_part_role_is_name_based_and_may_require_confirmation",
        "selectors_are_stable_ids_with_bbox_fallbacks_not_native_entity_ids",
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
