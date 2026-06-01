"""Export the active or specified SolidWorks document to a target file."""
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


def read_member(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        if args:
            if callable(member):
                value = member(*args)
            else:
                return {"error": f"member {name} is a property, arguments were provided"}
        elif hasattr(member, "_oleobj_"):
            return member
        elif callable(member):
            value = member()
        else:
            value = member
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if hasattr(value, "_oleobj_"):
            return value
        if isinstance(value, (list, tuple)):
            return [read_member_value(v) for v in value]
        return str(value)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def read_member_value(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if hasattr(value, "_oleobj_"):
        return value
    if isinstance(value, (list, tuple)):
        return [read_member_value(v) for v in value]
    return str(value)


def attach(allow_start: bool) -> tuple[Any, bool]:
    _pythoncom, win32_client = require_pywin32()
    try:
        return win32_client.GetActiveObject("SldWorks.Application"), False
    except Exception as exc:
        if not allow_start:
            raise RuntimeError("SolidWorks is not running. Start it or pass --start.") from exc
        sw = win32_client.Dispatch("SldWorks.Application")
        sw.Visible = True
        return sw, True


def open_or_active(sw: Any, model_path: str | None) -> Any:
    if not model_path:
        model = read_member(sw, "ActiveDoc")
        if model is None or isinstance(model, dict):
            raise RuntimeError("No active SolidWorks document. Open a document or pass --model.")
        return model
    path = str(Path(model_path).resolve())
    doc_type = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}.get(Path(path).suffix.lower())
    if doc_type is None:
        raise ValueError(f"Unsupported SolidWorks file type: {path}")
    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(path, doc_type, 0, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed: errors={errors.value}, warnings={warnings.value}, path={path}")
    return model


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--target", required=True)
    parser.add_argument("--out", default="tools/solidworks_codex/reports/export.json")
    args = parser.parse_args()
    pythoncom_mod, _win32_client = require_pywin32()
    pythoncom_mod.CoInitialize()
    sw, started = attach(args.start)
    model = open_or_active(sw, args.model)
    target = Path(args.target).resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    errors = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32com.client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    success = read_member(model, "SaveAs3", str(target), 0, 2)
    # Some versions expose SaveAs3 without byref error outputs; keep result generic.
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "document_title": read_member(model, "GetTitle"),
        "document_path": read_member(model, "GetPathName"),
        "target": str(target),
        "target_suffix": target.suffix.lower(),
        "success": success,
        "errors": getattr(errors, "value", None),
        "warnings": getattr(warnings, "value", None),
        "exists_after": target.exists(),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
