"""Build a task-scoped SolidWorks model understanding pack.

This is an AI context-shaping layer, not another raw dump. It turns an inspect
report into compact facts, relevant objects, relationship hypotheses, risks,
and next queries so an AI can understand the current CAD project before acting.
"""
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime
from pathlib import Path
import math
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

DOMAIN_KEYWORDS = {
    "rotating_support": ("bearing", "轴承", "bushing", "shaft", "轴", "sleeve", "spacer", "retainer"),
    "drive_or_actuator_interface": ("motor", "电机", "servo", "actuator", "gearbox", "drive", "mount", "adapter"),
    "sensor_or_reference_alignment": ("encoder", "编码", "sensor", "probe", "magnet", "reader", "datum", "基准"),
    "plate_shell_interface": ("flange", "法兰", "output", "输出", "plate", "cover", "housing", "base", "壳", "盖板", "底板", "盘"),
    "locating_fastening": ("screw", "bolt", "pin", "dowel", "m3", "m4", "m5", "m6", "螺", "销", "定位"),
    "manufacturing_features": ("hole", "孔", "cut", "extrude", "pattern", "pcd", "加工", "制造"),
    "mates_constraints": ("mate", "constraint", "concentric", "coincident", "配合", "约束"),
    "mass_clearance": ("mass", "weight", "interference", "clearance", "干涉", "间隙", "重量"),
}

VIEWS = {"auto", "general", "dimension-edit", "assembly-constraints", "interference-clearance", "manufacturing-holes", "spatial-assembly"}

