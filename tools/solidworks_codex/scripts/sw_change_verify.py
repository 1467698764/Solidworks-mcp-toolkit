"""Verify a compare delta contains only expected changes."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def normalize_dimension_key(value: str) -> str:
    text = str(value)
    for ext in (".SLDPRT", ".sldprt", ".SLDASM", ".sldasm"):
        text = text.replace(ext, ".Part")
    return text


def parse_component_rule(value: str) -> tuple[str, str | None]:
    if ":" in value:
        name, field = value.split(":", 1)
        return name, field
    return value, None


def add_decision(items: list[dict[str, Any]], kind: str, key: str, detail: Any, reason: str) -> None:
    items.append({"kind": kind, "key": key, "detail": detail, "reason": reason})


def verify(delta: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    allow_dims = {normalize_dimension_key(x) for x in (args.allow_dimension or [])}
    allow_comp_added = set(args.allow_component_added or [])
    allow_comp_removed = set(args.allow_component_removed or [])
    allow_feature_types = set(args.allow_feature_type or [])
    allow_components = [parse_component_rule(x) for x in (args.allow_component or [])]

    accepted: list[dict[str, Any]] = []
    unexpected: list[dict[str, Any]] = []

    for item in delta.get("dimensions", {}).get("changed", []) or []:
        key = str(item.get("key"))
        normalized_key = normalize_dimension_key(key)
        target = accepted if normalized_key in allow_dims else unexpected
        add_decision(target, "dimension_changed", key, item, "allowed dimension" if target is accepted else "dimension not in allow list")
    for item in delta.get("dimensions", {}).get("added", []) or []:
        key = str(item.get("full_name") or item.get("name") or item.get("display_name") or "<unnamed>")
        add_decision(unexpected, "dimension_added", key, item, "new dimensions are not allowed by default")
    for item in delta.get("dimensions", {}).get("removed", []) or []:
        key = str(item.get("full_name") or item.get("name") or item.get("display_name") or "<unnamed>")
        add_decision(unexpected, "dimension_removed", key, item, "removed dimensions are not allowed by default")

    for item in delta.get("components", {}).get("added", []) or []:
        key = str(item.get("name2") or item.get("path") or "<unnamed>")
        target = accepted if key in allow_comp_added else unexpected
        add_decision(target, "component_added", key, item, "allowed component addition" if target is accepted else "component addition not in allow list")
    for item in delta.get("components", {}).get("removed", []) or []:
        key = str(item.get("name2") or item.get("path") or "<unnamed>")
        target = accepted if key in allow_comp_removed else unexpected
        add_decision(target, "component_removed", key, item, "allowed component removal" if target is accepted else "component removal not in allow list")
    for item in delta.get("components", {}).get("changed", []) or []:
        key = str(item.get("key"))
        changes = item.get("changes") or {}
        fields = changes.keys() if isinstance(changes, dict) else []
        for field in fields:
            is_allowed = any(name == key and (allowed_field is None or allowed_field == field) for name, allowed_field in allow_components)
            target = accepted if is_allowed else unexpected
            add_decision(target, "component_changed", f"{key}:{field}", {"key": key, "field": field, "change": changes.get(field)}, "allowed component field" if target is accepted else "component field not in allow list")

    for item in delta.get("features", {}).get("count_changes", []) or []:
        key = str(item.get("type") or "<unknown>")
        target = accepted if key in allow_feature_types else unexpected
        add_decision(target, "feature_count_changed", key, item, "allowed feature type count change" if target is accepted else "feature type count change not in allow list")

    if getattr(args, "require_allowed_change", False) and (args.allow_dimension or args.allow_component or args.allow_component_added or args.allow_component_removed or args.allow_feature_type) and not accepted:
        add_decision(unexpected, "required_allowed_change_missing", "<allowed_changes>", {"policy": {"allow_dimension": sorted(allow_dims), "allow_component": args.allow_component or [], "allow_component_added": sorted(allow_comp_added), "allow_component_removed": sorted(allow_comp_removed), "allow_feature_type": sorted(allow_feature_types)}}, "no allowed changes were observed in the delta")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not unexpected,
        "delta_document": delta.get("document", {}),
        "policy": {
            "allow_dimension": sorted(allow_dims),
            "allow_component": args.allow_component or [],
            "allow_component_added": sorted(allow_comp_added),
            "allow_component_removed": sorted(allow_comp_removed),
            "allow_feature_type": sorted(allow_feature_types),
        },
        "accepted": accepted,
        "unexpected": unexpected,
        "summary": {"accepted": len(accepted), "unexpected": len(unexpected)},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--delta", required=True, help="JSON delta from sw_compare_reports.py")
    parser.add_argument("--allow-dimension", action="append", default=[])
    parser.add_argument("--allow-component", action="append", default=[], help="component or component:field")
    parser.add_argument("--allow-component-added", action="append", default=[])
    parser.add_argument("--allow-component-removed", action="append", default=[])
    parser.add_argument("--allow-feature-type", action="append", default=[])
    parser.add_argument("--require-allowed-change", action="store_true", help="Fail when allow lists are provided but the delta contains no matching allowed change")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/change_verify.json")
    args = parser.parse_args()
    result = verify(load(args.delta), args)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
