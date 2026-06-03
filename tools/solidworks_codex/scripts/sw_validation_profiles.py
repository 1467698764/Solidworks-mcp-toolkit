#!/usr/bin/env python3
"""Validation profile selection for SolidWorks MCP workflows.

Profiles keep acceptance proportional to user intent. A draft part should not be
blocked by mechanism motion checks, while a complete mechanism assembly should be
blocked by mate, clearance, and motion evidence. Reasoning agents may add checks
per task without making every heavy engineering gate global by default.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ValidationCheck:
    name: str
    layer: str
    severity: str
    reason: str
    evidence_scope: str = "standard"


@dataclass(frozen=True)
class ValidationProfile:
    name: str
    intent: str
    checks: tuple[ValidationCheck, ...]


KNOWN_LAYERS = {"geometry", "assembly", "engineering", "mcp_quality"}
KNOWN_SEVERITIES = {"blocking", "warning", "not_applicable"}
KNOWN_RUNTIME_BUDGETS = {"fast", "standard", "strict"}
EXPENSIVE_CHECKS = {"motion_sweep_collision"}


def C(name: str, layer: str, severity: str, reason: str, evidence_scope: str = "standard") -> ValidationCheck:
    if layer not in KNOWN_LAYERS:
        raise ValueError(f"unknown validation layer: {layer}")
    if severity not in KNOWN_SEVERITIES:
        raise ValueError(f"unknown validation severity: {severity}")
    return ValidationCheck(name=name, layer=layer, severity=severity, reason=reason, evidence_scope=evidence_scope)


BASE_PART_CHECKS = (
    C("native_artifacts", "geometry", "blocking", "native SLDPRT/SLDASM evidence is the deliverable"),
    C("rebuild_health", "mcp_quality", "blocking", "model must rebuild without missing references or rebuild errors"),
    C("part_shape_semantics", "geometry", "blocking", "requested holes, slots, cuts, bosses, and named semantic features exist"),
    C("mass_properties", "engineering", "warning", "mass/volume/center of mass are useful sanity checks but not always required"),
    C("dfm_screen", "engineering", "warning", "lightweight manufacturability screen should inform but not block drafts"),
    C("dfa_screen", "engineering", "warning", "assembly access/order is not always relevant for a single draft part"),
)

ASSEMBLY_OPTIONAL_FOR_SINGLE_PART = (
    C("assembly_mate_semantics", "assembly", "not_applicable", "single-part work has no assembly mate network"),
    C("component_placements", "assembly", "not_applicable", "single-part work has no component placement graph"),
    C("static_interference", "geometry", "not_applicable", "single-part work has no inter-component interference"),
    C("functional_adjacency", "assembly", "not_applicable", "single-part work has no functional component adjacency"),
    C("constraint_dof_intent", "assembly", "not_applicable", "single-part work has no assembly degrees of freedom"),
    C("motion_sweep_collision", "assembly", "not_applicable", "single-part work has no mechanism motion path"),
)

ASSEMBLY_BLOCKING_CHECKS = (
    C("assembly_mate_semantics", "assembly", "blocking", "mate readback must match intended component pairs"),
    C("component_placements", "assembly", "blocking", "component transforms must match the accepted assembly layout"),
    C("static_interference", "geometry", "blocking", "final assembly pose must be free of unintended interferences"),
    C("functional_adjacency", "assembly", "blocking", "functional pairs must be spatially connected, not merely inventoried"),
)

MECHANISM_BLOCKING_CHECKS = (
    C("constraint_dof_intent", "assembly", "blocking", "fixed, sliding, and revolute elements must match intended freedom"),
    C("motion_sweep_collision", "assembly", "blocking", "mechanism path must avoid collision/cardinal dead positions within scope"),
    C("clearance_tolerance_screen", "geometry", "blocking", "pins, slots, guides, and fasteners need plausible engineering clearance"),
)

ENGINEERING_WARNINGS = (
    C("bom_metadata", "engineering", "warning", "BOM/material/vendor metadata improves downstream traceability"),
    C("strength_stiffness_screen", "engineering", "warning", "rule-level load path and weak-section screening is advisory unless requested"),
    C("drawing_bom_readiness", "engineering", "warning", "drawings, exploded views, and BOM are downstream deliverables"),
    C("full_fea", "engineering", "not_applicable", "full FEA is expensive and should be explicit, not default"),
)


def normalize_intent(intent: str | None) -> str:
    value = (intent or "draft_part").strip().lower().replace("-", "_")
    aliases = {
        "draft": "draft_part",
        "part": "single_part",
        "single": "single_part",
        "assembly": "assembly",
        "mechanism": "mechanism_assembly",
        "engineering": "engineering_release",
        "release": "engineering_release",
    }
    return aliases.get(value, value)


def validation_profile_for_intent(
    intent: str | None,
    extra_checks: list[dict[str, Any]] | None = None,
    runtime_budget: str = "standard",
) -> ValidationProfile:
    normalized = normalize_intent(intent)
    budget = (runtime_budget or "standard").strip().lower().replace("-", "_")
    if budget not in KNOWN_RUNTIME_BUDGETS:
        raise ValueError(f"unknown validation runtime budget: {runtime_budget}")
    checks: list[ValidationCheck] = list(BASE_PART_CHECKS)
    if normalized in {"single_part", "draft_part"}:
        checks.extend(ASSEMBLY_OPTIONAL_FOR_SINGLE_PART)
    if normalized in {"assembly", "mechanism_assembly", "engineering_release"}:
        checks.extend(ASSEMBLY_BLOCKING_CHECKS)
    if normalized in {"mechanism_assembly", "engineering_release"}:
        checks.extend(MECHANISM_BLOCKING_CHECKS)
    if normalized == "engineering_release":
        checks.extend(ENGINEERING_WARNINGS)
    else:
        checks.extend(tuple(c for c in ENGINEERING_WARNINGS if c.severity != "not_applicable"))
    if budget == "fast":
        checks = [
            C(check.name, check.layer, "warning", check.reason, check.evidence_scope)
            if check.name in EXPENSIVE_CHECKS and check.severity == "blocking" else check
            for check in checks
        ]
    for item in extra_checks or []:
        checks.append(C(
            str(item["name"]),
            str(item.get("layer", "mcp_quality")),
            str(item.get("severity", "warning")),
            str(item.get("reason", "task-specific reasoning-model check")),
            str(item.get("evidence_scope", "task_specific")),
        ))
    return ValidationProfile(name=normalized, intent=normalized, checks=tuple(checks))


def check_names_by_severity(profile: ValidationProfile, severity: str) -> tuple[str, ...]:
    return tuple(check.name for check in profile.checks if check.severity == severity)


def blocking_check_names(profile: ValidationProfile) -> tuple[str, ...]:
    return check_names_by_severity(profile, "blocking")


def warning_check_names(profile: ValidationProfile) -> tuple[str, ...]:
    return check_names_by_severity(profile, "warning")


def not_applicable_check_names(profile: ValidationProfile) -> tuple[str, ...]:
    return check_names_by_severity(profile, "not_applicable")


def profile_to_dict(profile: ValidationProfile) -> dict[str, Any]:
    return asdict(profile)


def profile_decision_report(profile: ValidationProfile) -> dict[str, Any]:
    """Summarize why a profile blocks some checks and downgrades others.

    This report is meant for MCP callers and reasoning agents: it makes the
    acceptance contract explicit without pretending every possible engineering
    check is globally mandatory.
    """
    layers: dict[str, dict[str, list[str]]] = {}
    for check in profile.checks:
        layer = layers.setdefault(check.layer, {"blocking": [], "warning": [], "not_applicable": []})
        layer[check.severity].append(check.name)
    return {
        "profile": profile.name,
        "intent": profile.intent,
        "blocking": list(blocking_check_names(profile)),
        "warning": list(warning_check_names(profile)),
        "not_applicable": list(not_applicable_check_names(profile)),
        "layers": layers,
        "policy": (
            "Validation is intent-scoped, not global: lightweight work keeps only "
            "native artifacts, rebuild health, and requested shape semantics blocking; "
            "mechanism and release checks are enabled by profile or task-specific extra checks."
        ),
    }
