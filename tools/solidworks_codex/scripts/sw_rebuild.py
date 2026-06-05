"""Rebuild the active or specified SolidWorks document and write JSON result."""
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



def save_model(model: Any) -> dict[str, Any]:
    pythoncom_mod, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    ok = model.Save3(1, errors, warnings)
    return {"ok": bool(ok), "errors": getattr(errors, "value", errors), "warnings": getattr(warnings, "value", warnings)}


def call_int(obj: Any, name: str) -> int:
    func = getattr(obj, name, None)
    if not callable(func):
        return 0
    try:
        return int(func() or 0)
    except Exception:
        return 0


def feature_name(feature: Any) -> str:
    for method in ("GetNameForSelection", "Name", "GetName"):
        value = read_member(feature, method)
        if isinstance(value, str) and value:
            return value
    return "<unnamed>"


def feature_type(feature: Any) -> str:
    for method in ("GetTypeName2", "GetTypeName"):
        value = read_member(feature, method)
        if isinstance(value, str) and value:
            return value
    return "<unknown>"


def feature_error_code(feature: Any) -> int:
    for method in ("GetErrorCode2", "GetErrorCode"):
        value = read_member(feature, method)
        if isinstance(value, int):
            return value
    return 0


def next_feature(feature: Any) -> Any | None:
    for method in ("GetNextFeature", "IGetNextFeature"):
        func = getattr(feature, method, None)
        if not callable(func):
            continue
        try:
            return func()
        except Exception:
            continue
    return None


def iter_features(model: Any, limit: int = 500) -> list[Any]:
    func = getattr(model, "FirstFeature", None)
    if not callable(func):
        return []
    try:
        first = func()
    except Exception:
        return []
    result = []
    current = first
    seen: set[int] = set()
    while current is not None and id(current) not in seen and len(result) < limit:
        seen.add(id(current))
        result.append(current)
        current = next_feature(current)
    return result


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, reason: str, detail: Any = None) -> None:
    item = {"kind": kind, "reason": reason}
    if detail is not None:
        item["detail"] = detail
    findings.setdefault(severity, []).append(item)


def rebuild_health(model: Any) -> dict[str, Any]:
    rebuild_result = read_member(model, "ForceRebuild3", False)
    rebuild_ok = bool(rebuild_result) and not isinstance(rebuild_result, dict)
    extension = getattr(model, "Extension", None)
    error_count = call_int(extension, "GetErrorCount") if extension is not None else 0
    warning_count = call_int(extension, "GetWarningCount") if extension is not None else 0
    feature_errors = []
    for feature in iter_features(model):
        code = feature_error_code(feature)
        if code:
            feature_errors.append({"name": feature_name(feature), "type": feature_type(feature), "error_code": code})

    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    if not rebuild_ok:
        add(findings, "blocking", "rebuild_failed", "ForceRebuild3 did not report success", {"rebuild_result": rebuild_result})
    if error_count:
        add(findings, "blocking", "rebuild_error_count", "document extension reports rebuild errors", {"error_count": error_count})
    if warning_count:
        add(findings, "warning", "rebuild_warning_count", "document extension reports rebuild warnings", {"warning_count": warning_count})
    for item in feature_errors:
        add(findings, "blocking", "feature_error", "feature reports a nonzero error code", item)
    if not findings["blocking"]:
        add(findings, "accepted", "rebuild_health_clean", "rebuild completed without blocking health findings")

    return {
        "ok": not findings["blocking"],
        "rebuild_result": rebuild_result,
        "rebuild_ok": rebuild_ok,
        "error_count": error_count,
        "warning_count": warning_count,
        "feature_errors": feature_errors,
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--model", default=None)
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/rebuild.json")
    args = parser.parse_args()
    pythoncom_mod, _win32_client = require_pywin32()
    pythoncom_mod.CoInitialize()
    sw, started = attach(args.start)
    model = open_or_active(sw, args.model)
    health = rebuild_health(model)
    save_result = None
    if args.save:
        save_result = save_model(model)
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "document_title": read_member(model, "GetTitle"),
        "document_path": read_member(model, "GetPathName"),
        "ok": health["ok"],
        "rebuild_result": health["rebuild_result"],
        "rebuild_health": health,
        "saved": args.save,
        "save_result": save_result,
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
