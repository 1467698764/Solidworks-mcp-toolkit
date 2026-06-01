"""Report mass properties for the active or specified SolidWorks document."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pythoncom
import win32com.client


def read_member(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        value = member(*args) if callable(member) else member
        if isinstance(value, (str, int, float, bool)) or value is None:
            return value
        if isinstance(value, (list, tuple)):
            return list(value)
        return str(value)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def attach(allow_start: bool) -> tuple[Any, bool]:
    try:
        return win32com.client.GetActiveObject("SldWorks.Application"), False
    except Exception as exc:
        if not allow_start:
            raise RuntimeError("SolidWorks is not running. Start it or pass --start.") from exc
        sw = win32com.client.Dispatch("SldWorks.Application")
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


def mass_properties(model: Any) -> dict[str, Any]:
    ext = read_member(model, "Extension")
    if ext is None or isinstance(ext, dict):
        return {"available": False, "error": ext}
    mp = read_member(ext, "CreateMassProperty")
    if mp is None or isinstance(mp, dict):
        return {"available": False, "error": mp}
    return {
        "available": True,
        "mass_kg": read_member(mp, "Mass"),
        "volume_m3": read_member(mp, "Volume"),
        "surface_area_m2": read_member(mp, "SurfaceArea"),
        "center_of_mass_m": read_member(mp, "CenterOfMass"),
        "principal_moments": read_member(mp, "PrincipalMomentsOfInertia"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--out", default="tools/solidworks_codex/reports/mass_properties.json")
    args = parser.parse_args()
    pythoncom.CoInitialize()
    sw, started = attach(args.start)
    model = open_or_active(sw, args.model)
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "document_title": read_member(model, "GetTitle"),
        "document_path": read_member(model, "GetPathName"),
        "mass_properties": mass_properties(model),
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
