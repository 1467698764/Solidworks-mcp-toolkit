"""Validate a generic assembly contract against a SolidWorks inspect report.

This is offline/read-only: it consumes JSON produced by sw_assembly_inspect.py and
checks generic mechanical evidence such as required components, component
Transform2 origins, and semantic mate references. It is intentionally not tied to
one fixture; named fixtures are only regression cases for the same evidence
model.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

KNOWN_SEVERITIES = {"blocking", "warning", "not_applicable"}


def load_json(path: str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def active_document(report: dict[str, Any]) -> dict[str, Any]:
    doc = report.get("active_document") if isinstance(report, dict) else {}
    return doc if isinstance(doc, dict) else {}


INSTANCE_SUFFIX = re.compile(r"-\d+$")


def component_key(name: str) -> str:
    return INSTANCE_SUFFIX.sub("", str(name)).casefold()


def component_matches(actual: str, expected: str) -> bool:
    return component_key(actual) == str(expected).casefold()


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
    actual_keys = {component_key(str(item)) for item in component_names}
    return all(str(name).casefold() in actual_keys for name in semantic_pair)


def matched_components(component_names: Any, by_key: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    if not isinstance(component_names, list):
        return []
    matches: list[dict[str, Any]] = []
    for name in component_names:
        candidates = by_key.get(component_key(str(name)), [])
        if candidates:
            matches.append(candidates[0])
    return matches


def all_components_fixed(component_names: Any, by_key: dict[str, list[dict[str, Any]]]) -> bool:
    matches = matched_components(component_names, by_key)
    return len(matches) >= 2 and all(component.get("fixed") is True for component in matches[:2])


def part_feature_evidence(report: dict[str, Any]) -> dict[str, Any]:
    evidence = report.get("part_feature_evidence") if isinstance(report, dict) else {}
    if not isinstance(evidence, dict):
        evidence = active_document(report).get("part_feature_evidence")
    return evidence if isinstance(evidence, dict) else {}


def feature_names(features: Any) -> set[str]:
    if not isinstance(features, list):
        return set()
    return {str(item.get("name", "")) for item in features if isinstance(item, dict) and item.get("name") is not None}


def semantic_feature_count(features: Any, semantic: str) -> int:
    if not isinstance(features, list):
        return 0
    total = 0
    target = str(semantic).casefold()
    for item in features:
        if not isinstance(item, dict):
            continue
        if str(item.get("semantic", "")).casefold() != target:
            continue
        try:
            total += int(item.get("count", 1) or 1)
        except (TypeError, ValueError):
            total += 1
    return total


def mate_status_unsolved(mate: dict[str, Any]) -> bool:
    status = mate.get("status", mate.get("solver_status"))
    if status is None:
        return False
    return str(status).strip().casefold() not in {"ok", "solved", "satisfied", "active", "0"}


def add_decision(items: list[dict[str, Any]], kind: str, key: str, detail: Any, reason: str, severity: str = "blocking") -> None:
    items.append({"kind": kind, "key": key, "detail": detail, "reason": reason, "severity": severity})


def severity_of(spec: dict[str, Any], default: str = "blocking") -> str:
    return str(spec.get("severity", default) or default).strip().lower()


def decision_bucket(severity: str, accepted: list[dict[str, Any]], warnings: list[dict[str, Any]], not_applicable: list[dict[str, Any]], failed: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if severity == "warning":
        return warnings
    if severity == "not_applicable":
        return not_applicable
    return failed


def validate(report: dict[str, Any], contract: dict[str, Any]) -> dict[str, Any]:
    accepted: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    not_applicable: list[dict[str, Any]] = []
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
    by_key: dict[str, list[dict[str, Any]]] = {}
    for comp_name, comp in by_name.items():
        by_key.setdefault(component_key(comp_name), []).append(comp)

    for name, spec in (contract.get("components") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        severity = severity_of(spec)
        if severity not in KNOWN_SEVERITIES:
            add_decision(failed, "contract_severity", str(name), {"severity": severity, "allowed": sorted(KNOWN_SEVERITIES)}, "unknown component contract severity")
            continue
        matches = by_key.get(str(name).casefold(), [])
        required = spec.get("required", True)
        if severity == "not_applicable":
            add_decision(not_applicable, "component_not_applicable", str(name), spec, "component check marked not_applicable", severity)
            continue
        if required and not matches:
            add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "component_missing", str(name), spec, "required component prefix missing", severity)
            continue
        if matches:
            add_decision(accepted, "component_present", str(name), {"matches": [m.get("name2") for m in matches]}, "component prefix present")
            if required and any(match.get("suppressed") is True for match in matches):
                add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "component_suppressed", str(name), {"matches": [m.get("name2") for m in matches]}, "required component is suppressed", severity)
        if "origin_m" in spec:
            origin = component_origin(matches[0]) if matches else None
            expected = spec.get("origin_m")
            tolerance = float(spec.get("tolerance_m", contract.get("default_origin_tolerance_m", 0.003)))
            ok = origin is not None and isinstance(expected, list) and len(expected) == 3 and within_tolerance(origin, [float(x) for x in expected], tolerance)
            target = accepted if ok else decision_bucket(severity, accepted, warnings, not_applicable, failed)
            add_decision(target, "component_origin", str(name), {"actual": origin, "expected": expected, "tolerance_m": tolerance}, "component origin within tolerance" if ok else "component origin missing or outside tolerance", "blocking" if ok else severity)

    mate_features = [m for m in doc.get("mate_like_features", []) if isinstance(m, dict)]
    mate_by_name = {str(m.get("name", "")): m for m in mate_features}
    for name, spec in (contract.get("mates") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        severity = severity_of(spec)
        if severity not in KNOWN_SEVERITIES:
            add_decision(failed, "contract_severity", str(name), {"severity": severity, "allowed": sorted(KNOWN_SEVERITIES)}, "unknown mate contract severity")
            continue
        if severity == "not_applicable":
            add_decision(not_applicable, "mate_not_applicable", str(name), spec, "mate check marked not_applicable", severity)
            continue
        mate = mate_by_name.get(str(name))
        if not mate:
            add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "mate_missing", str(name), spec, "required semantic mate missing", severity)
            continue
        add_decision(accepted, "mate_present", str(name), {"type": mate.get("type")}, "mate feature present")
        expected_type = spec.get("type")
        if expected_type:
            ok = mate.get("type") == expected_type
            target = accepted if ok else decision_bucket(severity, accepted, warnings, not_applicable, failed)
            add_decision(target, "mate_type", str(name), {"actual": mate.get("type"), "expected": expected_type}, "mate type matched" if ok else "mate type mismatch", "blocking" if ok else severity)
        if mate.get("suppressed") is True:
            add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "mate_suppressed", str(name), mate, "mate is suppressed", severity)
        if mate.get("mate_error") not in (1, None):
            add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "mate_error", str(name), {"mate_error": mate.get("mate_error")}, "mate reports a non-success solver/API error", severity)
        if mate_status_unsolved(mate):
            add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "mate_status", str(name), {"status": mate.get("status", mate.get("solver_status"))}, "mate status is not solved/satisfied", severity)
        semantic_pair = spec.get("semantic_pair") or []
        if semantic_pair:
            ok = pair_matches(mate.get("components"), [str(x) for x in semantic_pair])
            target = accepted if ok else decision_bucket(severity, accepted, warnings, not_applicable, failed)
            add_decision(target, "mate_components", str(name), {"actual": mate.get("components"), "expected_semantic_pair": semantic_pair}, "mate references expected components" if ok else "mate component references do not match semantic pair", "blocking" if ok else severity)
        if not spec.get("allow_fixed_fixed") and all_components_fixed(mate.get("components"), by_key):
            add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "mate_between_fixed_components", str(name), {"components": mate.get("components")}, "mate references only fixed components and cannot prove an active assembly constraint", severity)

    part_evidence = part_feature_evidence(report)
    for name, spec in (contract.get("part_features") or {}).items():
        spec = spec if isinstance(spec, dict) else {}
        severity = severity_of(spec)
        if severity not in KNOWN_SEVERITIES:
            add_decision(failed, "contract_severity", str(name), {"severity": severity, "allowed": sorted(KNOWN_SEVERITIES)}, "unknown part feature contract severity")
            continue
        if severity == "not_applicable":
            add_decision(not_applicable, "part_feature_not_applicable", str(name), spec, "part feature check marked not_applicable", severity)
            continue
        evidence = part_evidence.get(str(name))
        required = spec.get("required", True)
        if required and (not isinstance(evidence, dict) or evidence.get("ok") is False):
            add_decision(decision_bucket(severity, accepted, warnings, not_applicable, failed), "part_feature_missing", str(name), spec, "required part feature evidence missing or failed", severity)
            continue
        if not isinstance(evidence, dict):
            continue
        features = evidence.get("features", [])
        names = feature_names(features)
        add_decision(accepted, "part_feature_evidence", str(name), {"feature_count": len(names)}, "part feature evidence present")
        for required_name in spec.get("required_names", []) or []:
            ok = any(str(required_name) in actual for actual in names)
            target = accepted if ok else decision_bucket(severity, accepted, warnings, not_applicable, failed)
            add_decision(target, "part_feature_name", f"{name}:{required_name}", {"available": sorted(names), "required": required_name}, "required part feature name present" if ok else "required part feature name missing", "blocking" if ok else severity)
        for semantic, expected in (spec.get("required_semantics") or {}).items():
            expected = expected if isinstance(expected, dict) else {}
            minimum = int(expected.get("min_count", 1) or 1)
            actual = semantic_feature_count(features, str(semantic))
            ok = actual >= minimum
            target = accepted if ok else decision_bucket(severity, accepted, warnings, not_applicable, failed)
            add_decision(target, "part_feature_semantic", f"{name}:{semantic}", {"actual": actual, "minimum": minimum}, "required semantic feature count met" if ok else "required semantic feature count below contract", "blocking" if ok else severity)

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not failed,
        "accepted": accepted,
        "warnings": warnings,
        "not_applicable": not_applicable,
        "failed": failed,
        "summary": {"accepted": len(accepted), "warnings": len(warnings), "not_applicable": len(not_applicable), "failed": len(failed)},
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
