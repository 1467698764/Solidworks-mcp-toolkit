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

SUPPORTED_OPERATIONS = {"fillet", "chamfer", "linear_pattern", "circular_pattern", "mirror"}
SELECT_BY_ID_TYPES = {"EDGE", "FACE", "PLANE", "AXIS", "SKETCH", "EXTSKETCHSEGMENT", "EXTSKETCHPOINT"}


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
    aliases = {"linear": "linear_pattern", "circular": "circular_pattern", "edge_fillet": "fillet", "edge_chamfer": "chamfer"}
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
    return {"operation": operation, "selectors": selectors, "parameters": params}


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


def execute_operation(model: Any, plan: dict[str, Any]) -> dict[str, Any]:
    feature_manager = read(model, "FeatureManager")
    if feature_manager is None or isinstance(feature_manager, dict):
        raise RuntimeError("Model.FeatureManager is unavailable.")
    operation = plan["operation"]
    params = plan["parameters"]
    if operation == "fillet":
        radius_m = float(params.get("radius_m", mm_to_m(params.get("radius_mm", 0))))
        return invoke_first(feature_manager, [
            ("FeatureFillet3", (195, radius_m, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, True, True, True)),
            ("FeatureFillet2", (195, radius_m, 0, 0, 0, 0, 0, 0, True, True, True)),
            ("InsertFeatureFillet", (radius_m,)),
        ])
    if operation == "chamfer":
        distance_m = float(params.get("distance_m", mm_to_m(params.get("distance_mm", 0))))
        angle_rad = float(params.get("angle_deg", 45.0)) * 3.141592653589793 / 180.0
        return invoke_first(feature_manager, [
            ("FeatureChamfer3", (4, distance_m, angle_rad, 0, 0, 0, True, True)),
            ("FeatureChamfer2", (4, distance_m, angle_rad, 0, 0, True, True)),
            ("InsertFeatureChamfer", (4, distance_m, angle_rad)),
        ])
    if operation == "linear_pattern":
        count = as_int(params, "count", 2)
        spacing_m = as_float(params, "spacing_m", mm_to_m(params.get("spacing_mm", 0)))
        return invoke_first(feature_manager, [
            ("FeatureLinearPattern5", (count, 1, spacing_m, 0.0, False, False, "", "", False, False, False, False, False, False)),
            ("FeatureLinearPattern4", (count, 1, spacing_m, 0.0, False, False, "", "", False, False, False, False)),
            ("InsertFeatureLinearPattern", (count, spacing_m)),
        ])
    if operation == "circular_pattern":
        count = as_int(params, "count", 2)
        angle_rad = as_float(params, "angle_deg", 360.0) * 3.141592653589793 / 180.0
        return invoke_first(feature_manager, [
            ("FeatureCircularPattern5", (count, angle_rad, False, "", False, False, False)),
            ("FeatureCircularPattern4", (count, angle_rad, False, "", False, False)),
            ("InsertFeatureCircularPattern", (count, angle_rad)),
        ])
    if operation == "mirror":
        return invoke_first(feature_manager, [
            ("InsertMirrorFeature2", (False, False, False, False)),
            ("InsertMirrorFeature", (False, False, False)),
            ("FeatureMirror", (False, False)),
        ])
    raise ValueError(f"Unsupported operation: {operation}")


def execute(model: Any, plan: dict[str, Any]) -> dict[str, Any]:
    clear_result = clear_selection(model)
    selection_results = [apply_selector(model, selector) for selector in plan["selectors"]]
    if not all(item["ok"] for item in selection_results):
        return {"ok": False, "clear_selection": clear_result, "selection_results": selection_results, "operation_result": None}
    operation_result = execute_operation(model, plan)
    return {
        "ok": bool(operation_result.get("ok")),
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
