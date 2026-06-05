"""Insert a reviewed component into an active or specified SolidWorks assembly."""
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
            raise RuntimeError("No active SolidWorks assembly. Open an assembly or pass --model.")
        return model
    path = str(Path(model_path).resolve())
    if Path(path).suffix.lower() != ".sldasm":
        raise ValueError(f"component insert requires a .SLDASM assembly model: {path}")
    pythoncom_mod, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom_mod.VT_BYREF | pythoncom_mod.VT_I4, 0)
    model = sw.OpenDoc6(path, 2, 0, "", errors, warnings)
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
        raise ValueError("component insert spec must be a JSON object")
    return data


def validate_origin(value: Any) -> list[float]:
    if not isinstance(value, list) or len(value) != 3:
        raise ValueError("origin_m must be a three-number array")
    return [float(value[0]), float(value[1]), float(value[2])]


def validate_attachment(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {
            "role": "",
            "host_component": "",
            "host_interface_id": "",
            "mate_group_id": "",
            "required_mates": [],
            "host_selector": None,
            "inserted_selector": None,
            "selector_handoff_status": "no_attachment_selectors",
        }
    if not isinstance(value, dict):
        raise ValueError("attachment must be a JSON object when provided")
    required_mates = value.get("required_mates", [])
    if isinstance(required_mates, str):
        required_mates = [item.strip() for item in required_mates.split(",") if item.strip()]
    if not isinstance(required_mates, list):
        raise ValueError("attachment.required_mates must be an array or comma-separated string")
    host_selector = value.get("host_selector") or value.get("host_interface_selector")
    inserted_selector = value.get("inserted_selector") or value.get("standard_part_selector") or value.get("component_selector")
    if host_selector is not None and not isinstance(host_selector, dict):
        raise ValueError("attachment.host_selector must be a JSON object when provided")
    if inserted_selector is not None and not isinstance(inserted_selector, dict):
        raise ValueError("attachment.inserted_selector must be a JSON object when provided")
    selector_handoff_status = "native_identity_ready_for_mate_group" if host_selector or inserted_selector else "awaiting_selector_capture"
    return {
        "role": str(value.get("role") or "").strip(),
        "host_component": str(value.get("host_component") or "").strip(),
        "host_interface_id": str(value.get("host_interface_id") or "").strip(),
        "mate_group_id": str(value.get("mate_group_id") or "").strip(),
        "required_mates": [str(item).strip() for item in required_mates if str(item).strip()],
        "host_selector": host_selector,
        "inserted_selector": inserted_selector,
        "selector_handoff_status": selector_handoff_status,
    }


def validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    part_path = str(spec.get("part_path") or spec.get("component_path") or "").strip()
    if not part_path:
        raise ValueError("component insert spec requires part_path")
    suffix = Path(part_path).suffix.lower()
    if suffix not in {".sldprt", ".sldasm"}:
        raise ValueError(f"component insert supports .SLDPRT or .SLDASM components, got {part_path}")
    origin_m = validate_origin(spec.get("origin_m", [0.0, 0.0, 0.0]))
    attachment_intent = validate_attachment(spec.get("attachment"))
    is_standard_part = bool(spec.get("standard_part", False)) or bool(attachment_intent["host_component"] or attachment_intent["host_interface_id"])
    component_role = "standard_part" if is_standard_part else "detail_component"
    return {
        "part_path": part_path,
        "component_name": str(spec.get("component_name") or "").strip(),
        "configuration": str(spec.get("configuration") or "").strip(),
        "origin_m": origin_m,
        "fixed": bool(spec.get("fixed", False)),
        "lightweight": bool(spec.get("lightweight", False)),
        "component_role": component_role,
        "attachment_intent": attachment_intent,
        "attachment_status": "awaiting_mate_group_execution" if is_standard_part else "placed_without_attachment_contract",
    }


def component_snapshot(component: Any) -> dict[str, Any]:
    return {
        "name": read(component, "Name2") or read(component, "Name"),
        "path": read(component, "GetPathName"),
        "suppressed": read(component, "IsSuppressed"),
    }


def invoke_insert(assembly: Any, plan: dict[str, Any]) -> dict[str, Any]:
    x, y, z = plan["origin_m"]
    path = plan["part_path"]
    config = plan["configuration"]
    attempts = []
    for name, args in (
        ("AddComponent5", (path, 0, config, False, "", x, y, z)),
        ("AddComponent4", (path, config, x, y, z)),
        ("AddComponent", (path, x, y, z)),
    ):
        try:
            member = getattr(assembly, name)
            component = member(*args)
            if component is not None:
                return {"ok": True, "method": name, "args": [val(item) for item in args], "component": component}
            attempts.append({"method": name, "error": "returned None"})
        except Exception as exc:
            attempts.append({"method": name, "error": f"{type(exc).__name__}: {exc}"})
    return {"ok": False, "attempts": attempts, "component": None}


def fix_component(assembly: Any, component: Any) -> dict[str, Any]:
    selected = read(component, "Select4", False, None, 0)
    fixed = read(assembly, "FixComponent")
    return {"selected": selected, "fixed": fixed}


def execute_insert(assembly: Any, plan: dict[str, Any]) -> dict[str, Any]:
    insert = invoke_insert(assembly, plan)
    component = insert.get("component")
    if not insert.get("ok") or component is None:
        return {"ok": False, "insert": insert, "component": None, "fix_result": None}
    fix_result = fix_component(assembly, component) if plan.get("fixed") else None
    return {
        "ok": True,
        "insert": {key: value for key, value in insert.items() if key != "component"},
        "component": component_snapshot(component),
        "fix_result": fix_result,
        "component_role": plan.get("component_role"),
        "attachment_intent": plan.get("attachment_intent"),
        "attachment_status": plan.get("attachment_status"),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, help="JSON spec containing part_path, origin_m, optional configuration/fixed")
    parser.add_argument("--model", default=None)
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/component_insert.json")
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
        assembly = open_or_active(sw, args.model)
        execution = execute_insert(assembly, plan)
        rebuild_result = read(assembly, "ForceRebuild3", False)
        save_result = save_model(assembly) if args.save else None
        result.update({
            "ok": bool(execution.get("ok")),
            "connected": True,
            "started_by_probe": started,
            "document_title": read(assembly, "GetTitle"),
            "document_path": read(assembly, "GetPathName"),
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
