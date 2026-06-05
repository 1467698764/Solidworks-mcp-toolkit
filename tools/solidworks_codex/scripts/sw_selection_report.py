"""Report current SolidWorks selection set for safe mate macro workflows."""
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

# Partial swSelectType_e map; unknown values are still reported numerically.
SELECT_TYPES = {
    1: "EDGES",
    2: "FACES",
    3: "VERTICES",
    4: "DATUMPLANES",
    5: "DATUMAXES",
    6: "DATUMPOINTS",
    7: "OLEITEMS",
    8: "ATTRIBUTES",
    9: "SKETCHES",
    10: "SKETCHSEGS",
    11: "SKETCHPOINTS",
    12: "DRAWINGVIEWS",
    13: "GTOLS",
    14: "DIMENSIONS",
    15: "NOTES",
    16: "SECTIONLINES",
    17: "DETAILCIRCLES",
    18: "COMPONENTS",
    19: "MATES",
    20: "BODYFEATURES",
    21: "REFCURVES",
    22: "EXTSKETCHSEGS",
    23: "EXTSKETCHPOINTS",
}


def val(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if hasattr(value, "_oleobj_"):
        return value
    if isinstance(value, (list, tuple)):
        return [val(v) for v in value]
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


def object_summary(obj: Any) -> dict[str, Any]:
    if obj is None or isinstance(obj, dict):
        return {"value": obj}
    summary = {"dispatch": str(obj)}
    for name in ("Name", "Name2", "GetName", "GetTypeName2", "GetPathName"):
        got = read(obj, name)
        if got is not None and not (isinstance(got, dict) and "error" in got):
            summary[name] = got
    return summary


def persist_reference_value(model: Any, obj: Any) -> list[int] | None:
    extension = getattr(model, "Extension", None)
    if extension is None:
        extension = read(model, "Extension")
    func = getattr(extension, "GetPersistReference3", None)
    if not callable(func):
        return None
    try:
        raw = func(obj)
    except Exception:
        return None
    if raw in (None, ""):
        return None
    values = raw if isinstance(raw, (list, tuple, bytes, bytearray)) else val(raw)
    if isinstance(values, (bytes, bytearray)):
        return [int(item) for item in values]
    if isinstance(values, (list, tuple)):
        try:
            return [int(item) for item in values]
        except (TypeError, ValueError):
            return None
    return None


def identity_member(obj: Any, names: tuple[str, ...]) -> Any:
    for name in names:
        got = read(obj, name)
        if got is not None and not (isinstance(got, dict) and "error" in got):
            return got
    return None


def native_identity(model: Any, obj: Any, comp: Any) -> dict[str, Any]:
    summary = object_summary(obj)
    component_summary = object_summary(comp)
    component_name = component_summary.get("Name2") or component_summary.get("Name") or component_summary.get("GetName")
    component_path = component_summary.get("GetPathName")
    select_name = identity_member(obj, ("GetNameForSelection", "GetName", "Name"))
    return {
        "persistent_reference": persist_reference_value(model, obj),
        "tracking_id": identity_member(obj, ("GetTrackingID", "GetTrackingId", "TrackingID")),
        "select_name": select_name,
        "component": component_name,
        "component_path": component_path,
        "object_type": summary.get("GetTypeName2"),
        "resolution_order": ["persistent_reference", "tracking_id", "select_name", "geometry_signature_fallback"],
    }


def report(start: bool) -> dict[str, Any]:
    pythoncom_mod, _win32_client = require_pywin32()
    pythoncom_mod.CoInitialize()
    sw, started = attach(start)
    model = read(sw, "ActiveDoc")
    if model is None or isinstance(model, dict):
        raise RuntimeError("No active SolidWorks document. Open an assembly/part and preselect entities.")
    sel_mgr = read(model, "SelectionManager")
    if sel_mgr is None or isinstance(sel_mgr, dict):
        raise RuntimeError(f"SelectionManager unavailable: {sel_mgr}")
    count = read(sel_mgr, "GetSelectedObjectCount2", -1)
    selections = []
    if isinstance(count, int):
        for i in range(1, count + 1):
            typ = read(sel_mgr, "GetSelectedObjectType3", i, -1)
            obj = read(sel_mgr, "GetSelectedObject6", i, -1)
            mark = read(sel_mgr, "GetSelectedObjectMark", i)
            comp = read(sel_mgr, "GetSelectedObjectsComponent4", i, -1)
            selections.append({
                "index": i,
                "type_code": typ,
                "type": SELECT_TYPES.get(typ, f"UNKNOWN:{typ}"),
                "mark": mark,
                "object": object_summary(obj),
                "component": object_summary(comp),
                "native_identity": native_identity(model, obj, comp),
            })
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "document_title": read(model, "GetTitle"),
        "document_path": read(model, "GetPathName"),
        "document_type": read(model, "GetType"),
        "selection_count": count,
        "selections": selections,
        "mate_macro_ready": count == 2,
        "recommendation": "Exactly two selected entities are recommended before mate-macro." if count != 2 else "Selection count is suitable for mate-macro; still review entity types before running generated VBA.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/selection_report.json")
    args = parser.parse_args()
    result = report(args.start)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
