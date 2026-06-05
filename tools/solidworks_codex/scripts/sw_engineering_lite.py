"""Generate a lightweight engineering BOM, DFM, and DFA review from inspect evidence."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
STANDARD_PART_HINTS = ("bolt", "screw", "washer", "nut", "pin", "dowel", "m3", "m4", "m5", "m6", "m8", "m10")


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document") if isinstance(report, dict) else {}
    return doc if isinstance(doc, dict) else {}


def rows(value: Any) -> list[dict[str, Any]]:
    return [item for item in (value or []) if isinstance(item, dict)]


def component_name(component: dict[str, Any]) -> str:
    return str(component.get("name2") or component.get("name") or component.get("display_name") or "<unnamed>")


def component_key(component: dict[str, Any]) -> tuple[str, str]:
    part = str(component.get("path") or component_name(component))
    config = str(component.get("configuration") or component.get("referenced_configuration") or "Default")
    return part, config


def material_of(component: dict[str, Any]) -> str:
    material = component.get("material") or component.get("material_name")
    if material:
        return str(material)
    props = component.get("custom_properties") if isinstance(component.get("custom_properties"), dict) else {}
    for key in ("Material", "material", "材质"):
        if props.get(key):
            return str(props[key])
    return ""


def add(findings: dict[str, list[dict[str, Any]]], severity: str, kind: str, reason: str, detail: Any = None) -> None:
    item = {"kind": kind, "reason": reason}
    if detail is not None:
        item["detail"] = detail
    findings.setdefault(severity, []).append(item)


def build_bom(components: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for component in components:
        if component.get("suppressed") is True:
            continue
        grouped[component_key(component)].append(component)
    rows_out = []
    for (part_key, configuration), items in sorted(grouped.items()):
        materials = sorted({material_of(item) for item in items if material_of(item)})
        rows_out.append({
            "part_key": part_key,
            "configuration": configuration,
            "quantity": len(items),
            "instances": [component_name(item) for item in items],
            "material": materials[0] if len(materials) == 1 else "",
            "materials": materials,
        })
    return {"rows": rows_out, "count": len(rows_out), "quantity_total": sum(row["quantity"] for row in rows_out)}


def is_standard_part(component: dict[str, Any]) -> bool:
    text = " ".join(str(component.get(key, "")) for key in ("name2", "name", "path", "description")).casefold()
    return any(hint in text for hint in STANDARD_PART_HINTS)


def mate_component_names(mates: list[dict[str, Any]]) -> set[str]:
    result: set[str] = set()
    for mate in mates:
        if mate.get("suppressed") is True or mate.get("mate_error") not in (None, 1):
            continue
        for name in mate.get("components", []) or []:
            result.add(str(name).casefold())
    return result


def feature_float(feature: dict[str, Any], key: str) -> float | None:
    value = feature.get(key)
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def analyze_dfm(features: list[dict[str, Any]], findings: dict[str, list[dict[str, Any]]]) -> None:
    for feature in features:
        semantic = str(feature.get("semantic") or feature.get("type") or "").casefold()
        diameter = feature_float(feature, "diameter_m")
        edge_distance = feature_float(feature, "edge_distance_m")
        if "hole" in semantic and diameter and edge_distance is not None and edge_distance < diameter:
            add(findings, "warning", "hole_edge_clearance_low", "hole edge distance is below one diameter", feature)
        depth = feature_float(feature, "depth_m")
        width = feature_float(feature, "width_m")
        if "pocket" in semantic and depth and width and depth / width > 2.0:
            add(findings, "warning", "deep_narrow_pocket", "pocket depth is more than twice its width", feature)


def analyze(report: dict[str, Any]) -> dict[str, Any]:
    doc = active_document(report)
    components = rows(doc.get("components"))
    mates = rows(doc.get("mate_like_features"))
    features = rows(doc.get("features"))
    findings: dict[str, list[dict[str, Any]]] = {"blocking": [], "warning": [], "accepted": []}
    bom = build_bom(components)

    for row in bom["rows"]:
        if not row.get("material"):
            add(findings, "blocking", "missing_material", "BOM row has no material evidence", row)
        else:
            add(findings, "accepted", "material_present", "BOM row has material evidence", row)

    mated = mate_component_names(mates)
    for component in components:
        name = component_name(component)
        if component.get("suppressed") is True:
            continue
        if is_standard_part(component) and name.casefold() not in mated:
            add(findings, "blocking", "hostless_standard_part", "standard/detail component has no accepted mate evidence", component)
        if component.get("fixed") is False and name.casefold() not in mated and not is_standard_part(component):
            add(findings, "warning", "floating_component_without_mate", "floating component has no accepted mate evidence", component)

    analyze_dfm(features, findings)
    if bom["rows"]:
        add(findings, "accepted", "bom_generated", "BOM rows were grouped by part path and configuration", {"rows": bom["count"], "quantity_total": bom["quantity_total"]})

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": "engineering_lite",
        "ok": not findings["blocking"],
        "document": {"title": doc.get("title"), "type": doc.get("type"), "path": doc.get("path")},
        "counts": {
            "components": len(components),
            "mates": len(mates),
            "features": len(features),
            "bom_rows": bom["count"],
            "blocking_findings": len(findings["blocking"]),
            "warning_findings": len(findings["warning"]),
        },
        "bom": bom,
        "findings": findings,
    }


def markdown(data: dict[str, Any]) -> str:
    lines = ["# Engineering Lite Review", ""]
    lines += [
        f"- Document: `{data['document'].get('title')}`",
        f"- Type: `{data['document'].get('type')}`",
        f"- OK: `{data['ok']}`",
        f"- Counts: `{data['counts']}`",
        "",
        "## BOM",
        "",
        "| Part/configuration | Quantity | Material | Instances |",
        "| --- | ---: | --- | --- |",
    ]
    for row in data["bom"]["rows"]:
        lines.append(f"| `{row['part_key']}` / `{row['configuration']}` | {row['quantity']} | `{row.get('material') or '<missing>'}` | {', '.join(f'`{name}`' for name in row['instances'])} |")
    lines += ["", "## Findings", ""]
    for severity in ("blocking", "warning", "accepted"):
        lines.append(f"### {severity}")
        items = data["findings"].get(severity, [])
        lines.extend([f"- `{item['kind']}`: {item['reason']}" for item in items] or ["- None"])
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate engineering-lite BOM, DFM, and DFA evidence from inspect JSON")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out", default="tools/solidworks_codex/reports/engineering_lite.md")
    parser.add_argument("--json-out", default="tools/solidworks_codex/reports/engineering_lite.json")
    args = parser.parse_args()

    result = analyze(load_json(resolve(args.report)))
    out = resolve(args.out)
    json_out = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    json_out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(result), encoding="utf-8")
    json_out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "out": str(out), "json_out": str(json_out), "blocking_findings": result["counts"]["blocking_findings"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
