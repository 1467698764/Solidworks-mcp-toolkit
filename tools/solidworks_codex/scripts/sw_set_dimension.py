"""Safely set a SolidWorks dimension by full parameter name.

This is intentionally narrow: it attaches to a running SolidWorks instance by default,
optionally opens a specified model, sets one dimension in meters, rebuilds, and writes a
JSON report. Use --save only after a backup has been created.
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
except ModuleNotFoundError:  # offline tests can import helpers without pywin32
    pythoncom = None  # type: ignore[assignment]
    win32com = None  # type: ignore[assignment]


def require_pywin32() -> tuple[Any, Any]:
    if pythoncom is None or win32com is None:
        raise RuntimeError(
            "SolidWorks live COM commands require pywin32. "
            "Install pywin32 or set SWCODEX_PYTHON to a Python that can import pythoncom and win32com.client."
        )
    return pythoncom, win32com.client


def safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_oleobj_"):
        return value
    if isinstance(value, (list, tuple)):
        return [safe_value(v) for v in value]
    return str(value)


def read_member(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        if args:
            if callable(member):
                return safe_value(member(*args))
            return {"error": f"member {name} is a property, arguments were provided"}
        if hasattr(member, "_oleobj_"):
            return member
        if callable(member):
            return safe_value(member())
        return safe_value(member)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def attach_solidworks(allow_start: bool) -> tuple[Any, bool]:
    _pythoncom, win32_client = require_pywin32()
    try:
        return win32_client.GetActiveObject("SldWorks.Application"), False
    except Exception as attach_error:
        if not allow_start:
            raise RuntimeError(
                "SolidWorks is not running. Start SolidWorks and rerun, or pass --start to launch it."
            ) from attach_error
        sw = win32_client.Dispatch("SldWorks.Application")
        try:
            sw.Visible = True
        except Exception:
            pass
        return sw, True


def open_model_if_requested(sw: Any, path: str | None) -> Any:
    if not path:
        model = read_member(sw, "ActiveDoc")
        if model is None or isinstance(model, dict):
            raise RuntimeError("No active SolidWorks document. Open a document or pass --model.")
        return model

    model_path = str(Path(path).resolve())
    suffix = Path(model_path).suffix.lower()
    doc_type = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}.get(suffix)
    if doc_type is None:
        raise ValueError(f"Unsupported SolidWorks file type: {model_path}")
    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(model_path, doc_type, 0, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed for {model_path}; errors={errors.value}, warnings={warnings.value}")
    return model



def save_model(model: Any) -> dict[str, Any]:
    pythoncom_mod, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    ok = model.Save3(1, errors, warnings)
    return {"ok": bool(ok), "errors": getattr(errors, "value", errors), "warnings": getattr(warnings, "value", warnings)}


def set_dimension(model: Any, dimension_name: str, value_m: float, save: bool) -> dict[str, Any]:
    param = read_member(model, "Parameter", dimension_name)
    if param is None or isinstance(param, dict):
        raise RuntimeError(f"Dimension/parameter not found: {dimension_name}; result={param}")

    old_value = read_member(param, "SystemValue")
    param.SystemValue = value_m
    rebuild_result = read_member(model, "ForceRebuild3", False)
    new_value = read_member(param, "SystemValue")

    save_result: Any = None
    if save:
        save_result = save_model(model)

    return {
        "dimension": dimension_name,
        "old_system_value_m": old_value,
        "new_system_value_m": new_value,
        "requested_system_value_m": value_m,
        "rebuild_result": rebuild_result,
        "saved": save,
        "save_result": save_result,
        "document_title": read_member(model, "GetTitle"),
        "document_path": read_member(model, "GetPathName"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dimension", required=True, help="Full SolidWorks dimension/parameter name, e.g. D1@Sketch1@Part.SLDPRT")
    parser.add_argument("--value-m", required=True, type=float, help="New SystemValue in meters")
    parser.add_argument("--model", default=None, help="Optional model path to open before editing")
    parser.add_argument("--start", action="store_true", help="Allow launching SolidWorks if it is not running")
    parser.add_argument("--save", action="store_true", help="Save after setting the dimension; create a backup first")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/set_dimension.json")
    args = parser.parse_args()

    pythoncom_mod, _win32_client = require_pywin32()
    pythoncom_mod.CoInitialize()
    sw, started_by_probe = attach_solidworks(args.start)
    model = open_model_if_requested(sw, args.model)
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started_by_probe,
        "operation": set_dimension(model, args.dimension, args.value_m, args.save),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
