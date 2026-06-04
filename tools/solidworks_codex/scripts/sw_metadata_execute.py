"""Execute reviewed SolidWorks material and custom-property metadata writes."""
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

CUSTOM_PROPERTY_TEXT = 30
CUSTOM_PROPERTY_ADD_OR_REPLACE = 1


def require_pywin32() -> tuple[Any, Any]:
    if pythoncom is None or win32com is None:
        raise RuntimeError(
            "SolidWorks live COM commands require pywin32. "
            "Install pywin32 or set SWCODEX_PYTHON to a Python that can import pythoncom and win32com.client."
        )
    return pythoncom, win32com.client


def val(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_oleobj_"):
        return value
    if isinstance(value, (list, tuple)):
        return [val(item) for item in value]
    return str(value)


def read(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        if args:
            if callable(member):
                return val(member(*args))
            return {"error": f"member {name} is a property, arguments were provided"}
        if hasattr(member, "_oleobj_"):
            return member
        if callable(member):
            return val(member())
        return val(member)
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
            raise RuntimeError("No active SolidWorks document. Open a model or pass --model.")
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
        raise ValueError("metadata spec must be a JSON object")
    return data


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    material = str(spec.get("material") or "").strip()
    configuration = str(spec.get("configuration") or "").strip()
    database = str(spec.get("material_database") or "").strip()
    properties = spec.get("properties") or spec.get("custom_properties") or {}
    if not isinstance(properties, dict):
        raise ValueError("properties must be a JSON object")
    normalized_properties = {str(key).strip(): str(value) for key, value in properties.items() if str(key).strip()}
    if not material and not normalized_properties:
        raise ValueError("metadata spec requires material or at least one property")
    return {
        "material": material,
        "material_database": database,
        "configuration": configuration,
        "properties": normalized_properties,
    }


def property_manager(model: Any, configuration: str) -> Any:
    extension = read(model, "Extension")
    if extension is None or isinstance(extension, dict):
        raise RuntimeError("Model.Extension is unavailable.")
    manager = read(extension, "CustomPropertyManager", configuration)
    if manager is None or isinstance(manager, dict):
        raise RuntimeError(f"CustomPropertyManager is unavailable for configuration {configuration!r}.")
    return manager


def set_property(manager: Any, name: str, value: str) -> dict[str, Any]:
    add = read(manager, "Add3", name, CUSTOM_PROPERTY_TEXT, value, CUSTOM_PROPERTY_ADD_OR_REPLACE)
    set_result = read(manager, "Set2", name, value)
    return {"name": name, "value": value, "add3": add, "set2": set_result}


def set_material(model: Any, plan: dict[str, Any]) -> dict[str, Any] | None:
    material = plan["material"]
    if not material:
        return None
    result = read(model, "SetMaterialPropertyName2", plan["configuration"], plan["material_database"], material)
    return {"material": material, "configuration": plan["configuration"], "database": plan["material_database"], "result": result}


def execute_metadata(model: Any, plan: dict[str, Any]) -> dict[str, Any]:
    material_result = set_material(model, plan)
    manager = property_manager(model, plan["configuration"])
    property_results = [set_property(manager, name, value) for name, value in plan["properties"].items()]
    return {
        "ok": True,
        "material": material_result,
        "properties": property_results,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="JSON spec containing material and/or properties")
    parser.add_argument("--model", default=None)
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/metadata_execute.json")
    args = parser.parse_args()
    plan = validate_spec(load_spec(args.spec))
    result: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "spec": str(Path(args.spec).resolve()),
        "dry_run": args.dry_run,
        "execution_plan": plan,
        "connected": False,
    }
    if args.dry_run:
        result["ok"] = True
    else:
        pythoncom_mod, _win32_client = require_pywin32()
        pythoncom_mod.CoInitialize()
        sw, started = attach(args.start)
        model = open_or_active(sw, args.model)
        execution = execute_metadata(model, plan)
        rebuild_result = read(model, "ForceRebuild3", False)
        save_result = save_model(model) if args.save else None
        result.update({
            "ok": bool(execution.get("ok")),
            "connected": True,
            "started_by_probe": started,
            "document_title": read(model, "GetTitle"),
            "document_path": read(model, "GetPathName"),
            "execution": execution,
            "rebuild_result": rebuild_result,
            "saved": args.save,
            "save_result": save_result,
        })
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
