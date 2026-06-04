"""Change SolidWorks feature state by feature name and emit JSON evidence.

Supported actions: suppress, unsuppress, delete.
Works on the active part/assembly document, or opens a provided model path.
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
            raise RuntimeError("No active SolidWorks document. Open a document or pass --model.")
        return model
    path = str(Path(model_path).resolve())
    doc_type = {".sldprt": 1, ".sldasm": 2, ".slddrw": 3}.get(Path(path).suffix.lower())
    if doc_type is None:
        raise ValueError(f"Unsupported SolidWorks file type: {path}")
    _pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(_pythoncom.VT_BYREF | _pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(_pythoncom.VT_BYREF | _pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(path, doc_type, 0, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed: errors={errors.value}, warnings={warnings.value}, path={path}")
    return model


def feature_name(feature: Any) -> Any:
    name = read(feature, "Name")
    if isinstance(name, str):
        return name
    return read(feature, "GetNameForSelection")


def feature_type(feature: Any) -> Any:
    type_name = read(feature, "GetTypeName2")
    if isinstance(type_name, str):
        return type_name
    return read(feature, "GetTypeName")


def is_suppressed(feature: Any) -> Any:
    for args in ((2, None), (2, []), ()):
        result = read(feature, "IsSuppressed2", *args)
        if not isinstance(result, dict):
            return result
    return read(feature, "IsSuppressed")


def iter_feature_chain(first: Any) -> list[Any]:
    result: list[Any] = []
    seen: set[int] = set()
    current = first
    while current is not None and not isinstance(current, dict):
        ident = id(current)
        if ident in seen:
            break
        seen.add(ident)
        result.append(current)
        sub = read(current, "GetFirstSubFeature")
        result.extend(iter_feature_chain(sub))
        current = read(current, "GetNextFeature")
    return result


def list_features(model: Any) -> list[Any]:
    return iter_feature_chain(read(model, "FirstFeature"))


def snapshot(feature: Any | None) -> dict[str, Any] | None:
    if feature is None:
        return None
    return {
        "name": feature_name(feature),
        "type": feature_type(feature),
        "suppressed": is_suppressed(feature),
        "select_name": read(feature, "GetNameForSelection"),
    }


def find_feature(model: Any, query: str) -> Any:
    exact = []
    contains = []
    for feature in list_features(model):
        name = feature_name(feature)
        select_name = read(feature, "GetNameForSelection")
        candidates = [x for x in (name, select_name) if isinstance(x, str)]
        if any(x == query for x in candidates):
            exact.append(feature)
        elif any(query.lower() in x.lower() for x in candidates):
            contains.append(feature)
    matches = exact or contains
    if not matches:
        raise RuntimeError(f"Feature not found by name: {query}")
    if len(matches) > 1:
        names = [feature_name(f) for f in matches[:20]]
        raise RuntimeError(f"Feature name is ambiguous for {query}: {names}")
    return matches[0]


def select_feature(feature: Any) -> Any:
    result = read(feature, "Select2", False, 0)
    if not isinstance(result, dict):
        return result
    return read(feature, "Select", False)


def set_suppression(feature: Any, suppress: bool) -> Any:
    action = 0 if suppress else 1
    for args in ((action, 2, None), (action, 2, []), (action,)):
        result = read(feature, "SetSuppression2", *args)
        if not isinstance(result, dict):
            return result
    return read(feature, "SetSuppression", action)


def delete_selected(model: Any) -> Any:
    extension = read(model, "Extension")
    if extension is not None and not isinstance(extension, dict):
        result = read(extension, "DeleteSelection2", 0)
        if not isinstance(result, dict):
            return result
    result = read(model, "EditDelete")
    if not isinstance(result, dict):
        return result
    return read(model, "DeleteSelection", False)


def apply_action(model: Any, feature: Any, action: str) -> Any:
    selection_result = select_feature(feature)
    if action == "suppress":
        return {"select": selection_result, "state": set_suppression(feature, True)}
    if action == "unsuppress":
        return {"select": selection_result, "state": set_suppression(feature, False)}
    if action == "delete":
        return {"select": selection_result, "delete": delete_selected(model)}
    raise ValueError(f"Unsupported action: {action}")


def save_model(model: Any) -> dict[str, Any]:
    pythoncom_mod, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    ok = model.Save3(1, errors, warnings)
    return {"ok": bool(ok), "errors": getattr(errors, "value", errors), "warnings": getattr(warnings, "value", warnings)}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--feature", required=True, help="Feature name exact or unique substring")
    parser.add_argument("--action", required=True, choices=["suppress", "unsuppress", "delete"])
    parser.add_argument("--model", default=None)
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/feature_state.json")
    args = parser.parse_args()
    pythoncom_mod, _win32_client = require_pywin32()
    pythoncom_mod.CoInitialize()
    sw, started = attach(args.start)
    model = open_or_active(sw, args.model)
    before_features = len(list_features(model))
    feature = find_feature(model, args.feature)
    before = snapshot(feature)
    action_result = apply_action(model, feature, args.action)
    rebuild_result = read(model, "ForceRebuild3", False)
    after = None if args.action == "delete" else snapshot(find_feature(model, args.feature))
    after_features = len(list_features(model))
    save_result = save_model(model) if args.save else None
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "document_title": read(model, "GetTitle"),
        "document_path": read(model, "GetPathName"),
        "feature_query": args.feature,
        "action": args.action,
        "before_feature_count": before_features,
        "after_feature_count": after_features,
        "before": before,
        "after": after,
        "action_result": action_result,
        "rebuild_result": rebuild_result,
        "saved": args.save,
        "save_result": save_result,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
