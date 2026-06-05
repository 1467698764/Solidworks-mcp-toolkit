"""Build a heuristic component/interface index from a SolidWorks inspect report.

The index is deliberately evidence-scoped: it records bbox-derived proximity,
role hints, and a stable native-identity envelope. Live face/edge selection can
fill persisted COM references or tracking ids into that envelope before applying
mates.
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


def rows(value: Any) -> list[dict[str, Any]]:
    return [item for item in (value or []) if isinstance(item, dict)]


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


def item_name(item: dict[str, Any]) -> str:
    return str(item.get("full_name") or item.get("name") or item.get("feature") or "")


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


def clean_vector(values: list[float]) -> list[float]:
    return [round(float(value), 12) for value in values]


def native_identity_envelope(component: str, component_path: str | None, stable_id: str, kind: str, geometry_signature: dict[str, Any]) -> dict[str, Any]:
    return {
        "stable_id": stable_id,
        "component": component,
        "component_path": component_path,
        "kind": kind,
        "persistent_reference": None,
        "tracking_id": None,
        "select_name": None,
        "geometry_signature": geometry_signature,
        "source": "interface_index_selector_signature",
        "resolution_order": ["persistent_reference", "tracking_id", "select_name", "geometry_signature_fallback"],
    }


def live_identity_capture_protocol(
    component: str,
    component_path: str | None,
    stable_id: str,
    selection_entity: str,
    geometry_signature: dict[str, Any],
) -> dict[str, Any]:
    return {
        "target_stable_id": stable_id,
        "component": component,
        "component_path": component_path,
        "selection_entity": selection_entity,
        "patch_target": "selector.native_identity",
        "capture_fields": ["persistent_reference", "tracking_id", "select_name", "geometry_signature"],
        "solidworks_calls": [
            "IModelDocExtension::SelectByID2",
            "ISelectionMgr::GetSelectedObject6",
            "IEntity::GetSafeEntity",
            "IModelDocExtension::GetPersistReference3",
            "IModelDocExtension::GetObjectByPersistReference3",
        ],
        "readback_checks": {
            "component_path": component_path,
            "geometry_signature": geometry_signature,
            "selection_entity": selection_entity,
            "stable_id": stable_id,
        },
        "failure_policy": "block_mate_execution_until_reviewed_native_identity_or_geometry_fallback_matches",
    }


def planar_selector(component: str, component_path: str | None, interface_id: str, face_name: str, face: dict[str, Any]) -> dict[str, Any]:
    geometry_signature = {
        "type": "bbox_planar_face",
        "face": face_name,
        "origin_m": face["local_frame"]["origin_m"],
        "normal": face["normal"],
        "source": face["source"],
    }
    return {
        "stable_id": interface_id,
        "component": component,
        "component_path": component_path,
        "strategy": "native_identity_then_stable_id_then_bbox_fallback",
        "native_identity": native_identity_envelope(component, component_path, interface_id, "face", geometry_signature),
        "live_identity_capture_protocol": live_identity_capture_protocol(component, component_path, interface_id, "face", geometry_signature),
        "fallback": geometry_signature,
        "tags": ["reopen_repair_selector", "review_before_live_selection", "native_identity_envelope", "capture_protocol"],
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


def confidence_level(confidence: float) -> str:
    if confidence >= 0.65:
        return "reviewable"
    if confidence >= 0.55:
        return "needs_corroboration"
    return "blocked"


def selection_policy_for_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    level = confidence_level(float(candidate.get("confidence", 0.0)))
    if level == "reviewable":
        return {
            "confidence_level": level,
            "allow_reviewed_selection": True,
            "block_automatic_selection": False,
            "required_evidence": ["operator_review", "live_face_axis_selection_before_mate"],
        }
    if level == "needs_corroboration":
        return {
            "confidence_level": level,
            "allow_reviewed_selection": False,
            "block_automatic_selection": True,
            "required_evidence": ["corroborating_feature_or_mate_evidence", "live_face_axis_selection_required"],
        }
    return {
        "confidence_level": level,
        "allow_reviewed_selection": False,
        "block_automatic_selection": True,
        "required_evidence": ["live_face_axis_selection_required"],
    }


def apply_confidence_policy(candidate: dict[str, Any]) -> dict[str, Any]:
    policy = selection_policy_for_candidate(candidate)
    candidate["confidence_level"] = policy["confidence_level"]
    candidate["selection_policy"] = policy
    return candidate


def explicit_component_refs(item: dict[str, Any]) -> list[str]:
    raw = item.get("components") or item.get("entities") or item.get("references") or item.get("component_refs")
    if isinstance(raw, list):
        return [str(value) for value in raw if str(value)]
    if isinstance(raw, str):
        return [value.strip() for value in raw.replace(";", ",").split(",") if value.strip()]
    return []


def feature_component_refs(feature: dict[str, Any], component_names: list[str]) -> list[str]:
    refs = explicit_component_refs(feature)
    text = " ".join(str(feature.get(key, "")) for key in ("name", "type", "description", "path")).lower()
    for name in component_names:
        if name.lower() in text:
            refs.append(name)
    result: list[str] = []
    seen: set[str] = set()
    for ref in refs:
        if ref not in seen:
            seen.add(ref)
            result.append(ref)
    return result


def parse_diameter_m(text: str) -> float | None:
    match = re.search(r"(?:dia|diameter|d)[_\-\s]*([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    if value <= 0:
        return None
    return value / 1000.0


def dimension_diameter_by_feature(dimensions: list[dict[str, Any]]) -> dict[str, float]:
    result: dict[str, float] = {}
    for dim in dimensions:
        name = item_name(dim)
        text = " ".join(str(dim.get(key, "")) for key in ("full_name", "name", "feature", "type")).lower()
        if not any(token in text for token in ("dia", "diameter", "直径", "bore", "shaft", "hole")):
            continue
        try:
            value = float(dim.get("system_value_m"))
        except (TypeError, ValueError):
            parsed = parse_diameter_m(name)
            if parsed is None:
                continue
            value = parsed
        if value <= 0:
            continue
        feature = str(dim.get("feature") or name.split("@")[1] if "@" in name else dim.get("feature") or "")
        if feature:
            result[feature] = value
    return result


def dimensions_by_feature(dimensions: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {}
    for dim in dimensions:
        name = item_name(dim)
        feature = str(dim.get("feature") or name.split("@")[1] if "@" in name else dim.get("feature") or "")
        if feature:
            result.setdefault(feature, []).append(dim)
    return result


def dimension_value_for_feature(dimensions: list[dict[str, Any]], tokens: tuple[str, ...]) -> float | None:
    for dim in dimensions:
        text = item_name(dim).lower()
        if not any(token in text for token in tokens):
            continue
        try:
            value = float(dim.get("system_value_m"))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def cylinder_role(feature: dict[str, Any], component: str) -> str | None:
    text = " ".join(str(feature.get(key, "")) for key in ("name", "type", "description", "kind")).lower()
    comp = component.lower()
    if any(token in text for token in ("bearing", "bore")):
        return "bearing_bore"
    if any(token in text for token in ("hole", "dowel", "pin")):
        return "hole_axis"
    if "shaft" in text or "shaft" in comp:
        return "shaft_axis"
    return None


def cylinder_axis_from_text(text: str, box: list[float] | None) -> tuple[str, list[float]]:
    lowered = text.lower()
    if re.search(r"(^|[_\-\s])x($|[_\-\s])", lowered):
        return "x", [1.0, 0.0, 0.0]
    if re.search(r"(^|[_\-\s])y($|[_\-\s])", lowered):
        return "y", [0.0, 1.0, 0.0]
    if re.search(r"(^|[_\-\s])z($|[_\-\s])", lowered):
        return "z", [0.0, 0.0, 1.0]
    if box is not None:
        sizes = size_from_bbox(box) or [0.0, 0.0, 0.0]
        axis_index = max(range(3), key=lambda index: sizes[index])
        axis_name = ("x", "y", "z")[axis_index]
        vector = [0.0, 0.0, 0.0]
        vector[axis_index] = 1.0
        return axis_name, vector
    return "z", [0.0, 0.0, 1.0]


def cylinder_selector(component: str, component_path: str | None, interface: dict[str, Any]) -> dict[str, Any]:
    geometry_signature = {
        "type": "cylindrical_axis",
        "axis": interface["axis"],
        "origin_m": interface["origin_m"],
        "radius_m": interface.get("radius_m"),
        "source_feature": interface.get("source_feature"),
        "source": interface.get("source"),
    }
    return {
        "stable_id": interface["interface_id"],
        "component": component,
        "component_path": component_path,
        "strategy": "native_identity_then_stable_id_then_feature_dimension_bbox_fallback",
        "native_identity": native_identity_envelope(component, component_path, interface["interface_id"], "face_or_axis", geometry_signature),
        "live_identity_capture_protocol": live_identity_capture_protocol(component, component_path, interface["interface_id"], "face_or_axis", geometry_signature),
        "fallback": geometry_signature,
        "tags": ["reopen_repair_selector", "review_before_live_selection", "native_identity_envelope", "capture_protocol"],
    }


def cylindrical_interfaces_for_component(
    component: dict[str, Any],
    component_names: list[str],
    features: list[dict[str, Any]],
    diameter_by_feature: dict[str, float],
    box: list[float] | None,
) -> list[dict[str, Any]]:
    name = component_name(component)
    result: list[dict[str, Any]] = []
    for feature in features:
        refs = feature_component_refs(feature, component_names)
        if name not in refs:
            continue
        role = cylinder_role(feature, name)
        if role is None:
            continue
        feature_name = item_name(feature)
        feature_text = " ".join(str(feature.get(key, "")) for key in ("name", "type", "description", "kind"))
        diameter_m = diameter_by_feature.get(feature_name) or parse_diameter_m(feature_text)
        axis_name, axis = cylinder_axis_from_text(feature_text, box)
        origin = [(box[i] + box[i + 3]) / 2.0 for i in range(3)] if box is not None else None
        interface_id = f"{name}:cylinder:{feature_name}"
        interface = {
            "interface_id": interface_id,
            "component": name,
            "kind": "cylindrical",
            "role": role,
            "axis_name": axis_name,
            "axis": axis,
            "origin_m": origin,
            "radius_m": (diameter_m / 2.0) if diameter_m is not None else None,
            "source_feature": feature_name,
            "source": "feature_dimension_name_evidence",
            "confidence": 0.68 if diameter_m is not None else 0.58,
        }
        interface["selector"] = cylinder_selector(name, component.get("path"), interface)
        result.append(apply_confidence_policy(interface))
    return result


def parse_named_mm(text: str, prefix: str) -> float | None:
    match = re.search(rf"(?:^|[_\-\s]){re.escape(prefix)}([0-9]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    return value / 1000.0 if value > 0 else None


def slot_axis_from_text(text: str, box: list[float] | None) -> tuple[str, list[float]]:
    lowered = text.lower()
    if re.search(r"(^|[_\-\s])x($|[_\-\s])", lowered):
        return "x", [1.0, 0.0, 0.0]
    if re.search(r"(^|[_\-\s])y($|[_\-\s])", lowered):
        return "y", [0.0, 1.0, 0.0]
    if re.search(r"(^|[_\-\s])z($|[_\-\s])", lowered):
        return "z", [0.0, 0.0, 1.0]
    if box is not None:
        sizes = size_from_bbox(box) or [0.0, 0.0, 0.0]
        axis_index = max(range(3), key=lambda index: sizes[index])
        axis_name = ("x", "y", "z")[axis_index]
        vector = [0.0, 0.0, 0.0]
        vector[axis_index] = 1.0
        return axis_name, vector
    return "x", [1.0, 0.0, 0.0]


def slot_role(feature: dict[str, Any]) -> str | None:
    text = " ".join(str(feature.get(key, "")) for key in ("name", "type", "description", "kind")).lower()
    if "slot" not in text and "槽" not in text:
        return None
    if any(token in text for token in ("slide", "slider", "guide", "rail")):
        return "slider_slot"
    if any(token in text for token in ("cam", "path")):
        return "cam_or_path_slot"
    return "slot_path"


def slot_selector(component: str, component_path: str | None, interface: dict[str, Any]) -> dict[str, Any]:
    geometry_signature = {
        "type": "slot_centerline",
        "path_axis": interface["path_axis"],
        "centerline_m": interface["centerline_m"],
        "width_m": interface.get("width_m"),
        "source_feature": interface.get("source_feature"),
        "source": interface.get("source"),
    }
    return {
        "stable_id": interface["interface_id"],
        "component": component,
        "component_path": component_path,
        "strategy": "native_identity_then_stable_id_then_feature_dimension_bbox_fallback",
        "native_identity": native_identity_envelope(component, component_path, interface["interface_id"], "edge_or_curve", geometry_signature),
        "live_identity_capture_protocol": live_identity_capture_protocol(component, component_path, interface["interface_id"], "edge_or_curve", geometry_signature),
        "fallback": geometry_signature,
        "tags": ["reopen_repair_selector", "review_before_live_selection", "native_identity_envelope", "capture_protocol"],
    }


def slot_path_interfaces_for_component(
    component: dict[str, Any],
    component_names: list[str],
    features: list[dict[str, Any]],
    dims_by_feature: dict[str, list[dict[str, Any]]],
    box: list[float] | None,
) -> list[dict[str, Any]]:
    name = component_name(component)
    result: list[dict[str, Any]] = []
    for feature in features:
        refs = feature_component_refs(feature, component_names)
        if name not in refs:
            continue
        role = slot_role(feature)
        if role is None:
            continue
        feature_name = item_name(feature)
        feature_text = " ".join(str(feature.get(key, "")) for key in ("name", "type", "description", "kind"))
        feature_dims = dims_by_feature.get(feature_name, [])
        width_m = dimension_value_for_feature(feature_dims, ("width", "slotwidth")) or parse_named_mm(feature_text, "w")
        length_m = dimension_value_for_feature(feature_dims, ("length", "slotlength")) or parse_named_mm(feature_text, "l")
        path_axis, path_vector = slot_axis_from_text(feature_text, box)
        axis_index = ("x", "y", "z").index(path_axis)
        center = [(box[i] + box[i + 3]) / 2.0 for i in range(3)] if box is not None else [0.0, 0.0, 0.0]
        if length_m is None and box is not None:
            length_m = max(0.0, box[axis_index + 3] - box[axis_index])
        half = (length_m or 0.0) / 2.0
        start = list(center)
        end = list(center)
        start[axis_index] -= half
        end[axis_index] += half
        interface = {
            "interface_id": f"{name}:slot:{feature_name}",
            "component": name,
            "kind": "slot_path",
            "role": role,
            "path_axis": path_axis,
            "path_vector": path_vector,
            "centerline_m": {"start": clean_vector(start), "end": clean_vector(end)},
            "width_m": width_m,
            "length_m": length_m,
            "source_feature": feature_name,
            "source": "feature_dimension_bbox_evidence",
            "confidence": 0.66 if width_m is not None and length_m is not None else 0.56,
        }
        interface["selector"] = slot_selector(name, component.get("path"), interface)
        result.append(apply_confidence_policy(interface))
    return result


def coordinate_system_selector(component: str, component_path: str | None, coordinate_system: dict[str, Any]) -> dict[str, Any]:
    geometry_signature = {
        "type": "bbox_center_coordinate_system",
        "origin_m": coordinate_system["origin_m"],
        "axes": coordinate_system["axes"],
        "source": coordinate_system["source"],
    }
    return {
        "stable_id": coordinate_system["coordinate_system_id"],
        "component": component,
        "component_path": component_path,
        "strategy": "native_identity_then_stable_id_then_bbox_fallback",
        "native_identity": native_identity_envelope(component, component_path, coordinate_system["coordinate_system_id"], "coordinate_system", geometry_signature),
        "live_identity_capture_protocol": live_identity_capture_protocol(component, component_path, coordinate_system["coordinate_system_id"], "coordinate_system", geometry_signature),
        "fallback": geometry_signature,
        "tags": ["reopen_repair_selector", "review_before_live_selection", "native_identity_envelope", "capture_protocol"],
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
    return apply_confidence_policy(coordinate_system)


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
    features = rows(doc.get("features"))
    dimensions = rows(doc.get("dimensions"))
    component_names = [component_name(c) for c in components]
    standard_re = re.compile(standard_part_regex, re.IGNORECASE)
    boxes = {component_name(c): bbox(c) for c in components}
    diameter_by_feature = dimension_diameter_by_feature(dimensions)
    dims_by_feature = dimensions_by_feature(dimensions)

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
    cylindrical_interfaces: list[dict[str, Any]] = []
    slot_path_interfaces: list[dict[str, Any]] = []
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
            apply_confidence_policy(face)
            planar_interfaces.append(face)
        cylindrical_interfaces.extend(cylindrical_interfaces_for_component(c, component_names, features, diameter_by_feature, boxes.get(name)))
        slot_path_interfaces.extend(slot_path_interfaces_for_component(c, component_names, features, dims_by_feature, boxes.get(name)))
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
        "cylindrical_interfaces": sorted(cylindrical_interfaces, key=lambda item: item["interface_id"]),
        "slot_path_interfaces": sorted(slot_path_interfaces, key=lambda item: item["interface_id"]),
        "interfaces": sorted(interfaces, key=lambda item: (item["gap_m"], item["a"], item["b"])),
        "parameters": {"near_tolerance_m": near_tolerance_m, "standard_part_regex": standard_part_regex},
        "operator_notes": [
            "heuristic_bbox_only",
            "use_live_face_axis_selection_before_applying_mates",
            "standard_part_role_is_name_based_and_may_require_confirmation",
            "selectors_carry_native_identity_envelopes_with_geometry_fallbacks",
            "selectors_publish_live_identity_capture_protocols",
            "interface_confidence_scoring_blocks_weak_bbox_only_targets",
            "named_cylindrical_interfaces_from_feature_and_dimension_evidence",
            "slot_path_interfaces_from_feature_dimension_bbox_evidence",
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
