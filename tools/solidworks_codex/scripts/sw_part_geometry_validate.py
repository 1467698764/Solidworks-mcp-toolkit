"""Validate part geometry readback evidence after part feature execution."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
KNOWN_SEVERITIES = {"blocking", "warning", "not_applicable"}


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document") if isinstance(report, dict) else {}
    return doc if isinstance(doc, dict) else report


def rows(value: Any) -> list[dict[str, Any]]:
    return [item for item in (value or []) if isinstance(item, dict)]


def add(items: list[dict[str, Any]], kind: str, key: str, detail: Any, reason: str, severity: str = "blocking") -> None:
    items.append({"kind": kind, "key": key, "detail": detail, "reason": reason, "severity": severity})


def bucket(severity: str, accepted: list[dict[str, Any]], warnings: list[dict[str, Any]], not_applicable: list[dict[str, Any]], failed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if severity == "warning":
        return warnings
    if severity == "not_applicable":
        return not_applicable
    return failed


def bbox_size(doc: dict[str, Any]) -> list[float] | None:
    bbox = doc.get("bbox_m") or doc.get("bounding_box_m")
    if isinstance(bbox, list) and len(bbox) == 6:
        try:
            return [abs(float(bbox[i + 3]) - float(bbox[i])) for i in range(3)]
        except (TypeError, ValueError):
            return None
    size = doc.get("bbox_size_m")
    if isinstance(size, list) and len(size) == 3:
        try:
            return [float(value) for value in size]
        except (TypeError, ValueError):
            return None
    return None


def doc_volume(doc: dict[str, Any]) -> float | None:
    for key in ("volume_m3", "volume"):
        if doc.get(key) not in (None, ""):
            try:
                return float(doc[key])
            except (TypeError, ValueError):
                return None
    mass = doc.get("mass_properties") if isinstance(doc.get("mass_properties"), dict) else {}
    if mass.get("volume_m3") not in (None, ""):
        try:
            return float(mass["volume_m3"])
        except (TypeError, ValueError):
            return None
    return None


def feature_names(features: list[dict[str, Any]]) -> set[str]:
    return {str(item.get("name", "")) for item in features if item.get("name") is not None}


def semantic_count(features: list[dict[str, Any]], semantic: str) -> int:
    total = 0
    target = str(semantic).casefold()
    for feature in features:
        if str(feature.get("semantic", "")).casefold() != target:
            continue
        try:
            total += int(feature.get("count", 1) or 1)
        except (TypeError, ValueError):
            total += 1
    return total


def interface_rows(doc: dict[str, Any]) -> list[dict[str, Any]]:
    interfaces = rows(doc.get("interfaces"))
    if interfaces:
        return interfaces
    index = doc.get("interface_index") if isinstance(doc.get("interface_index"), dict) else {}
    return rows(index.get("interfaces"))


def validate(report: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    doc = active_document(report)
    features = rows(doc.get("features"))
    interfaces = interface_rows(doc)
    accepted: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    not_applicable: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []

    body_min = contract.get("minimum_body_count")
    if body_min is not None:
        actual = int(doc.get("body_count", doc.get("solid_body_count", 0)) or 0)
        target = accepted if actual >= int(body_min) else failed
        add(target, "body_count", "minimum_body_count", {"actual": actual, "minimum": int(body_min)}, "body count met" if target is accepted else "body count below contract")

    min_size = contract.get("minimum_bbox_size_m")
    if isinstance(min_size, list) and len(min_size) == 3:
        actual = bbox_size(doc)
        ok = actual is not None and all(actual[i] >= float(min_size[i]) for i in range(3))
        target = accepted if ok else failed
        add(target, "bbox_size", "minimum_bbox_size_m", {"actual": actual, "minimum": min_size}, "bbox size met" if ok else "bbox size missing or below contract")

    min_volume = contract.get("minimum_volume_m3")
    if min_volume is not None:
        actual = doc_volume(doc)
        ok = actual is not None and actual >= float(min_volume)
        target = accepted if ok else failed
        add(target, "volume", "minimum_volume_m3", {"actual": actual, "minimum": float(min_volume)}, "volume met" if ok else "volume missing or below contract")

    available = feature_names(features)
    for name in contract.get("required_features", []) or []:
        ok = any(str(name) in actual for actual in available)
        target = accepted if ok else failed
        add(target, "feature_present" if ok else "feature_missing", str(name), {"available": sorted(available)}, "required feature present" if ok else "required feature missing")

    for semantic, spec in (contract.get("required_semantics") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        severity = str(spec.get("severity", "blocking")).casefold()
        if severity not in KNOWN_SEVERITIES:
            add(failed, "contract_severity", str(semantic), {"severity": severity, "allowed": sorted(KNOWN_SEVERITIES)}, "unknown semantic contract severity")
            continue
        if severity == "not_applicable":
            add(not_applicable, "semantic_not_applicable", str(semantic), spec, "semantic check marked not_applicable", severity)
            continue
        minimum = int(spec.get("min_count", 1) or 1)
        actual = semantic_count(features, str(semantic))
        ok = actual >= minimum
        target = accepted if ok else bucket(severity, accepted, warnings, not_applicable, failed)
        add(target, "semantic_count", str(semantic), {"actual": actual, "minimum": minimum}, "semantic feature count met" if ok else "semantic feature count below contract", "blocking" if ok else severity)

    min_interfaces = contract.get("minimum_interface_count")
    if min_interfaces is not None:
        actual = len(interfaces)
        ok = actual >= int(min_interfaces)
        target = accepted if ok else failed
        add(target, "interface_count", "minimum_interface_count", {"actual": actual, "minimum": int(min_interfaces)}, "interface count met" if ok else "interface count below contract")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not failed,
        "document": {"title": doc.get("title"), "type": doc.get("type"), "path": doc.get("path")},
        "accepted": accepted,
        "warnings": warnings,
        "not_applicable": not_applicable,
        "failed": failed,
        "summary": {"accepted": len(accepted), "warnings": len(warnings), "not_applicable": len(not_applicable), "failed": len(failed)},
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Validate part geometry readback evidence")
    parser.add_argument("--report", required=True)
    parser.add_argument("--contract", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()

    result = validate(load_json(resolve(args.report)), load_json(resolve(args.contract)))
    out = resolve(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": result["ok"], "out": str(out), "failed": result["summary"]["failed"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
