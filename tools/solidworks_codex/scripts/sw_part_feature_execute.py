"""Execute reviewed part feature operations in SolidWorks and emit evidence.

The command consumes a JSON spec so feature creation is traceable:
intent/spec -> reviewed selectors -> SolidWorks FeatureManager call -> rebuild
evidence.  Dry-run mode validates and reports the exact selection/call plan
without touching SolidWorks.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import pythoncom  # type: ignore[import-not-found]
    import win32com.client  # type: ignore[import-not-found]
except ModuleNotFoundError:
    pythoncom = None  # type: ignore[assignment]
    win32com = None  # type: ignore[assignment]

SUPPORTED_OPERATIONS = {
    "fillet",
    "chamfer",
    "basic_hole",
    "countersink_hole",
    "counterbore_hole",
    "extrude_boss",
    "extrude_cut",
    "revolve_boss",
    "revolved_cut",
    "slot_cut",
    "pocket_cut",
    "linear_pattern",
    "circular_pattern",
    "mirror",
}
SELECT_BY_ID_TYPES = {"EDGE", "FACE", "PLANE", "AXIS", "SKETCH", "EXTSKETCHSEGMENT", "EXTSKETCHPOINT"}
OPERATION_ROLE_BY_OPERATION = {
    "fillet": "edge_rounding",
    "chamfer": "edge_break",
    "basic_hole": "cylindrical_hole_cut",
    "countersink_hole": "countersunk_hole_cut",
    "counterbore_hole": "counterbored_hole_cut",
    "extrude_boss": "reviewed_profile_extrude_boss",
    "extrude_cut": "reviewed_profile_extrude_cut",
    "revolve_boss": "reviewed_profile_revolve_boss",
    "revolved_cut": "reviewed_profile_revolved_cut",
    "slot_cut": "slot_profile_cut",
    "pocket_cut": "rectangular_pocket_cut",
    "linear_pattern": "repeat_seed_feature",
    "circular_pattern": "repeat_seed_feature",
    "mirror": "mirror_seed_feature",
}


def require_pywin32() -> tuple[Any, Any]:
    if pythoncom is None or win32com is None:
        raise RuntimeError(
            "SolidWorks live COM commands require pywin32. "
            "Install pywin32 or set SWCODEX_PYTHON to a Python that can import pythoncom and win32com.client."
        )
    return pythoncom, win32com.client


def value_of(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [value_of(item) for item in value]
    if hasattr(value, "_oleobj_"):
        return value
    return str(value)


def read(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        if args:
            if callable(member):
                return value_of(member(*args))
            return {"error": f"member {name} is a property, arguments were provided"}
        if callable(member) and not hasattr(member, "_oleobj_"):
            return value_of(member())
        return value_of(member)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def attach(start: bool) -> tuple[Any, bool]:
    _pythoncom, win32_client = require_pywin32()
    try:
        return win32_client.GetActiveObject("SldWorks.Application"), False
    except Exception as exc:
        if not start:
            raise RuntimeError("SolidWorks is not running. Start it or pass --start.") from exc
        sw = win32_client.Dispatch("SldWorks.Application")
        sw.Visible = True
        return sw, True


def open_or_active(sw: Any, model_path: str | None) -> Any:
    if not model_path:
        model = read(sw, "ActiveDoc")
        if model is None or isinstance(model, dict):
            raise RuntimeError("No active SolidWorks document. Open a part or pass --model.")
        return model
    path = str(Path(model_path).resolve())
    doc_type = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}.get(Path(path).suffix.lower())
    if doc_type is None:
        raise ValueError(f"Unsupported SolidWorks file type: {path}")
    pythoncom_mod, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    model = sw.OpenDoc6(path, doc_type, 0, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed: errors={errors.value}, warnings={warnings.value}, path={path}")
    return model


def save_model(model: Any) -> dict[str, Any]:
    pythoncom_mod, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    ok = model.Save3(1, errors, warnings)
    return {"ok": bool(ok), "errors": getattr(errors, "value", errors), "warnings": getattr(warnings, "value", warnings)}


def load_spec(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict):
        raise ValueError("Part feature spec must be a JSON object.")
    return data


def as_float(params: dict[str, Any], key: str, default: float | None = None) -> float:
    value = params.get(key, default)
    if value is None:
        raise ValueError(f"Missing numeric parameter: {key}")
    return float(value)


def as_int(params: dict[str, Any], key: str, default: int | None = None) -> int:
    value = params.get(key, default)
    if value is None:
        raise ValueError(f"Missing integer parameter: {key}")
    return int(value)


def mm_to_m(value: Any) -> float:
    return float(value) / 1000.0


def params_for(spec: dict[str, Any]) -> dict[str, Any]:
    params = spec.get("parameters") or {}
    if not isinstance(params, dict):
        raise ValueError("parameters must be a JSON object.")
    return params


def selectors_for(spec: dict[str, Any]) -> list[dict[str, Any]]:
    selectors = spec.get("selectors") or spec.get("selections") or []
    if not isinstance(selectors, list):
        raise ValueError("selectors must be a JSON array.")
    result = []
    for index, selector in enumerate(selectors):
        if not isinstance(selector, dict):
            raise ValueError(f"selector {index} must be a JSON object.")
        result.append(selector)
    return result


def operation_for(spec: dict[str, Any]) -> str:
    operation = str(spec.get("operation", "")).strip().lower().replace("-", "_")
    aliases = {
        "hole": "basic_hole",
        "through_hole": "basic_hole",
        "blind_hole": "basic_hole",
        "countersink": "countersink_hole",
        "countersunk_hole": "countersink_hole",
        "counterbore": "counterbore_hole",
        "counterbored_hole": "counterbore_hole",
        "boss": "extrude_boss",
        "boss_extrude": "extrude_boss",
        "extruded_boss": "extrude_boss",
        "extrude": "extrude_boss",
        "cut": "extrude_cut",
        "extruded_cut": "extrude_cut",
        "revolve": "revolve_boss",
        "revolved_boss": "revolve_boss",
        "revolve_cut": "revolved_cut",
        "slot": "slot_cut",
        "pocket": "pocket_cut",
        "linear": "linear_pattern",
        "circular": "circular_pattern",
        "edge_fillet": "fillet",
        "edge_chamfer": "chamfer",
    }
    operation = aliases.get(operation, operation)
    if operation not in SUPPORTED_OPERATIONS:
        raise ValueError(f"Unsupported operation {operation!r}; expected one of {sorted(SUPPORTED_OPERATIONS)}")
    return operation


def validate_selector(selector: dict[str, Any], index: int) -> dict[str, Any]:
    kind = str(selector.get("kind") or selector.get("selection_kind") or "").lower()
    if kind not in {"entity", "feature"}:
        raise ValueError(f"selector {index} requires kind 'entity' or 'feature'")
    name = str(selector.get("name") or selector.get("feature") or "").strip()
    if not name:
        raise ValueError(f"selector {index} requires name")
    if kind == "entity":
        select_type = str(selector.get("type") or "").upper()
        if select_type not in SELECT_BY_ID_TYPES:
            raise ValueError(f"selector {index} has unsupported entity type {select_type!r}")
        point = selector.get("point") or {}
        if point and not isinstance(point, dict):
            raise ValueError(f"selector {index} point must be an object with x/y/z")
        return {
            "kind": kind,
            "name": name,
            "type": select_type,
            "append": bool(selector.get("append", index > 0)),
            "mark": int(selector.get("mark", 0)),
            "point": {
                "x": float(point.get("x", selector.get("x", 0.0))),
                "y": float(point.get("y", selector.get("y", 0.0))),
                "z": float(point.get("z", selector.get("z", 0.0))),
            },
        }
    return {"kind": kind, "name": name, "append": bool(selector.get("append", index > 0)), "mark": int(selector.get("mark", 0))}


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    operation = operation_for(spec)
    selectors = [validate_selector(selector, index) for index, selector in enumerate(selectors_for(spec))]
    params = params_for(spec)
    if operation in {"fillet", "chamfer"} and not selectors:
        raise ValueError(f"{operation} requires at least one reviewed edge/face selector")
    if operation in {"linear_pattern", "circular_pattern", "mirror"} and not any(s["kind"] == "feature" for s in selectors):
        raise ValueError(f"{operation} requires at least one seed feature selector")
    if operation == "fillet":
        radius_m = params.get("radius_m", mm_to_m(params.get("radius_mm", 0)))
        if float(radius_m) <= 0:
            raise ValueError("fillet radius must be positive")
    if operation == "chamfer":
        distance_m = params.get("distance_m", mm_to_m(params.get("distance_mm", 0)))
        if float(distance_m) <= 0:
            raise ValueError("chamfer distance must be positive")
        if float(params.get("angle_deg", 45)) <= 0:
            raise ValueError("chamfer angle_deg must be positive")
    if operation in {"basic_hole", "countersink_hole", "counterbore_hole"}:
        diameter_m = float(params.get("diameter_m", mm_to_m(params.get("diameter_mm", 0))))
        depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
        if diameter_m <= 0:
            raise ValueError(f"{operation} diameter must be positive")
        if depth_m <= 0 and not bool(params.get("through_all")):
            raise ValueError(f"{operation} depth must be positive unless through_all is true")
        if not any(s["kind"] == "entity" and s["type"] in {"PLANE", "FACE"} for s in selectors):
            raise ValueError(f"{operation} requires a reviewed sketch plane or planar face selector")
    if operation == "countersink_hole":
        countersink_diameter_m = float(params.get("countersink_diameter_m", mm_to_m(params.get("countersink_diameter_mm", 0))))
        countersink_angle_deg = float(params.get("countersink_angle_deg", 0))
        diameter_m = float(params.get("diameter_m", mm_to_m(params.get("diameter_mm", 0))))
        if countersink_diameter_m <= diameter_m:
            raise ValueError("countersink_hole countersink diameter must be greater than pilot diameter")
        if countersink_angle_deg <= 0:
            raise ValueError("countersink_hole countersink_angle_deg must be positive")
    if operation == "counterbore_hole":
        counterbore_diameter_m = float(params.get("counterbore_diameter_m", mm_to_m(params.get("counterbore_diameter_mm", 0))))
        counterbore_depth_m = float(params.get("counterbore_depth_m", mm_to_m(params.get("counterbore_depth_mm", 0))))
        diameter_m = float(params.get("diameter_m", mm_to_m(params.get("diameter_mm", 0))))
        depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
        if counterbore_diameter_m <= diameter_m:
            raise ValueError("counterbore_hole counterbore diameter must be greater than pilot diameter")
        if counterbore_depth_m <= 0:
            raise ValueError("counterbore_hole counterbore_depth must be positive")
        if depth_m > 0 and counterbore_depth_m >= depth_m:
            raise ValueError("counterbore_hole counterbore_depth must be less than hole depth")
    if operation in {"extrude_boss", "extrude_cut"}:
        depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
        if depth_m <= 0 and not bool(params.get("through_all")):
            raise ValueError(f"{operation} depth must be positive unless through_all is true")
        if not any(s["kind"] == "entity" and s["type"] in {"SKETCH", "PLANE", "FACE"} for s in selectors):
            raise ValueError(f"{operation} requires a reviewed sketch, sketch plane, or planar face selector")
    if operation in {"revolve_boss", "revolved_cut"}:
        angle_deg = float(params.get("angle_deg", 360.0))
        if angle_deg <= 0 or angle_deg > 360:
            raise ValueError(f"{operation} angle_deg must be greater than 0 and no more than 360")
        if not any(s["kind"] == "entity" and s["type"] == "SKETCH" for s in selectors):
            raise ValueError(f"{operation} requires a reviewed profile sketch selector")
        if not any(s["kind"] == "entity" and s["type"] == "AXIS" for s in selectors):
            raise ValueError(f"{operation} requires a reviewed axis selector")
    if operation == "slot_cut":
        length_m = float(params.get("length_m", mm_to_m(params.get("length_mm", 0))))
        width_m = float(params.get("width_m", mm_to_m(params.get("width_mm", 0))))
        depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
        if length_m <= 0 or width_m <= 0:
            raise ValueError("slot_cut length and width must be positive")
        if length_m <= width_m:
            raise ValueError("slot_cut length must be greater than width")
        if depth_m <= 0 and not bool(params.get("through_all")):
            raise ValueError("slot_cut depth must be positive unless through_all is true")
        if not any(s["kind"] == "entity" and s["type"] in {"PLANE", "FACE"} for s in selectors):
            raise ValueError("slot_cut requires a reviewed sketch plane or planar face selector")
    if operation == "pocket_cut":
        width_m = float(params.get("width_m", mm_to_m(params.get("width_mm", 0))))
        height_m = float(params.get("height_m", mm_to_m(params.get("height_mm", 0))))
        depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
        if width_m <= 0 or height_m <= 0:
            raise ValueError("pocket_cut width and height must be positive")
        if depth_m <= 0 and not bool(params.get("through_all")):
            raise ValueError("pocket_cut depth must be positive unless through_all is true")
        if not any(s["kind"] == "entity" and s["type"] in {"PLANE", "FACE"} for s in selectors):
            raise ValueError("pocket_cut requires a reviewed sketch plane or planar face selector")
    if operation == "linear_pattern":
        if as_int(params, "count", 2) < 2:
            raise ValueError("linear_pattern count must be at least 2")
        if as_float(params, "spacing_m", mm_to_m(params.get("spacing_mm", 0))) <= 0:
            raise ValueError("linear_pattern spacing must be positive")
    if operation == "circular_pattern":
        if as_int(params, "count", 2) < 2:
            raise ValueError("circular_pattern count must be at least 2")
        if as_float(params, "angle_deg", 360.0) <= 0:
            raise ValueError("circular_pattern angle_deg must be positive")
    if operation == "mirror" and not any(s["kind"] == "entity" and s["type"] == "PLANE" for s in selectors):
        raise ValueError("mirror requires a reviewed PLANE entity selector")
    if operation in {"basic_hole", "countersink_hole", "counterbore_hole"}:
        selectors = apply_hole_center_to_plane_selectors(selectors, params)
    return {"operation": operation, "operation_role": OPERATION_ROLE_BY_OPERATION[operation], "selectors": selectors, "parameters": params}


def find_feature(model: Any, query: str) -> Any:
    current = read(model, "FirstFeature")
    matches = []
    seen: set[int] = set()
    while current is not None and not isinstance(current, dict):
        ident = id(current)
        if ident in seen:
            break
        seen.add(ident)
        name = read(current, "Name")
        select_name = read(current, "GetNameForSelection")
        if query in {name, select_name}:
            matches.append(current)
        current = read(current, "GetNextFeature")
    if not matches:
        raise RuntimeError(f"Feature not found by exact name: {query}")
    if len(matches) > 1:
        raise RuntimeError(f"Feature name is ambiguous: {query}")
    return matches[0]


def clear_selection(model: Any) -> Any:
    extension = read(model, "Extension")
    if extension is not None and not isinstance(extension, dict):
        result = read(extension, "SelectByID2", "", "", 0, 0, 0, False, 0, None, 0)
        if not isinstance(result, dict):
            return result
    return read(model, "ClearSelection2", True)


def apply_selector(model: Any, selector: dict[str, Any]) -> dict[str, Any]:
    if selector["kind"] == "feature":
        feature = find_feature(model, selector["name"])
        selected = read(feature, "Select2", selector["append"], selector["mark"])
        return {"selector": selector, "ok": bool(selected), "method": "Feature.Select2", "raw": selected}
    extension = read(model, "Extension")
    if extension is None or isinstance(extension, dict):
        raise RuntimeError("Model.Extension is unavailable; cannot select named entity.")
    point = selector["point"]
    selected = read(
        extension,
        "SelectByID2",
        selector["name"],
        selector["type"],
        point["x"],
        point["y"],
        point["z"],
        selector["append"],
        selector["mark"],
        None,
        0,
    )
    return {"selector": selector, "ok": bool(selected), "method": "Extension.SelectByID2", "raw": selected}


def invoke_first(target: Any, candidates: list[tuple[str, tuple[Any, ...]]]) -> dict[str, Any]:
    errors = []
    for name, args in candidates:
        try:
            member = getattr(target, name)
            result = member(*args)
            if result is not None:
                return {"method": name, "ok": True, "raw": value_of(result)}
            errors.append({"method": name, "error": "returned None"})
        except Exception as exc:
            errors.append({"method": name, "error": f"{type(exc).__name__}: {exc}"})
    return {"ok": False, "errors": errors}


def point_params(params: dict[str, Any]) -> dict[str, float]:
    center = params.get("center") or {}
    if not isinstance(center, dict):
        raise ValueError("center must be an object with x/y/z")
    return {
        "x": float(center.get("x", params.get("x", 0.0))),
        "y": float(center.get("y", params.get("y", 0.0))),
        "z": float(center.get("z", params.get("z", 0.0))),
    }


def reviewed_feature_name(params: dict[str, Any]) -> str | None:
    return str(params.get("feature_name") or params.get("name") or "").strip() or None


def apply_hole_center_to_plane_selectors(selectors: list[dict[str, Any]], params: dict[str, Any]) -> list[dict[str, Any]]:
    center = point_params(params)
    result: list[dict[str, Any]] = []
    for selector in selectors:
        updated = dict(selector)
        if updated["kind"] == "entity" and updated["type"] in {"PLANE", "FACE"}:
            updated["point"] = dict(center)
        result.append(updated)
    return result


def sketch_manager_for(model: Any) -> Any:
    sketch_manager = read(model, "SketchManager")
    if sketch_manager is None or isinstance(sketch_manager, dict):
        raise RuntimeError("Model.SketchManager is unavailable.")
    return sketch_manager


def start_reviewed_sketch(model: Any) -> dict[str, Any]:
    sketch_manager = sketch_manager_for(model)
    opened = read(sketch_manager, "InsertSketch", True)
    return {"sketch_manager": sketch_manager, "opened": opened}


def finish_cut(model: Any, sketch_context: dict[str, Any], depth_m: float, through_all: bool = False, feature_name: str | None = None) -> dict[str, Any]:
    sketch_manager = sketch_context["sketch_manager"]
    closed = read(sketch_manager, "InsertSketch", True)
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable.")
    end_condition = 1 if through_all else 0
    cut = invoke_first(feature_manager, [
        ("FeatureCut3", (True, False, False, end_condition, 0, depth_m, depth_m, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)),
        ("FeatureCut2", (True, False, False, end_condition, 0, depth_m, depth_m, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0)),
    ])
    cut = apply_feature_name(cut, feature_name)
    return {"closed_sketch": closed, "cut": cut}


def execute_basic_hole(model: Any, params: dict[str, Any]) -> dict[str, Any]:
    sketch_context = start_reviewed_sketch(model)
    sketch_manager = sketch_context["sketch_manager"]
    center = point_params(params)
    diameter_m = float(params.get("diameter_m", mm_to_m(params.get("diameter_mm", 0))))
    depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
    feature_name = reviewed_feature_name(params)
    circle = read(sketch_manager, "CreateCircleByRadius", center["x"], center["y"], center["z"], diameter_m / 2.0)
    cut = finish_cut(model, sketch_context, depth_m, bool(params.get("through_all")), feature_name)
    return {"ok": bool((cut.get("cut") or {}).get("ok")), "feature_name": feature_name, "sketch": {"opened": sketch_context["opened"], "circle": circle}, **cut}


def hole_metadata(params: dict[str, Any], variant: str) -> dict[str, Any]:
    metadata = {
        "variant": variant,
        "diameter_m": float(params.get("diameter_m", mm_to_m(params.get("diameter_mm", 0)))),
        "depth_m": float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0)))),
        "through_all": bool(params.get("through_all")),
        "center": point_params(params),
    }
    if variant == "countersink":
        metadata["countersink_diameter_m"] = float(params.get("countersink_diameter_m", mm_to_m(params.get("countersink_diameter_mm", 0))))
        metadata["countersink_angle_deg"] = float(params.get("countersink_angle_deg", 0))
    if variant == "counterbore":
        metadata["counterbore_diameter_m"] = float(params.get("counterbore_diameter_m", mm_to_m(params.get("counterbore_diameter_mm", 0))))
        metadata["counterbore_depth_m"] = float(params.get("counterbore_depth_m", mm_to_m(params.get("counterbore_depth_mm", 0))))
    return metadata


def hole_wizard_args(metadata: dict[str, Any]) -> tuple[Any, ...]:
    variant_code = {"basic": 0, "counterbore": 1, "countersink": 2}[metadata["variant"]]
    diameter_m = metadata["diameter_m"]
    depth_m = metadata["depth_m"]
    head_diameter_m = metadata.get("counterbore_diameter_m") or metadata.get("countersink_diameter_m") or -1
    head_depth_m = metadata.get("counterbore_depth_m") or -1
    countersink_angle_rad = float(metadata.get("countersink_angle_deg", 118.0)) * 3.141592653589793 / 180.0
    return (
        variant_code,
        8,
        139,
        "Ansi Metric",
        0,
        diameter_m,
        head_diameter_m,
        head_depth_m,
        0,
        depth_m,
        0,
        1,
        countersink_angle_rad,
        0,
        0,
        0,
        -1,
        -1,
        -1,
        "",
        False,
        True,
        True,
        True,
        True,
        False,
    )


def execute_hole_wizard(model: Any, params: dict[str, Any], variant: str) -> dict[str, Any]:
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable.")
    metadata = hole_metadata(params, variant)
    wizard_call = invoke_first(feature_manager, [
        ("HoleWizard5", hole_wizard_args(metadata)),
    ])
    feature_name = reviewed_feature_name(params)
    wizard_call = apply_feature_name(wizard_call, feature_name)
    return {
        "ok": bool(wizard_call.get("ok")),
        "feature_name": feature_name,
        "hole_variant": variant,
        "hole_metadata": metadata,
        "wizard_call": wizard_call,
    }


def execute_slot_cut(model: Any, params: dict[str, Any]) -> dict[str, Any]:
    sketch_context = start_reviewed_sketch(model)
    sketch_manager = sketch_context["sketch_manager"]
    center = point_params(params)
    length_m = float(params.get("length_m", mm_to_m(params.get("length_mm", 0))))
    width_m = float(params.get("width_m", mm_to_m(params.get("width_mm", 0))))
    depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
    feature_name = reviewed_feature_name(params)
    half_line = (length_m - width_m) / 2.0
    slot = invoke_first(sketch_manager, [
        ("CreateStraightSlot", (center["x"] - half_line, center["y"], center["z"], center["x"] + half_line, center["y"], center["z"], width_m / 2.0)),
        ("CreateSketchSlot", (0, 0, center["x"] - half_line, center["y"], center["z"], center["x"] + half_line, center["y"], center["z"], width_m / 2.0, 0, 0, 0, 1, False)),
    ])
    cut = finish_cut(model, sketch_context, depth_m, bool(params.get("through_all")), feature_name)
    return {"ok": bool((cut.get("cut") or {}).get("ok")), "feature_name": feature_name, "sketch": {"opened": sketch_context["opened"], "slot": slot}, **cut}


def execute_pocket_cut(model: Any, params: dict[str, Any]) -> dict[str, Any]:
    sketch_context = start_reviewed_sketch(model)
    sketch_manager = sketch_context["sketch_manager"]
    center = point_params(params)
    width_m = float(params.get("width_m", mm_to_m(params.get("width_mm", 0))))
    height_m = float(params.get("height_m", mm_to_m(params.get("height_mm", 0))))
    depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
    feature_name = reviewed_feature_name(params)
    rectangle = invoke_first(sketch_manager, [
        ("CreateCenterRectangle", (center["x"], center["y"], center["z"], center["x"] + width_m / 2.0, center["y"] + height_m / 2.0, center["z"])),
        ("CreateCornerRectangle", (center["x"] - width_m / 2.0, center["y"] - height_m / 2.0, center["z"], center["x"] + width_m / 2.0, center["y"] + height_m / 2.0, center["z"])),
    ])
    cut = finish_cut(model, sketch_context, depth_m, bool(params.get("through_all")), feature_name)
    return {"ok": bool((cut.get("cut") or {}).get("ok")), "feature_name": feature_name, "sketch": {"opened": sketch_context["opened"], "rectangle": rectangle}, **cut}


def execute_extrude_cut(model: Any, params: dict[str, Any]) -> dict[str, Any]:
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable.")
    depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
    through_all = bool(params.get("through_all"))
    feature_name = reviewed_feature_name(params)
    end_condition = 1 if through_all else 0
    cut = invoke_first(feature_manager, [
        ("FeatureCut3", (True, False, False, end_condition, 0, depth_m, depth_m, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)),
        ("FeatureCut2", (True, False, False, end_condition, 0, depth_m, depth_m, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0)),
    ])
    cut = apply_feature_name(cut, feature_name)
    return {"ok": bool(cut.get("ok")), "cut": cut, "depth_m": depth_m, "through_all": through_all, "feature_name": feature_name}


def apply_feature_name(call_result: dict[str, Any], feature_name: str | None) -> dict[str, Any]:
    raw = call_result.get("raw")
    if feature_name and hasattr(raw, "_oleobj_"):
        try:
            setattr(raw, "Name", feature_name)
            call_result = {**call_result, "assigned_feature_name": feature_name}
        except Exception as exc:
            call_result = {**call_result, "assigned_feature_name_error": f"{type(exc).__name__}: {exc}"}
    return call_result


def execute_extrude_boss(model: Any, params: dict[str, Any]) -> dict[str, Any]:
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable.")
    depth_m = float(params.get("depth_m", mm_to_m(params.get("depth_mm", 0))))
    through_all = bool(params.get("through_all"))
    end_condition = 1 if through_all else 0
    feature_name = reviewed_feature_name(params)
    boss = invoke_first(feature_manager, [
        ("FeatureExtrusion3", (True, False, False, end_condition, 0, depth_m, depth_m, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)),
        ("FeatureExtrusion2", (True, False, False, end_condition, 0, depth_m, depth_m, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0)),
        ("FeatureExtrusion", (True, False, False, end_condition, 0, depth_m, depth_m, False, False, False, False, 0, 0)),
    ])
    boss = apply_feature_name(boss, feature_name)
    return {"ok": bool(boss.get("ok")), "boss": boss, "depth_m": depth_m, "through_all": through_all, "feature_name": feature_name}


def execute_revolve(model: Any, plan: dict[str, Any], cut: bool) -> dict[str, Any]:
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable.")
    params = plan["parameters"]
    angle_deg = float(params.get("angle_deg", 360.0))
    angle_rad = angle_deg * 3.141592653589793 / 180.0
    reverse_direction = bool(params.get("reverse_direction"))
    thin_feature = bool(params.get("thin_feature"))
    feature_name = reviewed_feature_name(params)
    candidates = [
        ("FeatureRevolveCut2" if cut else "FeatureRevolve2", (True, reverse_direction, False, False, False, False, angle_rad, 0.0, thin_feature, 0.0, 0.0, 0, 0, True, True, True)),
        ("FeatureRevolveCut" if cut else "FeatureRevolve", (True, reverse_direction, angle_rad)),
    ]
    call = invoke_first(feature_manager, candidates)
    call = apply_feature_name(call, feature_name)
    axis_selector = next(iter(selector_names(plan, kind="entity", select_type="AXIS")), None)
    key = "revolve_cut" if cut else "revolve"
    return {
        "ok": bool(call.get("ok")),
        key: call,
        "axis_selector": axis_selector,
        "profile_selectors": selector_names(plan, kind="entity", select_type="SKETCH"),
        "angle_deg": angle_deg,
        "angle_rad": angle_rad,
        "reverse_direction": reverse_direction,
        "thin_feature": thin_feature,
        "feature_name": feature_name,
    }


def selector_names(plan: dict[str, Any], *, kind: str | None = None, select_type: str | None = None) -> list[str]:
    result = []
    for selector in plan["selectors"]:
        if kind is not None and selector["kind"] != kind:
            continue
        if select_type is not None and selector.get("type") != select_type:
            continue
        result.append(selector["name"])
    return result


def pattern_result(call_result: dict[str, Any], evidence: dict[str, Any], feature_name: str | None = None) -> dict[str, Any]:
    call_result = apply_feature_name(call_result, feature_name)
    return {"ok": bool(call_result.get("ok")), "call": call_result, "pattern_evidence": evidence, "feature_name": feature_name}


def execute_operation(model: Any, plan: dict[str, Any]) -> dict[str, Any]:
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable.")
    operation = plan["operation"]
    params = plan["parameters"]
    if operation == "fillet":
        radius_m = float(params.get("radius_m", mm_to_m(params.get("radius_mm", 0))))
        feature_name = reviewed_feature_name(params)
        fillet = invoke_first(feature_manager, [
            ("FeatureFillet3", (195, radius_m, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, True, True, True)),
            ("FeatureFillet2", (195, radius_m, 0, 0, 0, 0, 0, 0, True, True, True)),
            ("InsertFeatureFillet", (radius_m,)),
        ])
        fillet = apply_feature_name(fillet, feature_name)
        return {"ok": bool(fillet.get("ok")), "fillet": fillet, "radius_m": radius_m, "feature_name": feature_name}
    if operation == "chamfer":
        distance_m = float(params.get("distance_m", mm_to_m(params.get("distance_mm", 0))))
        angle_rad = float(params.get("angle_deg", 45.0)) * 3.141592653589793 / 180.0
        feature_name = reviewed_feature_name(params)
        chamfer = invoke_first(feature_manager, [
            ("FeatureChamfer3", (4, distance_m, angle_rad, 0, 0, 0, True, True)),
            ("FeatureChamfer2", (4, distance_m, angle_rad, 0, 0, True, True)),
            ("InsertFeatureChamfer", (4, distance_m, angle_rad)),
        ])
        chamfer = apply_feature_name(chamfer, feature_name)
        return {"ok": bool(chamfer.get("ok")), "chamfer": chamfer, "distance_m": distance_m, "angle_rad": angle_rad, "feature_name": feature_name}
    if operation == "basic_hole":
        return execute_basic_hole(model, params)
    if operation == "countersink_hole":
        return execute_hole_wizard(model, params, "countersink")
    if operation == "counterbore_hole":
        return execute_hole_wizard(model, params, "counterbore")
    if operation == "extrude_boss":
        return execute_extrude_boss(model, params)
    if operation == "extrude_cut":
        return execute_extrude_cut(model, params)
    if operation == "revolve_boss":
        return execute_revolve(model, plan, cut=False)
    if operation == "revolved_cut":
        return execute_revolve(model, plan, cut=True)
    if operation == "slot_cut":
        return execute_slot_cut(model, params)
    if operation == "pocket_cut":
        return execute_pocket_cut(model, params)
    if operation == "linear_pattern":
        count = as_int(params, "count", 2)
        spacing_m = as_float(params, "spacing_m", mm_to_m(params.get("spacing_mm", 0)))
        feature_name = reviewed_feature_name(params)
        call = invoke_first(feature_manager, [
            ("FeatureLinearPattern5", (count, 1, spacing_m, 0.0, False, False, "", "", False, False, False, False, False, False)),
            ("FeatureLinearPattern4", (count, 1, spacing_m, 0.0, False, False, "", "", False, False, False, False)),
            ("InsertFeatureLinearPattern", (count, spacing_m)),
        ])
        return pattern_result(call, {
            "pattern_type": "linear",
            "seed_features": selector_names(plan, kind="feature"),
            "direction_selector": next(iter(selector_names(plan, kind="entity")), None),
            "expected_instance_count": count,
            "spacing_m": spacing_m,
        }, feature_name)
    if operation == "circular_pattern":
        count = as_int(params, "count", 2)
        angle_deg = as_float(params, "angle_deg", 360.0)
        angle_rad = angle_deg * 3.141592653589793 / 180.0
        feature_name = reviewed_feature_name(params)
        call = invoke_first(feature_manager, [
            ("FeatureCircularPattern5", (count, angle_rad, False, "", False, False, False)),
            ("FeatureCircularPattern4", (count, angle_rad, False, "", False, False)),
            ("InsertFeatureCircularPattern", (count, angle_rad)),
        ])
        return pattern_result(call, {
            "pattern_type": "circular",
            "seed_features": selector_names(plan, kind="feature"),
            "axis_selector": next(iter(selector_names(plan, kind="entity", select_type="AXIS")), None) or next(iter(selector_names(plan, kind="entity")), None),
            "expected_instance_count": count,
            "angle_deg": angle_deg,
            "angle_rad": angle_rad,
        }, feature_name)
    if operation == "mirror":
        feature_name = reviewed_feature_name(params)
        call = invoke_first(feature_manager, [
            ("InsertMirrorFeature2", (False, False, False, False)),
            ("InsertMirrorFeature", (False, False, False)),
            ("FeatureMirror", (False, False)),
        ])
        return pattern_result(call, {
            "pattern_type": "mirror",
            "seed_features": selector_names(plan, kind="feature"),
            "mirror_plane_selector": next(iter(selector_names(plan, kind="entity", select_type="PLANE")), None) or next(iter(selector_names(plan, kind="entity")), None),
            "expected_instance_count": 2,
        }, feature_name)
    raise ValueError(f"Unsupported operation: {operation}")


def execute(model: Any, plan: dict[str, Any]) -> dict[str, Any]:
    clear_result = clear_selection(model)
    selection_results = [apply_selector(model, selector) for selector in plan["selectors"]]
    if not all(item["ok"] for item in selection_results):
        return {"ok": False, "clear_selection": clear_result, "selection_results": selection_results, "operation_result": None}
    operation_result = execute_operation(model, plan)
    return {
        "ok": bool(operation_result.get("ok")),
        "operation": plan["operation"],
        "operation_role": plan["operation_role"],
        "clear_selection": clear_result,
        "selection_results": selection_results,
        "operation_result": operation_result,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="JSON spec containing operation, selectors, and parameters")
    parser.add_argument("--model", default=None)
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/part_feature_execute.json")
    args = parser.parse_args()
    spec = load_spec(args.spec)
    plan = validate_spec(spec)
    result: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "spec": str(Path(args.spec).resolve()),
        "operation": plan["operation"],
        "operation_role": plan["operation_role"],
        "dry_run": args.dry_run,
        "execution_plan": plan,
        "connected": False,
    }
    if not args.dry_run:
        pythoncom_mod, _win32_client = require_pywin32()
        pythoncom_mod.CoInitialize()
        sw, started = attach(args.start)
        model = open_or_active(sw, args.model)
        before_title = read(model, "GetTitle")
        execution = execute(model, plan)
        rebuild_result = read(model, "ForceRebuild3", False)
        save_result = save_model(model) if args.save else None
        result.update({
            "connected": True,
            "started_by_probe": started,
            "document_title": before_title,
            "document_path": read(model, "GetPathName"),
            "execution": execution,
            "rebuild_result": rebuild_result,
            "saved": args.save,
            "save_result": save_result,
            "ok": bool(execution.get("ok")),
        })
    else:
        result["ok"] = True
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