VIEW_MODELS = {
    "general": {
        "primary_object_kind": "mixed",
        "focus_fields": ["name", "path", "suppressed", "hidden", "fixed", "system_value_m", "feature", "type"],
        "purpose": "Compact whole-model orientation without dumping the raw inspect report.",
    },
    "dimension-edit": {
        "primary_object_kind": "dimension",
        "focus_fields": ["full_name", "system_value_m", "feature", "document path", "backup target", "compare delta"],
        "purpose": "Prepare an AI to choose one dimension, edit it safely, rebuild, compare, and verify only intended changes.",
    },
    "assembly-constraints": {
        "primary_object_kind": "component",
        "focus_fields": ["name2", "path", "suppressed", "hidden", "fixed", "lightweight", "mate-like features"],
        "purpose": "Explain assembly grounding, suppression, visibility, and mate intent before changing component states or mates.",
    },
    "interference-clearance": {
        "primary_object_kind": "component",
        "focus_fields": ["component state", "support/drive/sensor objects", "mate-like features", "interference check", "mass properties"],
        "purpose": "Focus on nearby components and clearance-sensitive relationships before geometry edits.",
    },
    "manufacturing-holes": {
        "primary_object_kind": "mixed",
        "focus_fields": ["hole/fastener features", "PCD-related dimensions", "feature type counts", "manufacturing risks"],
        "purpose": "Focus on holes, fasteners, flange/plate features, and dimensions that drive manufacturability.",
    },
    "spatial-assembly": {
        "primary_object_kind": "component",
        "focus_fields": ["bbox_m", "center_m", "size_m", "pairwise gaps", "overlap", "missing spatial evidence"],
        "purpose": "Ground AI reasoning in spatial evidence: component extents, centers, rough proximity, overlaps, and absent geometry evidence.",
    },
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


def explicit_component_refs(feature: dict[str, Any]) -> list[str]:
    explicit = feature.get("components") or feature.get("entities") or feature.get("references")
    found: list[str] = []
    if isinstance(explicit, list):
        found.extend(str(x) for x in explicit if str(x))
    elif isinstance(explicit, str):
        found.extend(x.strip() for x in explicit.replace(";", ",").split(",") if x.strip())
    deduped: list[str] = []
    seen: set[str] = set()
    for item in found:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def feature_rows_with_mates(doc: dict[str, Any]) -> list[dict[str, Any]]:
    """Return feature evidence with explicit assembly mate readback included.

    SolidWorks inspect reports expose ordinary feature tree rows under
    ``features`` and also expose a curated ``mate_like_features`` list with
    mate participant readback.  Earlier model-understand logic only consumed
    ``features``.  That made the "model space relationship understanding" view
    miss the most reliable mate evidence on real assemblies where the mate
    folder was summarized separately.  Keep both streams, dedupe by name/type,
    and mark the source so downstream graph evidence can prefer live mate
    participant readback over name inference.
    """
    result: list[dict[str, Any]] = []
    index_by_key: dict[tuple[str, str], int] = {}
    for source_name, source_rows in (("features", rows(doc.get("features"))), ("mate_like_features", rows(doc.get("mate_like_features")))):
        for item in source_rows:
            copied = dict(item)
            copied.setdefault("source", source_name)
            key = (name_of(copied), str(copied.get("type") or ""))
            existing_index = index_by_key.get(key)
            if existing_index is not None:
                existing = result[existing_index]
                existing_refs = explicit_component_refs(existing)
                copied_refs = explicit_component_refs(copied)
                if source_name == "mate_like_features" and len(copied_refs) > len(existing_refs):
                    result[existing_index] = copied
                continue
            index_by_key[key] = len(result)
            result.append(copied)
    return result


def name_of(item: dict[str, Any]) -> str:
    return str(item.get("name2") or item.get("full_name") or item.get("display_name") or item.get("name") or "<unnamed>")


def text_of(item: dict[str, Any]) -> str:
    parts: list[str] = []
    for key, value in item.items():
        if isinstance(value, (str, int, float, bool)) or value is None:
            parts.append(f"{key}:{value}")
        elif isinstance(value, list):
            parts.append(" ".join(map(str, value[:10])))
        elif isinstance(value, dict):
            parts.append(" ".join(f"{k}:{v}" for k, v in list(value.items())[:10]))
    return " ".join(parts).lower()


def task_tokens(task: str) -> list[str]:
    cleaned = task.replace(",", " ").replace(";", " ").replace("，", " ").replace("/", " ")
    return [t.lower() for t in cleaned.split() if t.strip()]


def resolve_view(requested: str, task: str) -> str:
    view = (requested or "auto").strip().lower()
    if view not in VIEWS:
        raise ValueError(f"Unsupported view: {requested}. Choose one of: {', '.join(sorted(VIEWS))}")
    if view != "auto":
        return view
    t = task.lower()
    if any(k in t for k in ("空间", "位置", "坐标", "包围", "距离", "相对", "可行性", "spatial", "position", "bbox")):
        return "spatial-assembly"
    if any(k in t for k in ("孔", "螺", "销", "定位", "加工", "制造", "bolt", "screw", "hole", "pin", "dowel", "pcd")):
        return "manufacturing-holes"
    if any(k in t for k in ("干涉", "间隙", "clearance", "interference", "碰撞")):
        return "interference-clearance"
    if any(k in t for k in ("尺寸", "厚度", "diameter", "width", "height", "length", "dimension", "改到", "修改")):
        return "dimension-edit"
    if any(k in t for k in ("约束", "配合", "固定", "浮动", "mate", "constraint", "装配")):
        return "assembly-constraints"
    return "general"


def detect_domains(task: str, components: list[dict[str, Any]], dimensions: list[dict[str, Any]], features: list[dict[str, Any]]) -> list[dict[str, Any]]:
    corpus = " ".join([task.lower()] + [text_of(x) for x in components + dimensions + features])
    task_lower = task.lower()
    result: list[dict[str, Any]] = []
    for domain, keys in DOMAIN_KEYWORDS.items():
        hits = [k for k in keys if k.lower() in corpus]
        task_hits = [k for k in keys if k.lower() in task_lower]
        if hits:
            result.append({
                "domain": domain,
                "task_mentioned": bool(task_hits),
                "evidence_keywords": sorted(set(hits), key=str.lower)[:8],
                "why": DOMAIN_WHY.get(domain, "Relevant to the requested CAD understanding task."),
            })
    return sorted(result, key=lambda d: (not d["task_mentioned"], d["domain"]))


DOMAIN_WHY = {
    "rotating_support": "Rotating/support parts often define shaft support, fits, axial stack, and clearance constraints.",
    "drive_or_actuator_interface": "Drive or actuator interfaces often define fixed datums, torque paths, and mounting constraints.",
    "sensor_or_reference_alignment": "Sensors or datum references are sensitive to alignment, air gap, orientation, and repeatability.",
    "plate_shell_interface": "Plates, covers, housings, and interface faces often carry load paths, sealing faces, hole patterns, and stack thickness.",
    "locating_fastening": "Pins, dowels, screws, and bolts constrain assembly order, repeatability, and serviceability.",
    "manufacturing_features": "Hole, cut, extrude, and pattern features are central to manufacturability and inspection planning.",
    "mates_constraints": "Mates reveal assembly intent and whether components are properly constrained.",
    "mass_clearance": "Mass and clearance decide whether the design is feasible after geometry changes.",
}


def object_kind(item: dict[str, Any], fallback: str) -> str:
    if "name2" in item:
        return "component"
    if "system_value_m" in item or "full_name" in item:
        return "dimension"
    if "type" in item:
        return "feature"
    return fallback


def score_object(item: dict[str, Any], domains: list[dict[str, Any]], tokens: list[str]) -> tuple[int, list[str]]:
    text = text_of(item)
    reasons: list[str] = []
    score = 0
    for t in tokens:
        if t and t in text:
            score += 5
            reasons.append(f"task token `{t}` matched")
    for d in domains:
        for kw in d["evidence_keywords"]:
            if kw.lower() in text:
                score += 4 if d["task_mentioned"] else 2
                reasons.append(f"{d['domain']} keyword `{kw}` matched")
                break
    if item.get("suppressed") is True:
        score += 3
        reasons.append("suppressed state affects interpretation")
    if item.get("fixed") is False and item.get("suppressed") is not True:
        score += 2
        reasons.append("floating component affects assembly intent")
    if item.get("hidden") is True:
        score += 2
        reasons.append("hidden component may affect visual review")
    if not item.get("path") and "name2" in item:
        score += 2
        reasons.append("missing component path weakens provenance")
    return score, sorted(set(reasons))[:4]


def view_boost(kind: str, item: dict[str, Any], view: str) -> tuple[int, list[str]]:
    text = text_of(item)
    if view == "dimension-edit":
        if kind == "dimension":
            return 20, ["dimension-edit view prioritizes editable dimensions"]
        if kind == "component" and any(k in text for k in ("flange", "法兰", "plate", "output", "输出")):
            return 6, ["dimension-edit view keeps likely owning component context"]
    if view == "assembly-constraints":
        if kind == "component":
            return 12, ["assembly-constraints view prioritizes component state"]
        if kind == "feature" and "mate" in text:
            return 16, ["assembly-constraints view prioritizes mate-like features"]
    if view == "interference-clearance":
        if kind == "component":
            return 12, ["interference-clearance view prioritizes nearby component candidates"]
        if kind == "feature" and "mate" in text:
            return 6, ["mate-like feature can affect clearance interpretation"]
    if view == "spatial-assembly":
        if kind == "component":
            return 18, ["spatial-assembly view prioritizes component extents and relative placement"]
        if kind == "feature" and "mate" in text:
            return 8, ["mate-like feature explains intended spatial relationship"]
    if view == "manufacturing-holes":
        if any(k in text for k in ("hole", "孔", "bolt", "screw", "螺", "cut", "flange", "plate")):
            return 12, ["manufacturing-holes view prioritizes hole/fastener/plate evidence"]
    return 0, []


def kind_priority(kind: str, view: str) -> int:
    table = {
        "dimension-edit": {"dimension": 0, "component": 1, "feature": 2},
        "assembly-constraints": {"component": 0, "feature": 1, "dimension": 2},
        "interference-clearance": {"component": 0, "feature": 1, "dimension": 2},
        "spatial-assembly": {"component": 0, "feature": 1, "dimension": 2},
        "manufacturing-holes": {"feature": 0, "dimension": 1, "component": 2},
    }
    return table.get(view, {}).get(kind, 3)


def relevant_objects(components: list[dict[str, Any]], dimensions: list[dict[str, Any]], features: list[dict[str, Any]], domains: list[dict[str, Any]], task: str, limit: int, view: str) -> list[dict[str, Any]]:
    tokens = task_tokens(task)
    candidates: list[dict[str, Any]] = []
    for source, fallback in ((components, "component"), (dimensions, "dimension"), (features, "feature")):
        for item in source:
            score, reasons = score_object(item, domains, tokens)
            kind = object_kind(item, fallback)
            boost, boost_reasons = view_boost(kind, item, view)
            score += boost
            reasons.extend(boost_reasons)
            if score <= 0:
                continue
            entry: dict[str, Any] = {
                "kind": kind,
                "name": name_of(item),
                "score": score,
                "why_relevant": reasons,
            }
            if kind == "component":
                entry.update({"path": item.get("path"), "state": {"suppressed": item.get("suppressed"), "hidden": item.get("hidden"), "fixed": item.get("fixed"), "lightweight": item.get("lightweight")}})
            elif kind == "dimension":
                entry.update({"value_m": item.get("system_value_m"), "feature": item.get("feature")})
            elif kind == "feature":
                entry.update({"type": item.get("type"), "suppressed": item.get("suppressed")})
            candidates.append(entry)
    candidates.sort(key=lambda x: (kind_priority(str(x.get("kind", "")), view), -int(x.get("score", 0)), x.get("name", "")))
    return candidates[:limit]


def compact_anchors(components: list[dict[str, Any]], dimensions: list[dict[str, Any]], features: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    anchors: list[dict[str, Any]] = []
    for c in components:
        if c.get("fixed") is True or c.get("suppressed") is True or c.get("hidden") is True or len(anchors) < 5:
            anchors.append({"kind": "component", "name": name_of(c), "state": {"suppressed": c.get("suppressed"), "hidden": c.get("hidden"), "fixed": c.get("fixed")}, "path": c.get("path")})
        if len(anchors) >= limit:
            return anchors
    for d in dimensions:
        anchors.append({"kind": "dimension", "name": name_of(d), "value_m": d.get("system_value_m"), "feature": d.get("feature")})
        if len(anchors) >= limit:
            return anchors
    for f in features:
        anchors.append({"kind": "feature", "name": name_of(f), "type": f.get("type")})
        if len(anchors) >= limit:
            return anchors
    return anchors


def risks_and_unknowns(components: list[dict[str, Any]], dimensions: list[dict[str, Any]], features: list[dict[str, Any]], domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for c in components:
        n = name_of(c)
        if c.get("suppressed") is True:
            items.append({"kind": "risk", "object": n, "issue": "component is suppressed", "impact": "geometry/mates may be intentionally absent or temporarily hidden from analysis"})
        if c.get("fixed") is False and c.get("suppressed") is not True:
            items.append({"kind": "risk", "object": n, "issue": "component is floating", "impact": "assembly intent may be under-constrained"})
        if not c.get("path"):
            items.append({"kind": "unknown", "object": n, "issue": "component path is missing", "impact": "cannot prove provenance or backup target from this report"})
    for d in dimensions:
        if d.get("system_value_m") in (None, 0, 0.0):
            items.append({"kind": "risk", "object": name_of(d), "issue": "dimension value is zero or missing", "impact": "do not infer physical size without live verification"})
    if features and not any("mate" in text_of(f) for f in features):
        items.append({"kind": "unknown", "object": "mates", "issue": "no mate-like feature sampled", "impact": "assembly constraint understanding may be incomplete"})
    if components and not any(parse_bbox(c) is not None for c in components):
        items.append({"kind": "unknown", "object": "spatial_evidence", "issue": "no component bounding boxes were sampled", "impact": "AI can discuss names/states, but cannot prove spatial layout, proximity, or containment from this report"})
    return items[:20]


def relationship_hypotheses(components: list[dict[str, Any]], features: list[dict[str, Any]], domains: list[dict[str, Any]]) -> list[dict[str, Any]]:
    names = [name_of(c) for c in components]
    text_names = " ".join(names).lower()
    result: list[dict[str, Any]] = []
    support_names = [n for n in names if any(k in n.lower() for k in ("bearing", "bushing", "shaft", "sleeve", "轴承", "轴"))]
    drive_names = [n for n in names if any(k in n.lower() for k in ("motor", "servo", "actuator", "gearbox", "drive", "电机"))]
    sensor_names = [n for n in names if any(k in n.lower() for k in ("encoder", "sensor", "probe", "reader", "编码"))]
    if drive_names:
        result.append({"hypothesis": "drive/actuator component may be part of a fixed reference or torque path", "evidence": drive_names[:5], "confidence": "medium"})
    if support_names:
        result.append({"hypothesis": "support/shaft-like components may constrain axis, fits, or axial stack", "evidence": support_names[:5], "confidence": "medium"})
    if sensor_names:
        result.append({"hypothesis": "sensor/reference component may require alignment, gap, or orientation checks", "evidence": sensor_names[:5], "confidence": "medium"})
    mate_features = [name_of(f) for f in features if "mate" in text_of(f)]
    if mate_features:
        result.append({"hypothesis": "mate-like features exist and should be treated as the primary assembly intent source", "evidence": mate_features[:5], "confidence": "high"})
    if not result:
        result.append({"hypothesis": "functional relationships cannot be inferred strongly from names alone", "evidence": [], "confidence": "low"})
    return result


def parse_bbox(item: dict[str, Any]) -> list[float] | None:
    raw = item.get("bbox_m") or item.get("bounding_box_m") or item.get("box_m")
    if not isinstance(raw, list) or len(raw) != 6:
        return None
    try:
        vals = [float(x) for x in raw]
    except (TypeError, ValueError):
        return None
    if vals[0] > vals[3] or vals[1] > vals[4] or vals[2] > vals[5]:
        return None
    return vals


def parse_transform_array(item: dict[str, Any]) -> list[float] | None:
    raw = item.get("transform_array") or item.get("transform_m") or item.get("transform")
    if isinstance(raw, dict) and all(k in raw for k in ("array", "origin_m", "local_axes")):
        raw = raw.get("array")
    if isinstance(raw, dict):
        raw = raw.get("array") or raw.get("array_data")
    if not isinstance(raw, list) or len(raw) < 12:
        return None
    try:
        return [float(x) for x in raw[:16]]
    except (TypeError, ValueError):
        return None


def transform_struct(item: dict[str, Any]) -> dict[str, Any] | None:
    arr = parse_transform_array(item)
    if arr is None:
        return None
    # SolidWorks MathTransform.ArrayData convention exposes 3 basis vectors
    # followed by translation. Keep this as evidence, not a final kinematic
    # proof, because exact interpretation should be verified against live API.
    return {
        "array": arr,
        "origin_m": [arr[9], arr[10], arr[11]],
        "local_axes": {
            "x": [arr[0], arr[1], arr[2]],
            "y": [arr[3], arr[4], arr[5]],
            "z": [arr[6], arr[7], arr[8]],
        },
        "scale": arr[12] if len(arr) > 12 else None,
    }


def bbox_center(box: list[float]) -> list[float]:
    return [(box[0] + box[3]) / 2.0, (box[1] + box[4]) / 2.0, (box[2] + box[5]) / 2.0]


def bbox_size(box: list[float]) -> list[float]:
    return [box[3] - box[0], box[4] - box[1], box[5] - box[2]]


def axis_gap(a_min: float, a_max: float, b_min: float, b_max: float) -> float:
    if a_max < b_min:
        return b_min - a_max
    if b_max < a_min:
        return a_min - b_max
    return -min(a_max, b_max) + max(a_min, b_min)


def pair_relation(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    abox = a["bbox_m"]
    bbox = b["bbox_m"]
    gaps = [
        axis_gap(abox[0], abox[3], bbox[0], bbox[3]),
        axis_gap(abox[1], abox[4], bbox[1], bbox[4]),
        axis_gap(abox[2], abox[5], bbox[2], bbox[5]),
    ]
    separated = [g for g in gaps if g > 0]
    if separated:
        gap = max(separated)
        relation = "near" if gap <= 0.002 else "separated"
    else:
        gap = max(gaps)
        relation = "overlap"
    ac = a["center_m"]
    bc = b["center_m"]
    center_delta = [bc[i] - ac[i] for i in range(3)]
    center_distance = sum(x * x for x in center_delta) ** 0.5
    return {
        "a": a["name"],
        "b": b["name"],
        "relation": relation,
        "gap_m": gap,
        "axis_gaps_m": {"x": gaps[0], "y": gaps[1], "z": gaps[2]},
        "center_delta_m": center_delta,
        "center_distance_m": center_distance,
    }


def dominant_axis_for_components(items: list[dict[str, Any]]) -> str:
    if not items:
        return "z"
    mins = [min(c["bbox_m"][i] for c in items) for i in range(3)]
    maxs = [max(c["bbox_m"][i + 3] for c in items) for i in range(3)]
    spans = [maxs[i] - mins[i] for i in range(3)]
    return ["x", "y", "z"][max(range(3), key=lambda i: spans[i])]


def axis_stack(items: list[dict[str, Any]], axis: str) -> list[dict[str, Any]]:
    idx = {"x": 0, "y": 1, "z": 2}[axis]
    result = []
    for c in items:
        box = c["bbox_m"]
        result.append({
            "name": c["name"],
            "axis": axis,
            "min_m": box[idx],
            "center_m": c["center_m"][idx],
            "max_m": box[idx + 3],
            "size_along_axis_m": c["size_m"][idx],
        })
    return sorted(result, key=lambda x: (x["center_m"], x["name"]))


def radial_center_distance(a: dict[str, Any], b: dict[str, Any], axis: str) -> float:
    axes = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}[axis]
    return sum((a["center_m"][i] - b["center_m"][i]) ** 2 for i in axes) ** 0.5


def radial_size(c: dict[str, Any], axis: str) -> float:
    axes = {"x": (1, 2), "y": (0, 2), "z": (0, 1)}[axis]
    return max(c["size_m"][i] for i in axes)


def infer_coaxial_candidates(items: list[dict[str, Any]], axis: str) -> list[dict[str, Any]]:
    pairs = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            first, second = sorted((a, b), key=lambda x: (0 if any(k in x["name"].lower() for k in ("bearing", "bushing", "shaft", "encoder", "sensor", "motor", "gearbox", "pin", "dowel")) else 1, x["name"]))
            dist = radial_center_distance(a, b, axis)
            tolerance = max(0.0015, min(radial_size(a, axis), radial_size(b, axis)) * 0.25)
            if dist <= tolerance:
                pairs.append({
                    "a": first["name"],
                    "b": second["name"],
                    "axis": axis,
                    "radial_center_distance_m": dist,
                    "tolerance_m": tolerance,
                    "confidence": "medium" if dist > 1e-6 else "high",
                })
    return sorted(pairs, key=lambda p: (p["radial_center_distance_m"], p["a"], p["b"]))


def contains_bbox(container: list[float], inside: list[float], tolerance: float = 1e-9) -> bool:
    return (
        container[0] <= inside[0] + tolerance
        and container[1] <= inside[1] + tolerance
        and container[2] <= inside[2] + tolerance
        and container[3] >= inside[3] - tolerance
        and container[4] >= inside[4] - tolerance
        and container[5] >= inside[5] - tolerance
    )


def infer_containment_relations(items: list[dict[str, Any]], axis: str) -> list[dict[str, Any]]:
    result = []
    for a in items:
        for b in items:
            if a["name"] == b["name"]:
                continue
            if contains_bbox(a["bbox_m"], b["bbox_m"]):
                result.append({"container": a["name"], "inside": b["name"], "confidence": "bbox_contains"})
                continue
            idx = {"x": 0, "y": 1, "z": 2}[axis]
            radial_dist = radial_center_distance(a, b, axis)
            radial_tol = max(0.0015, min(radial_size(a, axis), radial_size(b, axis)) * 0.25)
            axis_spans = a["bbox_m"][idx] <= b["bbox_m"][idx] and a["bbox_m"][idx + 3] >= b["bbox_m"][idx + 3]
            a_slender = radial_size(a, axis) < radial_size(b, axis) * 0.75
            if axis_spans and a_slender and radial_dist <= radial_tol:
                result.append({"container": a["name"], "inside": b["name"], "confidence": "axis_passes_through"})
    return sorted(result, key=lambda x: (x["container"], x["inside"]))


def feature_text(feature: dict[str, Any]) -> str:
    return f"{feature.get('name', '')} {feature.get('type', '')}".lower()


def infer_mate_type(feature: dict[str, Any]) -> str:
    text = feature_text(feature)
    for kind in ("concentric", "coincident", "parallel", "perpendicular", "tangent", "distance", "angle", "width", "symmetry", "cam", "cam_follower", "gear"):
        if kind in text:
            return kind
    if "mate" in text:
        return "mate"
    return "unknown"


def feature_entities(feature: dict[str, Any], component_names: list[str]) -> list[str]:
    found: list[str] = explicit_component_refs(feature)
    text = text_of(feature)
    for name in component_names:
        if name.lower() in text:
            found.append(name)
    deduped: list[str] = []
    seen: set[str] = set()
    for item in found:
        if item not in seen:
            seen.add(item)
            deduped.append(item)
    return deduped


def mate_evidence(features: list[dict[str, Any]], component_names: list[str]) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for f in features:
        if "mate" not in feature_text(f):
            continue
        refs = feature_entities(f, component_names)
        entry = {
            "name": name_of(f),
            "mate_type": infer_mate_type(f),
            "references": refs,
            "source": f.get("source", "features"),
            "evidence": "feature name/type/entities from inspect report",
        }
        if len(refs) >= 2:
            entry["a"] = refs[0]
            entry["b"] = refs[1]
        result.append(entry)
    return result


def manufacturing_feature_kind(feature: dict[str, Any]) -> str:
    text = feature_text(feature)
    if "thread" in text or "tap" in text:
        return "thread"
    if "hole" in text or "孔" in text:
        return "hole"
    if "pattern" in text or "pcd" in text:
        return "pattern"
    if "cut" in text:
        return "cut"
    return "manufacturing_candidate"


def manufacturing_evidence(features: list[dict[str, Any]], dimensions: list[dict[str, Any]], component_names: list[str]) -> dict[str, Any]:
    feature_rows: list[dict[str, Any]] = []
    for f in features:
        text = text_of(f)
        if any(k in text for k in ("hole", "孔", "pattern", "pcd", "cut", "extrude", "thread", "tap", "bolt", "screw", "dowel")):
            feature_rows.append({
                "name": name_of(f),
                "type": f.get("type"),
                "kind": manufacturing_feature_kind(f),
                "component_refs": feature_entities(f, component_names),
                "suppressed": f.get("suppressed"),
            })
    dim_rows: list[dict[str, Any]] = []
    for d in dimensions:
        text = text_of(d)
        if any(k in text for k in ("hole", "孔", "dia", "diameter", "pitch", "pcd", "clearance", "bolt", "dowel", "m3", "m4", "m5", "m6")):
            dim_rows.append({"name": name_of(d), "value_m": d.get("system_value_m"), "feature": d.get("feature")})
    return {"features": feature_rows, "dimensions": dim_rows, "hole_groups": manufacturing_hole_groups(feature_rows, dim_rows, component_names)}


def component_token(name: str) -> str:
    stem = name.lower().split("@")[-1].replace(".sldprt", "").replace(".sldasm", "")
    stem = stem.split("-")[0]
    return stem


def fastener_or_locator_name(name: str) -> bool:
    lower = name.lower()
    return any(k in lower for k in ("bolt", "screw", "fastener", "dowel", "pin", "locator", "m3", "m4", "m5", "m6", "螺", "销", "定位"))


def manufacturing_hole_groups(feature_rows: list[dict[str, Any]], dim_rows: list[dict[str, Any]], component_names: list[str]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for f in feature_rows:
        refs = [r for r in f.get("component_refs", []) if r]
        if not refs:
            continue
        for ref in refs:
            g = groups.setdefault(ref, {"component": ref, "features": [], "dimensions": [], "nearby_fastener_or_locator_components": [], "missing_engineering_detail": []})
            g["features"].append(f["name"])
    for d in dim_rows:
        token = component_token(str(d.get("name") or ""))
        for comp in component_names:
            if token and token in comp.lower():
                g = groups.setdefault(comp, {"component": comp, "features": [], "dimensions": [], "nearby_fastener_or_locator_components": [], "missing_engineering_detail": []})
                g["dimensions"].append(d["name"])
    fasteners = [c for c in component_names if fastener_or_locator_name(c)]
    for group in groups.values():
        text = " ".join(group["features"] + group["dimensions"] + [group["component"]]).lower()
        wanted = []
        for comp in fasteners:
            lower = comp.lower()
            if any(k in text for k in ("bolt", "m3", "m4", "m5", "m6", "clearance")) and any(k in lower for k in ("bolt", "screw", "fastener", "m3", "m4", "m5", "m6")):
                wanted.append(comp)
            if any(k in text for k in ("dowel", "pin", "locator")) and any(k in lower for k in ("dowel", "pin", "locator")):
                wanted.append(comp)
        group["nearby_fastener_or_locator_components"] = sorted(set(wanted))
        group["features"] = sorted(set(group["features"]))
        group["dimensions"] = sorted(set(group["dimensions"]))
        group["missing_engineering_detail"] = [
            "thread_or_fit_spec",
            "tolerance_or_inspection_requirement",
            "manufacturing_process",
            "tool_access_direction",
            "minimum_edge_distance",
        ]
    return sorted(groups.values(), key=lambda g: g["component"])


def transform_evidence(components: list[dict[str, Any]]) -> dict[str, Any]:
    items: list[dict[str, Any]] = []
    missing: list[dict[str, str]] = []
    for c in components:
        name = name_of(c)
        t = transform_struct(c)
        if t is None:
            missing.append({"object": name, "issue": "component lacks transform_array evidence"})
            continue
        items.append({
            "name": name,
            "origin_m": t["origin_m"],
            "local_axes": t["local_axes"],
            "scale": t.get("scale"),
            "evidence": "Component transform_array from inspect report",
        })
    return {"components": items, "relationships": transform_relationships(items), "missing_transform_evidence": missing}


def dot(a: list[float], b: list[float]) -> float:
    return sum(float(x) * float(y) for x, y in zip(a, b))


def norm(a: list[float]) -> float:
    return math.sqrt(dot(a, a))


def unit_dot(a: list[float], b: list[float]) -> float | None:
    na = norm(a)
    nb = norm(b)
    if na <= 1e-12 or nb <= 1e-12:
        return None
    return dot(a, b) / (na * nb)


def origin_distance(a: list[float], b: list[float]) -> float:
    return math.sqrt(sum((float(x) - float(y)) ** 2 for x, y in zip(a, b)))


def transform_relationships(items: list[dict[str, Any]], limit: int = 80) -> list[dict[str, Any]]:
    relationships: list[dict[str, Any]] = []
    for i, a in enumerate(items):
        for b in items[i + 1:]:
            a_name = str(a.get("name"))
            b_name = str(b.get("name"))
            a_origin = a.get("origin_m") or []
            b_origin = b.get("origin_m") or []
            if len(a_origin) == 3 and len(b_origin) == 3:
                delta = [float(b_origin[j]) - float(a_origin[j]) for j in range(3)]
                relationships.append({
                    "a": a_name,
                    "b": b_name,
                    "relation": "transform:origin_offset",
                    "delta_m": delta,
                    "distance_m": origin_distance(a_origin, b_origin),
                    "evidence": "component transform origins",
                })
            a_axes = a.get("local_axes") or {}
            b_axes = b.get("local_axes") or {}
            for axis_a, vec_a in a_axes.items():
                if not isinstance(vec_a, list) or len(vec_a) != 3:
                    continue
                for axis_b, vec_b in b_axes.items():
                    if not isinstance(vec_b, list) or len(vec_b) != 3:
                        continue
                    cos = unit_dot(vec_a, vec_b)
                    if cos is None:
                        continue
                    abs_cos = abs(cos)
                    if abs_cos >= 0.999:
                        relationships.append({
                            "a": a_name,
                            "b": b_name,
                            "relation": "transform:axis_parallel",
                            "axis_a": axis_a,
                            "axis_b": axis_b,
                            "cosine": cos,
                            "confidence": "high",
                            "evidence": "component local_axes dot product",
                        })
                    elif abs(cos) <= 0.001:
                        relationships.append({
                            "a": a_name,
                            "b": b_name,
                            "relation": "transform:axis_orthogonal",
                            "axis_a": axis_a,
                            "axis_b": axis_b,
                            "cosine": cos,
                            "confidence": "high",
                            "evidence": "component local_axes dot product",
                        })
    priority = {"transform:origin_offset": 0, "transform:axis_parallel": 1, "transform:axis_orthogonal": 2}
    relationships.sort(key=lambda r: (priority.get(str(r.get("relation")), 9), r.get("a", ""), r.get("b", ""), r.get("axis_a", ""), r.get("axis_b", "")))
    return relationships[:limit]


def node_id(kind: str, name: str) -> str:
    return f"{kind}:{name}"


def add_node(nodes: dict[str, dict[str, Any]], kind: str, name: str, **attrs: Any) -> str:
    nid = node_id(kind, name)
    if nid not in nodes:
        nodes[nid] = {"id": nid, "kind": kind, "name": name}
    nodes[nid].update({k: v for k, v in attrs.items() if v is not None})
    return nid


def add_edge(edges: list[dict[str, Any]], source: str, target: str, relation: str, **attrs: Any) -> None:
    edge = {"source": source, "target": target, "relation": relation}
    edge.update({k: v for k, v in attrs.items() if v is not None})
    edges.append(edge)


def constraint_network(
    components: list[dict[str, Any]],
    dimensions: list[dict[str, Any]],
    features: list[dict[str, Any]],
    mates: list[dict[str, Any]],
    manufacturing: dict[str, Any],
    spatial: dict[str, Any],
    transforms: dict[str, Any],
    gaps: list[dict[str, str]],
) -> dict[str, Any]:
    nodes: dict[str, dict[str, Any]] = {}
    edges: list[dict[str, Any]] = []
    component_ids: dict[str, str] = {}
    for c in components:
        name = name_of(c)
        component_ids[name] = add_node(nodes, "component", name, suppressed=c.get("suppressed"), hidden=c.get("hidden"), fixed=c.get("fixed"), has_bbox=parse_bbox(c) is not None)
    for f in features:
        name = name_of(f)
        add_node(nodes, "feature", name, type=f.get("type"), suppressed=f.get("suppressed"))
    for d in dimensions:
        name = name_of(d)
        did = add_node(nodes, "dimension", name, value_m=d.get("system_value_m"), feature=d.get("feature"))
        if d.get("feature"):
            fid = add_node(nodes, "feature", str(d.get("feature")))
            add_edge(edges, did, fid, "drives_or_measures_feature")

    for m in mates:
        mid = add_node(nodes, "feature", str(m.get("name")), type=m.get("mate_type"))
        refs = [r for r in m.get("references", []) if r in component_ids]
        for ref in refs:
            add_edge(edges, mid, component_ids[ref], "references_component", evidence="mate feature reference")
        if len(refs) >= 2:
            add_edge(edges, component_ids[refs[0]], component_ids[refs[1]], f"mate:{m.get('mate_type')}", via=mid)

    for f in manufacturing.get("features", []):
        fid = add_node(nodes, "feature", str(f.get("name")), type=f.get("type"), manufacturing_kind=f.get("kind"))
        refs = [r for r in f.get("component_refs", []) if r in component_ids]
        for ref in refs:
            add_edge(edges, fid, component_ids[ref], "manufacturing_feature_on", kind=f.get("kind"))
    for d in manufacturing.get("dimensions", []):
        did = add_node(nodes, "dimension", str(d.get("name")), value_m=d.get("value_m"), feature=d.get("feature"))
        if d.get("feature"):
            fid = add_node(nodes, "feature", str(d.get("feature")))
            add_edge(edges, did, fid, "drives_or_measures_feature")
    for g in manufacturing.get("hole_groups", []):
        gid = add_node(nodes, "manufacturing_hole_group", str(g.get("component")), missing_engineering_detail=g.get("missing_engineering_detail"))
        comp = str(g.get("component"))
        if comp in component_ids:
            add_edge(edges, gid, component_ids[comp], "manufacturing:hole_group_on")
        for nearby in g.get("nearby_fastener_or_locator_components", []):
            if nearby in component_ids:
                add_edge(edges, gid, component_ids[nearby], "manufacturing:nearby_fastener_or_locator")

    for p in spatial.get("near_or_overlap_pairs", [])[:20]:
        if p.get("a") in component_ids and p.get("b") in component_ids:
            add_edge(edges, component_ids[p["a"]], component_ids[p["b"]], f"spatial:{p.get('relation')}", gap_m=p.get("gap_m"), center_distance_m=p.get("center_distance_m"))
    for p in spatial.get("coaxial_candidates", [])[:20]:
        if p.get("a") in component_ids and p.get("b") in component_ids:
            add_edge(edges, component_ids[p["a"]], component_ids[p["b"]], "spatial:coaxial_candidate", axis=p.get("axis"), confidence=p.get("confidence"))
    for r in spatial.get("containment_relations", [])[:20]:
        if r.get("container") in component_ids and r.get("inside") in component_ids:
            add_edge(edges, component_ids[r["container"]], component_ids[r["inside"]], "spatial:contains", confidence=r.get("confidence"))

    for r in transforms.get("relationships", [])[:40]:
        if r.get("a") in component_ids and r.get("b") in component_ids:
            add_edge(
                edges,
                component_ids[r["a"]],
                component_ids[r["b"]],
                str(r.get("relation")),
                axis_a=r.get("axis_a"),
                axis_b=r.get("axis_b"),
                cosine=r.get("cosine"),
                distance_m=r.get("distance_m"),
                confidence=r.get("confidence"),
            )

    for g in gaps:
        gid = add_node(nodes, "gap", str(g.get("kind")), why=g.get("why"))
        add_edge(edges, "document:active", gid, "evidence_gap")
    if gaps:
        add_node(nodes, "document", "active")

    unique_edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for e in edges:
        key = (str(e["source"]), str(e["target"]), str(e["relation"]))
        if key not in seen:
            seen.add(key)
            unique_edges.append(e)
    summary = {
        "nodes": len(nodes),
        "edges": len(unique_edges),
        "component_nodes": sum(1 for n in nodes.values() if n["kind"] == "component"),
        "feature_nodes": sum(1 for n in nodes.values() if n["kind"] == "feature"),
        "dimension_nodes": sum(1 for n in nodes.values() if n["kind"] == "dimension"),
        "gap_nodes": sum(1 for n in nodes.values() if n["kind"] == "gap"),
        "manufacturing_hole_group_nodes": sum(1 for n in nodes.values() if n["kind"] == "manufacturing_hole_group"),
        "mate_edges": sum(1 for e in unique_edges if str(e["relation"]).startswith("mate:")),
        "manufacturing_edges": sum(1 for e in unique_edges if str(e["relation"]).startswith("manufacturing")),
        "spatial_edges": sum(1 for e in unique_edges if str(e["relation"]).startswith("spatial:")),
        "transform_edges": sum(1 for e in unique_edges if str(e["relation"]).startswith("transform:")),
    }
    return {"summary": summary, "nodes": sorted(nodes.values(), key=lambda n: (n["kind"], n["name"])), "edges": unique_edges}


def task_readiness(graph: dict[str, Any], dimensions: list[dict[str, Any]], components: list[dict[str, Any]]) -> list[dict[str, Any]]:
    manufacturing = graph.get("manufacturing_evidence") or {}
    spatial = graph.get("spatial_evidence") or {}
    gaps = graph.get("evidence_gaps") or []
    gap_kinds = {str(g.get("kind")) for g in gaps}
    has_dimensions = bool(dimensions)
    has_mate_edges = bool(graph.get("mate_evidence"))
    has_spatial_pairs = bool(spatial.get("near_or_overlap_pairs") or spatial.get("coaxial_candidates") or spatial.get("containment_relations"))
    has_manufacturing = bool(manufacturing.get("features") or manufacturing.get("dimensions"))
    floating = [name_of(c) for c in components if c.get("fixed") is False and c.get("suppressed") is not True]

    readiness = [
        {
            "task": "dimension_edit",
            "status": "needs_evidence" if has_dimensions else "blocked",
            "supported_by": ["dimension candidates present"] if has_dimensions else [],
            "missing_evidence": [
                "backup set and owning model path before any write",
                "exact full dimension chosen for a one-variable edit",
                "before/after inspect and compare plan",
            ] if has_dimensions else ["no dimensions were reported"],
            "recommended_next_queries": [
                {"tool": "report-search", "why": "narrow to the exact dimension full name", "command": "swctl.ps1 report-search -Report <inspect.json> -Action dimensions -Target \"<dimension concern>\""},
                {"tool": "safe-set-dimension", "why": "only after backup target and exact dimension are known", "command": "swctl.ps1 safe-set-dimension -Model <model> -Dimension <full_name> -ValueM <meters>"},
            ],
        },
        {
            "task": "assembly_constraints",
            "status": "ready_for_review" if has_mate_edges or floating else "needs_evidence",
            "supported_by": (["mate-like evidence present"] if has_mate_edges else []) + ([f"floating components: {', '.join(floating[:5])}"] if floating else []),
            "missing_evidence": [] if has_mate_edges else ["explicit mate references or live selection evidence"],
            "recommended_next_queries": [
                {"tool": "selection-report", "why": "confirm live selected faces/axes/components before mate edits", "command": "swctl.ps1 selection-report -Out <selection.json>"},
                {"tool": "report-search", "why": "expand mate/fixed/floating evidence", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"mate fixed floating suppressed\""},
            ],
        },
        {
            "task": "interference_clearance",
            "status": "needs_live_check" if has_spatial_pairs else "blocked",
            "supported_by": ["bbox spatial relationships present"] if has_spatial_pairs else [],
            "missing_evidence": ["SolidWorks interference result", "section/view confirmation for intentional contact vs collision"] if has_spatial_pairs else ["no spatial relationships were derivable"],
            "recommended_next_queries": [
                {"tool": "interference", "why": "bbox overlap/proximity is not final interference evidence", "command": "swctl.ps1 interference -Out <interference.json>"},
                {"tool": "inspect", "why": "refresh spatial evidence before judging clearance", "command": "swctl.ps1 inspect -Out <inspect_after_refresh.json>"},
            ],
        },
        {
            "task": "manufacturing_holes",
            "status": "needs_engineering_detail" if has_manufacturing else "needs_evidence",
            "supported_by": ["hole/manufacturing feature or dimension candidates present"] if has_manufacturing else [],
            "missing_evidence": [
                "thread or fit specification",
                "tolerance and inspection requirement",
                "manufacturing process and tool access confirmation",
            ] if has_manufacturing else ["no hole/manufacturing feature or dimension evidence was detected"],
            "recommended_next_queries": [
                {"tool": "report-search", "why": "expand hole, pitch, diameter, cut, and pattern evidence", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"hole pitch diameter pattern cut thread\""},
                {"tool": "model-understand", "why": "switch to spatial view to assess access and adjacent components", "command": "swctl.ps1 model-understand -Report <inspect.json> -View spatial-assembly -Target \"tool access and hole clearance\""},
            ],
        },
    ]
    if "mate_reference_partial" in gap_kinds:
        for item in readiness:
            if item["task"] == "assembly_constraints":
                item["missing_evidence"].append("some mate references are partial in inspect data")
    return readiness


def evidence_graph(components: list[dict[str, Any]], dimensions: list[dict[str, Any]], features: list[dict[str, Any]]) -> dict[str, Any]:
    component_names = [name_of(c) for c in components]
    spatial = spatial_model(components)
    manufacturing = manufacturing_evidence(features, dimensions, component_names)
    transforms = transform_evidence(components)
    mates = mate_evidence(features, component_names)
    near_or_overlap = [p for p in spatial["pairwise_relations"] if p["relation"] in {"overlap", "near"}][:20]
    gaps: list[dict[str, str]] = []
    if manufacturing["features"] or manufacturing["dimensions"]:
        gaps.extend([
            {"kind": "thread_or_fit_spec_missing", "why": "Inspect evidence identifies hole/manufacturing candidates but does not prove thread class, fit, tolerance, or fastener standard."},
            {"kind": "manufacturing_process_missing", "why": "Feature names/types do not prove milling, drilling, reaming, tapping, print tolerance, or inspection process."},
            {"kind": "tool_access_unproven", "why": "Bounding boxes and feature names do not prove tool approach direction, setup, or service access."},
        ])
    if not mates:
        gaps.append({"kind": "mate_reference_missing", "why": "No mate-like feature evidence links components; constraint intent needs live mate or selection evidence."})
    else:
        unresolved = [m["name"] for m in mates if len(m.get("references", [])) < 2]
        if unresolved:
            gaps.append({"kind": "mate_reference_partial", "why": "Some mate-like features lack two explicit component references in the inspect report.", "objects": ", ".join(unresolved[:5])})
        explicit_edges = [(m.get("a"), m.get("b")) for m in mates if m.get("a") and m.get("b")]
        constrained_components = {str(x) for edge in explicit_edges for x in edge}
        # A single mate in a many-part assembly is almost always too weak for
        # real assembly understanding.  Do not pretend that "some mate exists"
        # means the spatial/constraint model is credible; surface it as a
        # graph-level evidence gap so the operator is pushed toward diagnose /
        # repair-plan / mate-group planning.
        if len(component_names) >= 3 and len(explicit_edges) <= 1:
            missing = sorted(name for name in component_names if name not in constrained_components)
            gaps.append({
                "kind": "constraint_network_underconnected",
                "why": "Only one or zero explicit component-to-component mate edges were readable for a three-or-more-component assembly.",
                "objects": ", ".join(missing[:8]),
            })
    if spatial["missing_spatial_evidence"]:
        gaps.append({"kind": "spatial_evidence_partial", "why": "Some components lack bounding boxes, so proximity/containment reasoning is incomplete."})
    spatial_evidence = {
        "dominant_axis": spatial["dominant_axis"],
        "near_or_overlap_pairs": near_or_overlap,
        "coaxial_candidates": spatial["coaxial_candidates"],
        "containment_relations": spatial["containment_relations"],
        "missing_spatial_evidence": spatial["missing_spatial_evidence"],
    }
    return {
        "components_index": [{"name": name_of(c), "state": {"suppressed": c.get("suppressed"), "hidden": c.get("hidden"), "fixed": c.get("fixed")}, "has_bbox": parse_bbox(c) is not None} for c in components],
        "mate_evidence": mates,
        "manufacturing_evidence": manufacturing,
        "transform_evidence": transforms,
        "spatial_evidence": spatial_evidence,
        "evidence_gaps": gaps,
        "constraint_network": constraint_network(components, dimensions, features, mates, manufacturing, spatial_evidence, transforms, gaps),
    }


def spatial_model(components: list[dict[str, Any]], limit: int = 60) -> dict[str, Any]:
    with_box: list[dict[str, Any]] = []
    missing: list[dict[str, Any]] = []
    for c in components:
        box = parse_bbox(c)
        name = name_of(c)
        if box is None:
            missing.append({"object": name, "issue": "component lacks bbox_m/bounding_box_m evidence"})
            continue
        with_box.append({
            "name": name,
            "path": c.get("path"),
            "bbox_m": box,
            "center_m": bbox_center(box),
            "size_m": bbox_size(box),
            "state": {"suppressed": c.get("suppressed"), "hidden": c.get("hidden"), "fixed": c.get("fixed")},
        })
    pairs: list[dict[str, Any]] = []
    for i, a in enumerate(with_box):
        for b in with_box[i + 1:]:
            pairs.append(pair_relation(a, b))
    pairs.sort(key=lambda p: ({"overlap": 0, "near": 1, "separated": 2}.get(str(p["relation"]), 9), abs(float(p["gap_m"])), p["a"], p["b"]))
    axis = dominant_axis_for_components(with_box)
    return {
        "components": with_box,
        "dominant_axis": axis,
        "axis_stack": axis_stack(with_box, axis),
        "coaxial_candidates": infer_coaxial_candidates(with_box, axis),
        "containment_relations": infer_containment_relations(with_box, axis),
        "pairwise_relations": pairs[:limit],
        "missing_spatial_evidence": missing,
    }


def next_queries(domains: list[dict[str, Any]], risks: list[dict[str, Any]], view: str) -> list[dict[str, str]]:
    queries: list[dict[str, str]] = []
    if view == "dimension-edit":
        queries.extend([
            {"tool": "report-search", "why": "find the exact full dimension name before editing", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"<dimension or feature name>\" -Action dimensions"},
            {"tool": "safe-set-dimension", "why": "run backup, edit, rebuild, inspect, compare, and change verification as one guarded flow", "command": "swctl.ps1 safe-set-dimension -Model <model.SLDPRT|SLDASM> -Dimension <full_name> -ValueM <meters>"},
            {"tool": "compare", "why": "review before/after report delta before saving or continuing", "command": "swctl.ps1 compare -Before <before.json> -After <after.json> -JsonOut <delta.json>"},
        ])
    elif view == "assembly-constraints":
        queries.extend([
            {"tool": "selection-report", "why": "verify selected mates/entities or intended datum components in live SolidWorks", "command": "swctl.ps1 selection-report -Out <selection.json>"},
            {"tool": "report-search", "why": "expand mate/component evidence related to constraints", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"mate fixed suppressed floating\""},
        ])
    elif view == "interference-clearance":
        queries.extend([
            {"tool": "interference", "why": "run assembly interference detection for clearance-sensitive objects", "command": "swctl.ps1 interference -Out <interference.json>"},
            {"tool": "mass", "why": "collect mass properties if clearance changes also affect weight or center of mass", "command": "swctl.ps1 mass -Out <mass.json>"},
        ])
    elif view == "spatial-assembly":
        queries.extend([
            {"tool": "inspect", "why": "refresh component transforms and bounding boxes before trusting spatial inferences", "command": "swctl.ps1 inspect -Out <inspect_spatial.json>"},
            {"tool": "interference", "why": "turn rough bbox overlap/proximity into SolidWorks interference evidence", "command": "swctl.ps1 interference -Out <interference.json>"},
            {"tool": "selection-report", "why": "capture exact selected faces/axes when spatial intent depends on datums", "command": "swctl.ps1 selection-report -Out <selection.json>"},
        ])
    elif view == "manufacturing-holes":
        queries.extend([
            {"tool": "report-search", "why": "find hole, bolt, flange, and cut features before judging manufacturability", "command": "swctl.ps1 report-search -Report <inspect.json> -Target \"hole bolt screw flange cut\""},
            {"tool": "model-understand", "why": "switch to dimension-edit view before changing hole or PCD dimensions", "command": "swctl.ps1 model-understand -Report <inspect.json> -View dimension-edit -Target \"<hole change>\""},
        ])
    for d in domains[:5]:
        q = " ".join(d["evidence_keywords"][:4]) or d["domain"]
        queries.append({"tool": "report-search", "why": f"expand task-relevant objects for {d['domain']}", "command": f"swctl.ps1 report-search -Report <inspect.json> -Target \"{q}\""})
    if any(r["kind"] == "risk" and "floating" in r.get("issue", "") for r in risks):
        queries.append({"tool": "selection-report", "why": "verify intended datum/fixed component before changing mates or states", "command": "swctl.ps1 selection-report -Out <selection.json>"})
    if any(d["domain"] in {"mass_clearance", "rotating_support", "sensor_or_reference_alignment"} for d in domains):
        queries.append({"tool": "interference", "why": "validate clearance-sensitive relationships after understanding key components", "command": "swctl.ps1 interference -Out <interference.json>"})
    queries.append({"tool": "report-context", "why": "create a broader handoff only if this compact view is insufficient", "command": "swctl.ps1 report-context -Report <inspect.json> -Target \"<focus>\""})
    deduped: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for q in queries:
        key = (q["tool"], q["command"])
        if key not in seen:
            seen.add(key)
            deduped.append(q)
    return deduped[:8]


def understand(report: dict[str, Any], task: str, object_limit: int, anchor_limit: int, requested_view: str = "auto") -> dict[str, Any]:
    doc = active_doc(report)
    comps = rows(doc.get("components"))
    dims = rows(doc.get("dimensions"))
    feats = feature_rows_with_mates(doc)
    view = resolve_view(requested_view, task)
    domains = detect_domains(task, comps, dims, feats)
    mode = "focused" if any(d["task_mentioned"] for d in domains) else "broad"
    if not domains:
        domains = [{"domain": "general_model_state", "task_mentioned": False, "evidence_keywords": [], "why": "No specific domain was detected, so keep a compact baseline view."}]
    relevant = relevant_objects(comps, dims, feats, domains, task, object_limit if mode == "focused" or view != "general" else min(object_limit, 10), view)
    anchors = compact_anchors(comps, dims, feats, anchor_limit)
    risks = risks_and_unknowns(comps, dims, feats, domains)
    spatial = spatial_model(comps) if view == "spatial-assembly" else None
    graph = evidence_graph(comps, dims, feats)
    if spatial:
        for p in spatial["pairwise_relations"]:
            if p["relation"] == "overlap":
                risks.append({"kind": "spatial_overlap", "object": f"{p['a']} ↔ {p['b']}", "issue": "component bounding boxes overlap", "impact": "may be intentional containment/contact or actual interference; verify with SolidWorks interference and section view"})
        for m in spatial["missing_spatial_evidence"]:
            risks.append({"kind": "unknown", "object": m["object"], "issue": m["issue"], "impact": "AI cannot reason about this component's spatial relationship from the current report"})
    feature_counts = dict(sorted(Counter(str(f.get("type") or "<unknown>") for f in feats).items()))
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "task": task,
        "scope": {"mode": mode, "view": view, "requested_view": requested_view, "object_limit": object_limit, "anchor_limit": anchor_limit, "principle": "Give enough task-specific CAD context for reasoning, but avoid raw report dumps."},
        "document": {"title": doc.get("title"), "path": doc.get("path"), "type": doc.get("type"), "configuration": doc.get("configuration")},
        "baseline": {
            "inventory": {
                "component_count": len(comps),
                "dimension_count": len(dims),
                "feature_count": len(feats),
                "feature_type_counts": feature_counts,
                "suppressed_components": [name_of(c) for c in comps if c.get("suppressed") is True],
                "hidden_components": [name_of(c) for c in comps if c.get("hidden") is True],
                "floating_components": [name_of(c) for c in comps if c.get("fixed") is False and c.get("suppressed") is not True],
            },
            "anchors": anchors,
        },
        "view_model": VIEW_MODELS[view],
        "task_model": {"domains": domains, "relevant_objects": relevant},
        "relationship_hypotheses": relationship_hypotheses(comps, feats, domains),
        "cad_evidence_graph": graph,
        "decision_readiness": task_readiness(graph, dims, comps),
        "unknowns_and_risks": risks,
        "next_queries": next_queries(domains, risks, view),
    }
    if spatial:
        result["spatial_model"] = spatial
    return result


def markdown(data: dict[str, Any]) -> str:
    lines = ["# SolidWorks Model Understanding", ""]
    lines += [
        f"- Task: `{data['task'] or '<empty>'}`",
        f"- Scope: `{data['scope']['mode']}`",
        f"- View: `{data['scope']['view']}`",
        f"- Document: `{data['document'].get('title')}`",
        f"- Path: `{data['document'].get('path')}`",
        "",
        "## Baseline facts",
    ]
    inv = data["baseline"]["inventory"]
    lines += [
        f"- Components: `{inv['component_count']}`",
        f"- Dimensions: `{inv['dimension_count']}`",
        f"- Features: `{inv['feature_count']}`",
        f"- Suppressed components: `{', '.join(inv['suppressed_components']) or '<none>'}`",
        f"- Floating components: `{', '.join(inv['floating_components']) or '<none>'}`",
        "",
        "## Task-scoped view",
        "## View-specific context",
        f"- Primary object kind: `{data['view_model']['primary_object_kind']}`",
        f"- Purpose: {data['view_model']['purpose']}",
        f"- Focus fields: `{', '.join(data['view_model']['focus_fields'])}`",
        "",
        "### Detected domains",
    ]
    for d in data["task_model"]["domains"]:
        kws = ", ".join(d.get("evidence_keywords") or []) or "no direct keyword"
        lines.append(f"- `{d['domain']}` task_mentioned=`{d['task_mentioned']}` keywords=`{kws}` — {d['why']}")
    lines += ["", "### Relevant objects"]
    if data["task_model"]["relevant_objects"]:
        for o in data["task_model"]["relevant_objects"]:
            reason = "; ".join(o.get("why_relevant") or [])
            extra = ""
            if o["kind"] == "dimension":
                extra = f" value_m=`{o.get('value_m')}` feature=`{o.get('feature')}`"
            elif o["kind"] == "component":
                st = o.get("state") or {}
                extra = f" suppressed=`{st.get('suppressed')}` hidden=`{st.get('hidden')}` fixed=`{st.get('fixed')}`"
            elif o["kind"] == "feature":
                extra = f" type=`{o.get('type')}`"
            lines.append(f"- {o['kind']} `{o['name']}` score=`{o['score']}`{extra} — {reason}")
    else:
        lines.append("- No task-specific object exceeded the relevance threshold; use next queries to gather focus.")
    lines += ["", "## Relationship hypotheses"]
    for h in data["relationship_hypotheses"]:
        ev = ", ".join(h.get("evidence") or []) or "<weak evidence>"
        lines.append(f"- confidence=`{h['confidence']}` {h['hypothesis']} evidence=`{ev}`")
    if data.get("cad_evidence_graph"):
        graph = data["cad_evidence_graph"]
        lines += ["", "## CAD evidence graph"]
        lines.append(f"- Components indexed: `{len(graph.get('components_index', []))}`")
        lines += ["", "### Mate evidence"]
        if graph.get("mate_evidence"):
            for m in graph["mate_evidence"][:12]:
                refs = ", ".join(m.get("references") or []) or "<references not explicit>"
                pair = f" `{m.get('a')}` ↔ `{m.get('b')}`" if m.get("a") and m.get("b") else ""
                lines.append(f"- `{m['name']}` type=`{m['mate_type']}`{pair} refs=`{refs}`")
        else:
            lines.append("- No mate-like feature evidence in this inspect report.")
        manufacturing = graph.get("manufacturing_evidence") or {}
        lines += ["", "### Manufacturing evidence"]
        if manufacturing.get("features"):
            for f in manufacturing["features"][:12]:
                refs = ", ".join(f.get("component_refs") or []) or "<component not explicit>"
                lines.append(f"- feature `{f['name']}` type=`{f.get('type')}` kind=`{f.get('kind')}` refs=`{refs}`")
        if manufacturing.get("dimensions"):
            for d in manufacturing["dimensions"][:12]:
                lines.append(f"- dimension `{d['name']}` value_m=`{d.get('value_m')}` feature=`{d.get('feature')}`")
        if not manufacturing.get("features") and not manufacturing.get("dimensions"):
            lines.append("- No manufacturing-like feature or dimension evidence was detected.")
        if manufacturing.get("hole_groups"):
            lines += ["", "#### Hole groups"]
            for g in manufacturing["hole_groups"][:12]:
                lines.append(f"- component `{g['component']}` features=`{', '.join(g.get('features') or []) or '<none>'}` dimensions=`{', '.join(g.get('dimensions') or []) or '<none>'}` nearby_fastener_or_locator=`{', '.join(g.get('nearby_fastener_or_locator_components') or []) or '<none>'}` missing=`{', '.join(g.get('missing_engineering_detail') or [])}`")
        transforms = graph.get("transform_evidence") or {}
        lines += ["", "### Transform evidence"]
        if transforms.get("components"):
            for t in transforms["components"][:12]:
                axes = t.get("local_axes") or {}
                lines.append(f"- component `{t['name']}` origin_m=`{t.get('origin_m')}` x_axis=`{axes.get('x')}` y_axis=`{axes.get('y')}` z_axis=`{axes.get('z')}`")
            if transforms.get("relationships"):
                lines.append("")
                lines.append("#### Transform relationships")
                for r in transforms["relationships"][:16]:
                    if r.get("relation") == "transform:origin_offset":
                        lines.append(f"- `{r['a']}` -> `{r['b']}` relation=`{r['relation']}` delta_m=`{r.get('delta_m')}` distance_m=`{r.get('distance_m')}`")
                    else:
                        lines.append(f"- `{r['a']}` -> `{r['b']}` relation=`{r['relation']}` axes=`{r.get('axis_a')}:{r.get('axis_b')}` cosine=`{r.get('cosine')}`")
        else:
            lines.append("- No component transform evidence was detected.")
        lines += ["", "### Evidence gaps"]
        if graph.get("evidence_gaps"):
            for g in graph["evidence_gaps"][:12]:
                extra = f" objects=`{g.get('objects')}`" if g.get("objects") else ""
                lines.append(f"- `{g['kind']}`{extra}: {g['why']}")
        else:
            lines.append("- No graph-level evidence gaps detected; still verify live CAD state.")
        if graph.get("constraint_network"):
            net = graph["constraint_network"]
            summary = net.get("summary") or {}
            lines += ["", "### Constraint network"]
            lines.append(f"- nodes=`{summary.get('nodes')}` edges=`{summary.get('edges')}` mate_edges=`{summary.get('mate_edges')}` manufacturing_edges=`{summary.get('manufacturing_edges')}` spatial_edges=`{summary.get('spatial_edges')}` transform_edges=`{summary.get('transform_edges')}`")
            for e in (net.get("edges") or [])[:20]:
                lines.append(f"- `{e['source']}` -> `{e['target']}` relation=`{e['relation']}`")
    if data.get("decision_readiness"):
        lines += ["", "## Decision readiness"]
        for item in data["decision_readiness"]:
            supported = "; ".join(item.get("supported_by") or []) or "<weak evidence>"
            missing = "; ".join(item.get("missing_evidence") or []) or "<none at report level>"
            lines.append(f"- `{item['task']}` status=`{item['status']}` supported_by=`{supported}` missing=`{missing}`")
    if data.get("spatial_model"):
        lines += ["", "## Spatial relationships"]
        sm = data["spatial_model"]
        lines.append(f"- Dominant axis: `{sm.get('dominant_axis')}`")
        for c in sm["components"][:12]:
            lines.append(f"- component `{c['name']}` center_m=`{c['center_m']}` size_m=`{c['size_m']}`")
        if sm.get("axis_stack"):
            lines += ["", "### Axis stack"]
            for s in sm["axis_stack"][:16]:
                lines.append(f"- `{s['name']}` {s['axis']}=[{s['min_m']}, {s['max_m']}] center=`{s['center_m']}`")
        if sm.get("coaxial_candidates"):
            lines += ["", "### Coaxial candidates"]
            for p in sm["coaxial_candidates"][:16]:
                lines.append(f"- `{p['a']}` ↔ `{p['b']}` axis=`{p['axis']}` radial_center_distance_m=`{p['radial_center_distance_m']}` confidence=`{p['confidence']}`")
        if sm.get("containment_relations"):
            lines += ["", "### Containment relations"]
            for r in sm["containment_relations"][:16]:
                lines.append(f"- `{r['container']}` contains `{r['inside']}` confidence=`{r['confidence']}`")
        lines += ["", "### Pairwise bbox relations"]
        for p in sm["pairwise_relations"][:12]:
            lines.append(f"- `{p['a']}` ↔ `{p['b']}` relation=`{p['relation']}` gap_m=`{p['gap_m']}` center_delta_m=`{p['center_delta_m']}`")
        if sm["missing_spatial_evidence"]:
            lines += ["", "### Missing spatial evidence"]
            for m in sm["missing_spatial_evidence"][:12]:
                lines.append(f"- `{m['object']}`: {m['issue']}")
    lines += ["", "## Unknowns and risks"]
    if data["unknowns_and_risks"]:
        for r in data["unknowns_and_risks"]:
            lines.append(f"- `{r['kind']}` `{r['object']}`: {r['issue']} — {r['impact']}")
    else:
        lines.append("- No obvious report-level risk found; still verify live state before edits.")
    lines += ["", "## Next minimal queries"]
    for q in data["next_queries"]:
        lines.append(f"- `{q['tool']}`: {q['why']} — `{q['command']}`")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--task", default="")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/model_understanding.md")
    parser.add_argument("--json-out", default="tools/solidworks_codex/reports/model_understanding.json")
    parser.add_argument("--object-limit", type=int, default=12)
    parser.add_argument("--anchor-limit", type=int, default=15)
    parser.add_argument("--view", choices=sorted(VIEWS), default="auto")
    args = parser.parse_args()
    data = understand(load_report(args.report), args.task, args.object_limit, args.anchor_limit, args.view)
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(data), encoding="utf-8")
    jout.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(jout), "mode": data["scope"]["mode"], "view": data["scope"]["view"], "relevant_objects": len(data["task_model"]["relevant_objects"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
