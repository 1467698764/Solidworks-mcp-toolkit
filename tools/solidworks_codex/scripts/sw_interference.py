"""Run SolidWorks assembly interference detection and emit JSON.

This is a conservative COM wrapper. SolidWorks API versions differ, so if the direct
InterferenceDetectionManager path is unavailable the script reports a clear unavailable
state instead of pretending success.
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


def val(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_oleobj_"):
        return value
    if isinstance(value, (list, tuple)):
        return [val(v) for v in value]
    return str(value)



def json_safe(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_oleobj_"):
        return str(value)
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [json_safe(v) for v in value]
    if isinstance(value, dict):
        return {str(k): json_safe(v) for k, v in value.items()}
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


def active_assembly(sw: Any) -> Any:
    model = read(sw, "ActiveDoc")
    if model is None or isinstance(model, dict):
        raise RuntimeError("No active SolidWorks document. Open an assembly first.")
    doc_type = read(model, "GetType")
    if doc_type != 2:
        raise RuntimeError(f"Active document is not an assembly. GetType={doc_type}")
    return model


def detect(asm: Any) -> dict[str, Any]:
    manager = read(asm, "InterferenceDetectionManager")
    if manager is None or isinstance(manager, dict):
        return {"available": False, "error": manager, "interferences": []}
    # Best-effort generic sequence. Some versions expose these as properties/methods.
    treat_coincident = read(manager, "TreatCoincidenceAsInterference")
    try:
        setattr(manager, "TreatCoincidenceAsInterference", False)
    except Exception:
        pass
    result = read(manager, "GetInterferences")
    interferences = []
    if isinstance(result, list):
        for item in result:
            interferences.append({"raw": val(item)})
    elif result is None:
        interferences = []
    elif isinstance(result, dict):
        return {"available": False, "error": result, "treat_coincidence_previous": treat_coincident, "interferences": []}
    else:
        interferences.append({"raw": result})
    return {"available": True, "count": len(interferences), "treat_coincidence_previous": treat_coincident, "interferences": interferences}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/interference.json")
    args = parser.parse_args()
    pythoncom_mod, _win32_client = require_pywin32()
    pythoncom_mod.CoInitialize()
    sw, started = attach(args.start)
    asm = active_assembly(sw)
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "assembly_title": read(asm, "GetTitle"),
        "assembly_path": read(asm, "GetPathName"),
        "interference": detect(asm),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    result = json_safe(result)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
