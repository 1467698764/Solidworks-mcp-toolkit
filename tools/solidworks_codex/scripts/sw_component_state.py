"""Change SolidWorks assembly component state by Component2.Name2.

Supported actions: hide, show, suppress, unsuppress, fix, float.
This script is intentionally narrow and emits JSON for every operation.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pythoncom
import win32com.client


def val(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple)):
        return [val(v) for v in value]
    return str(value)


def read(obj: Any, name: str, *args: Any) -> Any:
    try:
        member = getattr(obj, name)
        return val(member(*args) if callable(member) else member)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def attach(start: bool) -> tuple[Any, bool]:
    try:
        return win32com.client.GetActiveObject("SldWorks.Application"), False
    except Exception as exc:
        if not start:
            raise RuntimeError("SolidWorks is not running. Start it or pass --start.") from exc
        sw = win32com.client.Dispatch("SldWorks.Application")
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


def find_component(asm: Any, name2: str) -> Any:
    comps = read(asm, "GetComponents", False)
    if isinstance(comps, dict) or not comps:
        raise RuntimeError("Assembly returned no components.")
    exact = []
    contains = []
    for comp in list(comps):
        cname = read(comp, "Name2")
        if cname == name2:
            exact.append(comp)
        elif isinstance(cname, str) and name2.lower() in cname.lower():
            contains.append(comp)
    matches = exact or contains
    if not matches:
        raise RuntimeError(f"Component not found by Name2: {name2}")
    if len(matches) > 1:
        names = [read(c, "Name2") for c in matches[:20]]
        raise RuntimeError(f"Component name is ambiguous for {name2}: {names}")
    return matches[0]


def snapshot(comp: Any) -> dict[str, Any]:
    return {
        "name2": read(comp, "Name2"),
        "path": read(comp, "GetPathName"),
        "suppressed": read(comp, "IsSuppressed"),
        "hidden": read(comp, "IsHidden", True),
        "fixed": read(comp, "IsFixed"),
        "lightweight": read(comp, "IsLightWeight"),
    }


def apply_action(asm: Any, comp: Any, action: str) -> Any:
    # Select component first; many assembly actions operate on selection.
    sel = read(comp, "Select4", False, None, False)
    if action == "hide":
        return read(comp, "HideComponent", True)
    if action == "show":
        return read(comp, "HideComponent", False)
    if action == "suppress":
        # swComponentSuppressed = 0 in many API versions; keep via SetSuppression2.
        return read(comp, "SetSuppression2", 0)
    if action == "unsuppress":
        # swComponentResolved = 2 in many API versions.
        return read(comp, "SetSuppression2", 2)
    if action == "fix":
        return read(asm, "FixComponent")
    if action == "float":
        return read(asm, "UnfixComponent")
    raise ValueError(f"Unsupported action: {action}; select={sel}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--component", required=True, help="Component2.Name2 exact or unique substring")
    parser.add_argument("--action", required=True, choices=["hide", "show", "suppress", "unsuppress", "fix", "float"])
    parser.add_argument("--start", action="store_true")
    parser.add_argument("--save", action="store_true")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/component_state.json")
    args = parser.parse_args()
    pythoncom.CoInitialize()
    sw, started = attach(args.start)
    asm = active_assembly(sw)
    comp = find_component(asm, args.component)
    before = snapshot(comp)
    action_result = apply_action(asm, comp, args.action)
    rebuild_result = read(asm, "ForceRebuild3", False)
    after = snapshot(comp)
    save_result = read(asm, "Save3", 1, 0, 0) if args.save else None
    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started,
        "assembly_title": read(asm, "GetTitle"),
        "assembly_path": read(asm, "GetPathName"),
        "component_query": args.component,
        "action": args.action,
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
