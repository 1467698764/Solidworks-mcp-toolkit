"""Validate current SolidWorks selection evidence before running a mate macro."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


SUPPORTED_SELECTION_TYPES = {
    "FACES",
    "EDGES",
    "DATUMAXES",
    "DATUMPLANES",
    "SKETCHSEGS",
    "EXTSKETCHSEGS",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, reason: str, detail: Any = None) -> None:
    item = {"kind": kind, "reason": reason}
    if detail is not None:
        item["detail"] = detail
    findings.setdefault(severity, []).append(item)


def normalize_component(name: str) -> str:
    return str(name or "").strip().casefold()


def component_name(selection: dict[str, Any]) -> str:
    comp = selection.get("component")
    if isinstance(comp, dict):
        for key in ("Name2", "Name", "GetName", "GetPathName"):
            value = comp.get(key)
            if value:
                return str(value)
    return ""


def choose_macro(manifest: dict[str, Any], expected_mate_name: str) -> dict[str, Any] | None:
    macros = [item for item in manifest.get("macros", []) if isinstance(item, dict)]
    if expected_mate_name:
        for item in macros:
            if str(item.get("expected_mate_name")) == expected_mate_name:
                return item
        return None
    return macros[0] if macros else None


def check(manifest: dict[str, Any], selection_report: dict[str, Any], expected_mate_name: str = "") -> dict[str, Any]:
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    macro = choose_macro(manifest, expected_mate_name)
    if not macro:
        add(findings, "blocking", "macro_not_found", "expected mate macro was not found", {"expected_mate_name": expected_mate_name})
        macro = {}

    selections = [item for item in selection_report.get("selections", []) if isinstance(item, dict)]
    count = selection_report.get("selection_count", len(selections))
    if count != 2 or len(selections) != 2:
        add(findings, "blocking", "selection_count", "mate macros require exactly two currently selected entities", {"selection_count": count, "reported_items": len(selections)})

    expected_components = {normalize_component(c) for c in macro.get("components", []) if c}
    selected_components = {normalize_component(component_name(item)) for item in selections if component_name(item)}
    if expected_components and not selected_components.issubset(expected_components):
        add(findings, "blocking", "selection_component_mismatch", "selected entity components are not all in the expected mate component set", {"expected": sorted(expected_components), "selected": sorted(selected_components)})
    elif expected_components and len(selected_components) < min(2, len(expected_components)):
        add(findings, "warning", "selection_component_coverage", "selection report does not prove both expected components", {"expected": sorted(expected_components), "selected": sorted(selected_components)})

    accepted = 0
    for item in selections:
        typ = str(item.get("type", "")).upper()
        if typ not in SUPPORTED_SELECTION_TYPES:
            add(findings, "blocking", "unsupported_selection_type", "selection is not a face/edge/axis/plane style entity suitable for reviewed mate macros", {"index": item.get("index"), "type": typ})
            continue
        accepted += 1
        add(findings, "accepted", "selection_entity_supported", "selection entity type is suitable for a reviewed mate macro", {"index": item.get("index"), "type": typ, "component": component_name(item)})

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not findings["blocking"],
        "document": {
            "title": selection_report.get("document_title"),
            "path": selection_report.get("document_path"),
            "type": selection_report.get("document_type"),
        },
        "macro": {
            "group_id": macro.get("group_id"),
            "mate_type": macro.get("mate_type"),
            "expected_mate_name": macro.get("expected_mate_name"),
            "components": macro.get("components", []),
        },
        "counts": {
            "selection_count": count,
            "reported_selections": len(selections),
            "accepted_selections": accepted,
            "blocking_findings": len(findings["blocking"]),
            "warning_findings": len(findings["warning"]),
        },
        "findings": findings,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate current selection evidence before running a mate macro")
    parser.add_argument("--macro-manifest", required=True)
    parser.add_argument("--selection-report", required=True)
    parser.add_argument("--expected-mate-name", default="")
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = check(load_json(Path(args.macro_manifest)), load_json(Path(args.selection_report)), args.expected_mate_name)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "selection_ok": result["ok"], "out": str(out)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
