"""Read-only SolidWorks COM probe for Codex.

Does not create or modify documents. By default it only attaches to an already-running
SolidWorks instance. Pass --start to allow launching SolidWorks through COM.
"""
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
        if callable(member):
            return member(*args)
        if args:
            return {"error": f"member {name} is a property, arguments were provided"}
        return member
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def attach_solidworks(allow_start: bool) -> tuple[Any, bool]:
    try:
        return win32com.client.GetActiveObject("SldWorks.Application"), False
    except Exception as attach_error:
        if not allow_start:
            raise RuntimeError(
                "SolidWorks is not running. Start SolidWorks and rerun, or pass --start to launch it."
            ) from attach_error
        return win32com.client.Dispatch("SldWorks.Application"), True


def probe(allow_start: bool = False) -> dict[str, Any]:
    pythoncom.CoInitialize()
    sw, started_by_probe = attach_solidworks(allow_start)
    report: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "connected": True,
        "started_by_probe": started_by_probe,
        "revision_number": read_member(sw, "RevisionNumber"),
        "visible": read_member(sw, "Visible"),
        "active_document": None,
    }

    model = read_member(sw, "ActiveDoc")
    if isinstance(model, dict) or model is None:
        report["active_document"] = None
        report["note"] = "No active SolidWorks document detected."
        return report

    active: dict[str, Any] = {
        "title": read_member(model, "GetTitle"),
        "path": read_member(model, "GetPathName"),
        "type": read_member(model, "GetType"),
        "configuration": None,
        "feature_count_sampled": 0,
        "features_sample": [],
    }
    cfg_mgr = read_member(model, "ConfigurationManager")
    if not isinstance(cfg_mgr, dict) and cfg_mgr is not None:
        active_cfg = read_member(cfg_mgr, "ActiveConfiguration")
        if not isinstance(active_cfg, dict) and active_cfg is not None:
            active["configuration"] = read_member(active_cfg, "Name")

    feat = read_member(model, "FirstFeature")
    while feat is not None and not isinstance(feat, dict) and active["feature_count_sampled"] < 80:
        active["features_sample"].append({
            "name": read_member(feat, "Name"),
            "type": read_member(feat, "GetTypeName2"),
        })
        active["feature_count_sampled"] += 1
        feat = read_member(feat, "GetNextFeature")

    if active.get("type") == 2:  # swDocASSEMBLY
        comps = read_member(model, "GetComponents", False)
        comp_items = []
        if not isinstance(comps, dict) and comps:
            for comp in list(comps)[:100]:
                comp_items.append({
                    "name2": read_member(comp, "Name2"),
                    "path": read_member(comp, "GetPathName"),
                    "suppressed": read_member(comp, "IsSuppressed"),
                })
        active["components_sample"] = comp_items
        active["component_count_sampled"] = len(comp_items)

    report["active_document"] = active
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--start", action="store_true", help="Allow launching SolidWorks if it is not running")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/com_probe.json")
    args = parser.parse_args()
    result = probe(args.start)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
