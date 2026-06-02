"""Validate a generic assembly contract against a SolidWorks inspect report.

This is offline/read-only: it consumes JSON produced by sw_assembly_inspect.py and
checks generic mechanical evidence such as required components, component
Transform2 origins, and semantic mate references. It is intentionally not tied to
one fixture; complex fixtures such as the bullhead shaper can use the same style
of contract as a stress test.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document") if isinstance(report, dict) else {}
    return doc if isinstance(doc, dict) else {}


def component_prefix(name: str) -> str:
    return str(name).split("-")[0]


def component_origin(component: dict[str, Any]) -> list[float] | None:
    transform = component.get("transform")
    if isinstance(transform, dict):
        origin = transform.get("origin_m")
        if isinstance(origin, list) and len(origin) == 3:
            try:
                return [float(v) for v in origin]
            except (TypeError, ValueError):
                return None
    raw = component.get("transform_array") or component.get("transform_m")
    if isinstance(raw, list) and len(raw) >= 12:
        try:
            return [float(raw[9]), float(raw[10]), float(raw[11])]
        except (TypeError, ValueError):
            return None
    return None


def within_tolerance(actual: list[float], expected: list[float], tolerance_m: float) -> bool:
    return all(abs(float(actual[i]) - float(expected[i])) <= tolerance_m for i in range(3))


def pair_matches(component_names: Any, semantic_pair: list[str]) -> bool:
    if not isinstance(component_names, list) or len(component_names) < 2:
        return False
    text = "\n".join(str(item) for item in component_names)
    return all(str(name) in text for name in semantic_pair)


def add_decision(items: list[dict[str, Any]], kind: str, key: str, detail: Any, reason: str) -> None:
    items.append({"kind": kind, "key": key, "detail": detail, "reason": reason})


def validate(report: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    doc = active_document(report)

    expected_type = contract.get("document_type")
    if expected_type:
        target = accepted if doc.get("type") == expected_type else failed
        add_decision(target, "document_type", str(expected_type), {"actual": doc.get("type")}, "document type matched" if target is accepted else "document type mismatch")

    min_count = contract.get("minimum_component_count")
    if min_count is not None:
        actual = int(doc.get("component_count_sampled", 0) or 0)
        target = accepted if actual >= int(min_count) else failed
        add_decision(target, "component_count", "minimum_component_count", {"actual": actual, "minimum": int(min_count)}, "component count met" if target is accepted else "component count below contract")

    components = doc.get("components", [])
    components = components if isinstance(components, list) else []
    by_name = {str(c.get("name2", "")): c for c in components if isinstance(c, dict)}
    by_prefix: dict[str, list[dict[str, Any]]] = {}
    for comp_name, comp in by_name.items():
        by_prefix.setdefault(component_prefix(comp_name), []).append(comp)

    for name, spec in (contract.get("components") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        matches = by_prefix.get(str(name), [])
        required = spec.get("required", True)
        if required and not matches:
            add_decision(failed, "component_missing", str(name), spec, "required component prefix missing")
            continue
        if matches:
            add_decision(accepted, "component_present", str(name), {"matches": [m.get("name2") for m in matches]}, "component prefix present")
        if "origin_m" in spec:
            origin = component_origin(matches[0]) if matches else None
            expected = spec.get("origin_m")
            tolerance = float(spec.get("tolerance_m", contract.get("default_origin_tolerance_m", 0.003)))
            ok = origin is not None and isinstance(expected, list) and len(expected) == 3 and within_tolerance(origin, [float(x) for x in expected], tolerance)
            target = accepted if ok else failed
            add_decision(target, "component_origin", str(name), {"actual": origin, "expected": expected, "tolerance_m": tolerance}, "component origin within tolerance" if ok else "component origin missing or outside tolerance")

    mate_features = [m for m in doc.get("mate_like_features", []) if isinstance(m, dict)]
    mate_by_name = {str(m.get("name", "")): m for m in mate_features}
    for name, spec in (contract.get("mates") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        mate = mate_by_name.get(str(name))
        if not mate:
            add_decision(failed, "mate_missing", str(name), spec, "required semantic mate missing")
            continue
        add_decision(accepted, "mate_present", str(name), {"type": mate.get("type")}, "mate feature present")
        expected_type = spec.get("type")
        if expected_type:
            target = accepted if mate.get("type") == expected_type else failed
            add_decision(target, "mate_type", str(name), {"actual": mate.get("type"), "expected": expected_type}, "mate type matched" if target is accepted else "mate type mismatch")
        if mate.get("suppressed") is True:
            add_decision(failed, "mate_suppressed", str(name), mate, "mate is suppressed")
        semantic_pair = spec.get("semantic_pair") or []
        if semantic_pair:
            ok = pair_matches(mate.get("components"), [str(x) for x in semantic_pair])
            target = accepted if ok else failed
            add_decision(target, "mate_components", str(name), {"actual": mate.get("components"), "expected_semantic_pair": semantic_pair}, "mate references expected components" if ok else "mate component references do not match semantic pair")

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not failed,
        "accepted": accepted,
        "failed": failed,
        "summary": {"accepted": len(accepted), "failed": len(failed)},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True, help="SolidWorks inspect JSON")
    parser.add_argument("--contract", required=True, help="Generic assembly contract JSON")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/assembly_contract.json")
    args = parser.parse_args()
    result = validate(load_json(args.report), load_json(args.contract))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
