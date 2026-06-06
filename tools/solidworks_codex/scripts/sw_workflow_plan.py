#!/usr/bin/env python3
"""Build an intent-scoped CAD workflow plan for part and assembly loops.

This is one level above change-plan: it does not assume there is already one
open model and one narrow edit. It helps a reasoning agent compose design,
part modeling, self-check, feedback edits, assembly insertion, and assembly
verification without forcing a shaper-specific or release-grade workflow.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

KNOWN_INTENTS = {"auto", "single_part", "part_to_assembly", "assembly", "mechanism_assembly"}
KNOWN_RUNTIME_BUDGETS = {"fast", "standard", "strict"}


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def load_validation_profiles() -> Any:
    path = Path(__file__).resolve().parent / "sw_validation_profiles.py"
    spec = importlib.util.spec_from_file_location("sw_validation_profiles_for_workflow", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def normalize_intent(intent: str) -> str:
    value = (intent or "auto").strip().lower().replace("-", "_")
    aliases = {
        "infer": "auto",
        "detect": "auto",
        "part": "single_part",
        "single": "single_part",
        "part_assembly": "part_to_assembly",
        "part_to_asm": "part_to_assembly",
        "assembly_design": "assembly",
        "mechanism": "mechanism_assembly",
    }
    normalized = aliases.get(value, value)
    if normalized not in KNOWN_INTENTS:
        raise ValueError(f"unknown workflow intent: {intent}")
    return normalized


def goal_has_any(lowered: str, terms: tuple[str, ...]) -> bool:
    return any(term in lowered for term in terms)


def classify_intent(goal: str, requested_intent: str) -> dict[str, Any]:
    normalized = normalize_intent(requested_intent)
    lowered = goal.lower()
    signals: list[str] = []
    if goal_has_any(lowered, ("validate", "validation", "inspect", "check", "verify", "诊断", "验证", "检查", "校验")):
        signals.append("validation")
    if goal_has_any(lowered, (".sldasm", "assembly", "assembl", "mate", "component", "fit", "interference", "装配", "组件", "配合", "干涉")):
        signals.append("assembly")
    if goal_has_any(lowered, ("mechanism", "motion", "slider", "crank", "linkage", "dof", "limit", "sweep", "机构", "运动", "滑块", "曲柄", "自由度", "行程")):
        signals.append("mechanism")
    if goal_has_any(lowered, (".sldprt", "part", "bracket", "plate", "hole", "slot", "boss", "cut", "零件", "支架", "板", "孔", "槽")):
        signals.append("part")
    if goal_has_any(lowered, ("modify", "edit", "change", "adjust", "repair", "fix", "修改", "调整", "修复")):
        signals.append("modification")
    if goal_has_any(lowered, ("create", "build", "design", "generate", "make", "创建", "设计", "生成", "建模")):
        signals.append("creation")
    if goal_has_any(lowered, ("without changing", "no mutation", "read-only", "readonly", "只读", "不修改", "不要修改")):
        signals.append("read_only")

    if normalized != "auto":
        resolved_intent = normalized
        cad_scope = "validation_only" if "validation" in signals and "read_only" in signals else normalized
    elif "mechanism" in signals:
        resolved_intent = "mechanism_assembly"
        cad_scope = "mechanism"
    elif "assembly" in signals and "part" in signals and "creation" in signals:
        resolved_intent = "part_to_assembly"
        cad_scope = "part_to_assembly"
    elif "assembly" in signals:
        resolved_intent = "assembly"
        cad_scope = "validation_only" if "validation" in signals and ("read_only" in signals or "creation" not in signals) else "assembly"
    else:
        resolved_intent = "single_part"
        cad_scope = "part_modify" if "modification" in signals else "single_part"

    source = "explicit_action" if normalized != "auto" else "goal_text"
    non_goals = [
        "do not mutate native files when cad_scope is validation_only",
        "do not infer exact dimensions from broad category words",
    ]
    if resolved_intent != "mechanism_assembly":
        non_goals.append("do not require mechanism motion evidence unless mechanism signals or explicit action request it")
    return {
        "artifact": "intent_classification",
        "source": source,
        "requested_intent": normalized,
        "resolved_intent": resolved_intent,
        "cad_scope": cad_scope,
        "selected_profile": public_profile_name(selected_profile_for_intent(resolved_intent)),
        "detected_signals": signals,
        "non_goals": non_goals,
    }


def normalize_budget(runtime_budget: str) -> str:
    value = (runtime_budget or "standard").strip().lower().replace("-", "_")
    if value not in KNOWN_RUNTIME_BUDGETS:
        raise ValueError(f"unknown runtime budget: {runtime_budget}")
    return value


def profile_blocking(profile: Any) -> list[str]:
    return [check.name for check in profile.checks if check.severity == "blocking"]


def profile_warnings(profile: Any) -> list[str]:
    return [check.name for check in profile.checks if check.severity == "warning"]


def profile_not_applicable(profile: Any) -> list[str]:
    return [check.name for check in profile.checks if check.severity == "not_applicable"]


def public_profile_name(profile_name: str) -> str:
    names = {
        "assembly": "assembly_static",
        "mechanism_assembly": "mechanism_lite",
    }
    return names.get(profile_name, profile_name)


def stage(
    name: str,
    purpose: str,
    validation_profile: str,
    required_evidence: list[str],
    candidate_tools: list[str],
    profile: Any,
    exit_criteria: list[str],
    optional: bool = False,
) -> dict[str, Any]:
    return {
        "name": name,
        "purpose": purpose,
        "validation_profile": validation_profile,
        "required_evidence": required_evidence,
        "blocking_checks": profile_blocking(profile),
        "warning_checks": profile_warnings(profile),
        "candidate_tools": candidate_tools,
        "exit_criteria": exit_criteria,
        "optional": optional,
    }


def build_profiles(vp: Any, runtime_budget: str) -> dict[str, Any]:
    return {
        "draft_part": vp.validation_profile_for_intent("draft_part", runtime_budget=runtime_budget),
        "single_part": vp.validation_profile_for_intent("single_part", runtime_budget=runtime_budget),
        "assembly": vp.validation_profile_for_intent("assembly", runtime_budget=runtime_budget),
        "mechanism_assembly": vp.validation_profile_for_intent("mechanism_assembly", runtime_budget=runtime_budget),
    }


def selected_profile_for_intent(intent: str) -> str:
    if intent == "mechanism_assembly":
        return "mechanism_assembly"
    if intent in {"part_to_assembly", "assembly"}:
        return "assembly"
    return "single_part"


def validation_profile_selection(
    intent: str,
    runtime_budget: str,
    profiles: dict[str, Any],
    stages: list[dict[str, Any]],
    vp: Any,
) -> dict[str, Any]:
    profile_name = selected_profile_for_intent(intent)
    profile = profiles[profile_name]
    return {
        "artifact": "validation_profile_selection",
        "requested_intent": intent,
        "runtime_budget": runtime_budget,
        "source_profile": profile_name,
        "selected_profile": public_profile_name(profile_name),
        "blocking_checks": profile_blocking(profile),
        "warning_checks": profile_warnings(profile),
        "not_applicable_checks": profile_not_applicable(profile),
        "stage_profiles": [
            {
                "stage": item["name"],
                "profile": public_profile_name(item["validation_profile"]),
                "source_profile": item["validation_profile"],
            }
            for item in stages
        ],
        "extra_checks": [],
        "decision": vp.profile_decision_report(profile),
        "acceptance_rule": (
            "Use the selected profile as the handoff gate: single-part work keeps "
            "assembly and motion checks not-applicable, while mechanism work requires "
            "motion evidence when the runtime budget leaves it blocking."
        ),
    }


def base_part_stages(goal: str, profiles: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        stage(
            "design_brief",
            "Capture design intent, interfaces, target dimensions, and acceptance depth before creating geometry.",
            "draft_part",
            ["goal", "intended_units", "key_dimensions", "interfaces", "validation_profile"],
            ["design-review", "change-plan", "model-understand"],
            profiles["draft_part"],
            ["The next modeling step has named features, rough dimensions, and known unknowns."],
        ),
        stage(
            "part_model",
            "Create or modify one part with named sketches/features and a bounded file scope.",
            "draft_part",
            ["native_sldprt", "feature_names", "dimension_handles", "backup_scope"],
            ["template-macro", "safe-set-dimension", "rebuild", "inspect"],
            profiles["draft_part"],
            ["Native SLDPRT exists or the active part was modified in a backed-up scope."],
        ),
        stage(
            "part_self_check",
            "Verify the part before it is allowed into an assembly or another edit loop.",
            "single_part",
            ["part_geometry_readback", "rebuild_report", "feature_inventory", "mass_properties"],
            ["inspect", "mass", "compare", "change-verify"],
            profiles["single_part"],
            ["Requested holes, slots, cuts, bosses, and semantic features are visible in evidence."],
        ),
        stage(
            "part_feedback_edit",
            "Apply one evidence-driven correction when part self-check or assembly fit exposes a gap.",
            "single_part",
            ["compare_delta", "allowed_change_contract", "backup_status"],
            ["safe-set-dimension", "template-macro", "backup", "restore-backup", "change-verify"],
            profiles["single_part"],
            ["The delta is intentionally scoped and can be accepted, iterated, or restored."],
        ),
    ]


def assembly_stages(intent: str, profiles: dict[str, Any]) -> list[dict[str, Any]]:
    profile_name = "mechanism_assembly" if intent == "mechanism_assembly" else "assembly"
    profile = profiles[profile_name]
    stages = [
        stage(
            "assembly_insert",
            "Insert checked parts into an assembly with explicit placement, grounding policy, and connection intent.",
            "assembly",
            ["native_sldasm", "component_list", "component_transforms", "grounding_policy"],
            ["inspect", "component-state", "mate-macro", "assembly-contract"],
            profiles["assembly"],
            ["Components are present, intentionally fixed/floating, and traceable to native files."],
        ),
        stage(
            "assembly_self_check",
            "Verify placement, mate/readback evidence, static interference, and functional adjacency.",
            profile_name,
            ["assembly_component_placements", "mate_reference_components", "interference_report", "model_understanding"],
            ["inspect", "interference", "assembly-contract", "model-understand", "report-context"],
            profile,
            ["Blocking assembly checks are satisfied or downgraded with explicit rationale."],
        ),
    ]
    if intent == "mechanism_assembly":
        stages.append(stage(
            "motion_or_dof_check",
            "Check mechanism freedom and path risk only when mechanism intent requires it.",
            "mechanism_assembly",
            ["constraint_dof_intent", "motion_sweep_collision", "clearance_tolerance_screen"],
            ["model-understand", "interference", "selection-report", "assembly-contract"],
            profiles["mechanism_assembly"],
            ["Motion/DOF gaps are either verified, scoped as future work, or reported as blocking."],
        ))
    return stages


def feedback_edges(intent: str) -> list[dict[str, str]]:
    edges = [
        {"from": "part_self_check", "to": "part_feedback_edit", "condition": "part evidence is missing, stale, or shape semantics fail"},
        {"from": "part_feedback_edit", "to": "part_self_check", "condition": "one accepted edit was made"},
    ]
    if intent in {"part_to_assembly", "assembly", "mechanism_assembly"}:
        edges.extend([
            {"from": "part_self_check", "to": "assembly_insert", "condition": "part-level blocking checks pass"},
            {"from": "assembly_insert", "to": "assembly_self_check", "condition": "native assembly exists and components are inserted"},
            {"from": "assembly_self_check", "to": "part_feedback_edit", "condition": "assembly check exposes a part geometry/interface issue"},
            {"from": "assembly_self_check", "to": "assembly_insert", "condition": "assembly issue is placement, mate, grounding, or component selection"},
        ])
    if intent == "mechanism_assembly":
        edges.extend([
            {"from": "assembly_self_check", "to": "motion_or_dof_check", "condition": "static assembly checks pass"},
            {"from": "motion_or_dof_check", "to": "part_feedback_edit", "condition": "motion or clearance issue requires geometry change"},
            {"from": "motion_or_dof_check", "to": "assembly_insert", "condition": "motion or clearance issue requires constraint/layout change"},
        ])
    edges.append({"from": "handoff_or_iterate", "to": "design_brief", "condition": "scope changes or the user asks for a new variant"})
    return edges


def candidate_actions(intent: str) -> list[dict[str, str]]:
    actions = [
        {"tool": "design-review", "why": "Review evidence and open questions before choosing a modeling path."},
        {"tool": "template-macro", "why": "Generate common medium-difficulty part primitives when a template fits the intent."},
        {"tool": "inspect", "why": "Read current native SolidWorks state after each create/edit step."},
        {"tool": "change-verify", "why": "Reject unintended deltas after a guarded edit."},
        {"tool": "model-understand", "why": "Build task-scoped reasoning context instead of using a fixed checklist."},
    ]
    if intent in {"part_to_assembly", "assembly", "mechanism_assembly"}:
        actions.extend([
            {"tool": "assembly-contract", "why": "Validate component placement, mate/readback, fixed state, and semantic pairs offline."},
            {"tool": "interference", "why": "Use live SolidWorks for final static interference evidence."},
            {"tool": "mate-macro", "why": "Create reviewable mate macros only after selection evidence is known."},
        ])
    return actions


def assumption_ledger(goal: str, intent: str, runtime_budget: str) -> dict[str, Any]:
    items = [
        {
            "topic": "dimensions",
            "severity": "assumption",
            "statement": "Dimensions not stated in the goal are placeholders until inspect evidence, user constraints, or a design brief records exact values.",
            "required_resolution": "Record key driving dimensions before creating or editing native geometry.",
            "blocks_stage": "",
        },
        {
            "topic": "materials",
            "severity": "assumption",
            "statement": "Material, density, finish, and manufacturing process are unknown unless the source model or goal names them.",
            "required_resolution": "Keep material-dependent mass, strength, and DFM/DFA checks as warnings unless the selected profile requires them.",
            "blocks_stage": "",
        },
        {
            "topic": "simplified_geometry",
            "severity": "warning",
            "statement": "Templates and generated macros may simplify fillets, chamfers, threads, cosmetic details, and vendor hardware.",
            "required_resolution": "List omitted or simplified features in worklog/handoff before accepting the artifact.",
            "blocks_stage": "",
        },
        {
            "topic": "validation_scope",
            "severity": "warning",
            "statement": f"The `{runtime_budget}` runtime budget controls how expensive validation can be for `{intent}` intent.",
            "required_resolution": "Escalate to strict validation or add explicit extra_checks when the task is release-like or safety-critical.",
            "blocks_stage": "",
        },
        {
            "topic": "native_write_safety",
            "severity": "blocker",
            "statement": "Any native file mutation without a backup target and rollback path is blocked.",
            "required_resolution": "Run backup or safe-set-dimension and record backup_status before a write command.",
            "blocks_stage": "part_model",
        },
    ]
    if intent in {"part_to_assembly", "assembly", "mechanism_assembly"}:
        items.append({
            "topic": "assembly_interfaces",
            "severity": "blocker",
            "statement": "Assembly mates or placement changes are blocked when target interfaces/components cannot be identified from inspect, selection, or interface-index evidence.",
            "required_resolution": "Run inspect/model-understand/interface-index/selection-report before creating mate macros or accepting component placement.",
            "blocks_stage": "assembly_insert",
        })
    if intent == "mechanism_assembly":
        items.append({
            "topic": "motion_evidence",
            "severity": "blocker",
            "statement": "Mechanism acceptance is blocked when DOF intent, limit positions, or collision sampling evidence is absent.",
            "required_resolution": "Run mechanism-profile checks and record unresolved DOF or motion-sweep gaps before handoff.",
            "blocks_stage": "motion_or_dof_check",
        })
    return {
        "artifact": "assumption_ledger",
        "goal_excerpt": goal[:160],
        "items": items,
        "acceptance_rule": "Reports must distinguish assumption, warning, and blocker; blockers stop the named stage until resolved or explicitly rescoped.",
    }


def runtime_budget_plan(intent: str, runtime_budget: str) -> dict[str, Any]:
    budget_table = {
        "fast": {
            "expected_solidworks_sessions": 1,
            "memory_ceiling_mb": 2500,
            "timeout_seconds": 120,
            "rebuild_scope": "active document or directly changed part/assembly only",
            "extra_checks_policy": "skip release-like checks unless a blocker needs one focused query",
        },
        "standard": {
            "expected_solidworks_sessions": 1,
            "memory_ceiling_mb": 3500,
            "timeout_seconds": 300,
            "rebuild_scope": "changed native files plus dependent assembly inspect/compare loop",
            "extra_checks_policy": "run profile blocking checks and selected warnings tied to the goal",
        },
        "strict": {
            "expected_solidworks_sessions": 2,
            "memory_ceiling_mb": 4500,
            "timeout_seconds": 600,
            "rebuild_scope": "full affected assembly plus reopen/readback validation where practical",
            "extra_checks_policy": "run profile blocking checks, relevant warnings, and documented extra_checks",
        },
    }
    selected = dict(budget_table[runtime_budget])
    if intent == "mechanism_assembly":
        selected["expected_solidworks_sessions"] = max(2, selected["expected_solidworks_sessions"])
        selected["rebuild_scope"] += "; include mechanism DOF/clearance sampling when available"
    elif intent == "single_part":
        selected["expected_solidworks_sessions"] = 1
    justification_policy = {
        "artifact": "full_rebuild_justification_policy",
        "default_decision": "local_repair_first",
        "allowed_reasons": [
            "stale_base",
            "invalid_topology",
            "missing_interface",
            "cheaper_regeneration",
        ],
        "required_fields": [
            "selected_reason",
            "rejected_local_repairs",
            "affected_files",
            "expected_validation_reports",
            "rollback_path",
        ],
        "blocks_full_rebuild_without_reason": True,
        "acceptance_rule": "A full rebuild is allowed only when one allowed reason is selected and local repair options are explicitly rejected with evidence.",
        "execution_gate": {
            "tool": "workflow-plan",
            "decision": "block_full_rebuild_until_authorized",
            "required_evidence": [
                "selected_reason",
                "rejected_local_repairs",
                "affected_files",
                "backup_status",
                "rollback_path",
                "expected_validation_reports",
            ],
            "allowed_next_tools": ["backup", "backup-status", "restore-backup", "assembly-review-pipeline", "live-gate"],
        },
        "request_template": {
            "selected_reason": "",
            "rejected_local_repairs": [],
            "affected_files": [],
            "backup_status": "",
            "rollback_path": "",
            "expected_validation_reports": [],
            "approval_status": "pending",
        },
    }
    return {
        "artifact": "runtime_budget_plan",
        "intent": intent,
        "budget": runtime_budget,
        "expected_solidworks_sessions": selected["expected_solidworks_sessions"],
        "rebuild_scope": selected["rebuild_scope"],
        "memory_ceiling_mb": selected["memory_ceiling_mb"],
        "timeout_seconds": selected["timeout_seconds"],
        "cleanup_policy": "scan generated lock files before/after live work, close generated documents, and keep user models out of cleanup scope",
        "full_rebuild_requires_reason": True,
        "full_rebuild_justification_policy": justification_policy,
        "extra_checks_policy": selected["extra_checks_policy"],
    }


def design_intent(goal: str, intent: str) -> dict[str, Any]:
    lowered = goal.lower()
    part_hints = [
        name
        for name, keys in (
            ("bracket", ("bracket", "支架", "mount")),
            ("plate", ("plate", "板", "盖板")),
            ("housing", ("housing", "壳体", "箱体")),
            ("shaft_or_pin", ("shaft", "pin", "轴", "销")),
            ("fastener", ("bolt", "screw", "螺栓", "螺钉")),
        )
        if any(key in lowered for key in keys)
    ]
    if not part_hints:
        part_hints = ["primary_part"]
    interfaces = ["mounting_faces", "datum_planes_or_axes"]
    if intent in {"part_to_assembly", "assembly", "mechanism_assembly"}:
        interfaces.extend(["assembly_mate_interfaces", "clearance_sensitive_neighbors"])
    motion_pairs: list[str] = []
    if intent == "mechanism_assembly":
        motion_pairs.extend(["revolute_pairs", "prismatic_pairs", "limit_positions"])
    editable_parameters = ["key_dimensions", "feature_depths_or_offsets"]
    if any(key in lowered for key in ("hole", "孔", "bolt", "螺")):
        editable_parameters.append("hole_diameter_pattern_or_spacing")
    validation_profile = public_profile_name(selected_profile_for_intent(intent))
    return {
        "artifact": "design_intent",
        "goal": goal,
        "scope": intent,
        "validation_profile": validation_profile,
        "assumptions_source": "workflow-plan heuristic; refine with inspect/model-understand/worklog before mutation",
        "parts": part_hints,
        "subassemblies": ["functional_assembly"] if intent in {"part_to_assembly", "assembly", "mechanism_assembly"} else [],
        "interfaces": interfaces,
        "motion_pairs": motion_pairs,
        "standard_parts": ["fasteners_or_locators_if_named"] if any(key in lowered for key in ("bolt", "screw", "螺", "pin", "销")) else [],
        "editable_parameters": editable_parameters,
        "non_goals": [
            "do not assume exact dimensions not present in goal or inspect evidence",
            "do not accept broad release-grade engineering claims unless the selected profile or extra_checks requires them",
        ],
    }


def build_plan(goal: str, intent: str, runtime_budget: str) -> dict[str, Any]:
    classification = classify_intent(goal, intent)
    normalized_intent = classification["resolved_intent"]
    budget = normalize_budget(runtime_budget)
    vp = load_validation_profiles()
    profiles = build_profiles(vp, budget)
    stages = base_part_stages(goal, profiles)
    if normalized_intent in {"part_to_assembly", "assembly", "mechanism_assembly"}:
        stages.extend(assembly_stages(normalized_intent, profiles))
    stages.append(stage(
        "handoff_or_iterate",
        "Record accepted evidence, unresolved risks, artifacts, and the next narrow loop.",
        normalized_intent if normalized_intent != "part_to_assembly" else "assembly",
        ["worklog", "handoff_bundle", "accepted_reports", "next_step"],
        ["worklog", "handoff-bundle", "finalize"],
        profiles["assembly"] if normalized_intent != "single_part" else profiles["single_part"],
        ["A future agent can replay the state without trusting memory or stale reports."],
    ))
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "goal": goal,
        "intent": normalized_intent,
        "runtime_budget": budget,
        "intent_classification": classification,
        "design_intent": design_intent(goal, normalized_intent),
        "stage_graph": stages,
        "feedback_edges": feedback_edges(normalized_intent),
        "candidate_actions": candidate_actions(normalized_intent),
        "validation_profile_selection": validation_profile_selection(normalized_intent, budget, profiles, stages, vp),
        "assumption_ledger": assumption_ledger(goal, normalized_intent, budget),
        "runtime_budget_plan": runtime_budget_plan(normalized_intent, budget),
        "principle": "Compose small evidence loops: design, model, inspect, adjust, assemble, inspect again.",
    }


def markdown(plan: dict[str, Any]) -> str:
    lines = ["# Mechanical CAD Workflow Plan", ""]
    lines.extend([
        f"- Goal: {plan['goal']}",
        f"- Intent: `{plan['intent']}`",
        f"- Runtime budget: `{plan['runtime_budget']}`",
        f"- Principle: {plan['principle']}",
        "",
        "## Intent Classification",
    ])
    classification = plan.get("intent_classification") or {}
    lines.extend([
        f"- CAD scope: `{classification.get('cad_scope')}`",
        f"- Source: `{classification.get('source')}`",
        f"- Detected signals: {', '.join(f'`{x}`' for x in classification.get('detected_signals', [])) or '`<none>`'}",
        "",
        f"- Requested intent: `{classification.get('requested_intent')}`",
        f"- Resolved intent: `{classification.get('resolved_intent')}`",
        f"- Selected profile: `{classification.get('selected_profile')}`",
        f"- Non-goals: {'; '.join(classification.get('non_goals', []))}",
        "",
        "## Design Intent Details",
    ])
    intent = plan.get("design_intent") or {}
    lines.extend([
        f"- Scope: `{intent.get('scope')}`",
        f"- Validation profile: `{intent.get('validation_profile')}`",
        f"- Parts: {', '.join(f'`{x}`' for x in intent.get('parts', [])) or '`<none>`'}",
        f"- Interfaces: {', '.join(f'`{x}`' for x in intent.get('interfaces', [])) or '`<none>`'}",
        f"- Motion pairs: {', '.join(f'`{x}`' for x in intent.get('motion_pairs', [])) or '`<none>`'}",
        f"- editable parameters: {', '.join(f'`{x}`' for x in intent.get('editable_parameters', [])) or '`<none>`'}",
        f"- Non-goals: {'; '.join(intent.get('non_goals', []))}",
        "",
        "## Validation Profile Selection",
    ])
    selection = plan.get("validation_profile_selection") or {}
    lines.extend([
        f"- Selected profile: `{selection.get('selected_profile')}` from `{selection.get('source_profile')}`",
        f"- Runtime budget: `{selection.get('runtime_budget')}`",
        f"- Blocking checks: {', '.join(f'`{x}`' for x in selection.get('blocking_checks', [])) or '`<none>`'}",
        f"- Not-applicable checks: {', '.join(f'`{x}`' for x in selection.get('not_applicable_checks', [])) or '`<none>`'}",
        f"- Acceptance rule: {selection.get('acceptance_rule', '')}",
        "",
        "## Stages",
    ])
    for index, item in enumerate(plan["stage_graph"], 1):
        lines.extend([
            f"### {index}. `{item['name']}`",
            "",
            f"- Purpose: {item['purpose']}",
            f"- Validation profile: `{item['validation_profile']}`",
            f"- Required evidence: {', '.join(f'`{x}`' for x in item['required_evidence'])}",
            f"- Blocking checks: {', '.join(f'`{x}`' for x in item['blocking_checks']) or '`<none>`'}",
            f"- Candidate tools: {', '.join(f'`{x}`' for x in item['candidate_tools'])}",
            f"- Exit criteria: {'; '.join(item['exit_criteria'])}",
            "",
        ])
    lines.extend(["## Feedback Edges", ""])
    for edge in plan["feedback_edges"]:
        lines.append(f"- `{edge['from']}` -> `{edge['to']}` when {edge['condition']}")
    ledger = plan.get("assumption_ledger") or {}
    lines.extend(["", "## Assumption Ledger", ""])
    lines.append(f"- Acceptance rule: {ledger.get('acceptance_rule', '')}")
    for item in ledger.get("items", []):
        blocked = f"; blocks `{item['blocks_stage']}`" if item.get("blocks_stage") else ""
        lines.append(f"- `{item['severity']}` `{item['topic']}`: {item['statement']} Resolution: {item['required_resolution']}{blocked}")
    runtime = plan.get("runtime_budget_plan") or {}
    lines.extend(["", "## Runtime Budget Plan", ""])
    lines.extend([
        f"- Budget: `{runtime.get('budget')}` for `{runtime.get('intent')}`",
        f"- Expected SolidWorks sessions: `{runtime.get('expected_solidworks_sessions')}`",
        f"- Rebuild scope: {runtime.get('rebuild_scope')}",
        f"- memory ceiling: `{runtime.get('memory_ceiling_mb')}` MB",
        f"- Timeout: `{runtime.get('timeout_seconds')}` seconds",
        f"- Cleanup policy: {runtime.get('cleanup_policy')}",
        f"- Full rebuild requires reason: `{runtime.get('full_rebuild_requires_reason')}`",
        f"- Extra checks policy: {runtime.get('extra_checks_policy')}",
    ])
    justification = runtime.get("full_rebuild_justification_policy") or {}
    lines.extend(["", "## Full Rebuild Justification", ""])
    lines.extend([
        f"- Default decision: `{justification.get('default_decision')}`",
        f"- Allowed reasons: {', '.join(f'`{x}`' for x in justification.get('allowed_reasons', [])) or '`<none>`'}",
        f"- Required fields: {', '.join(f'`{x}`' for x in justification.get('required_fields', [])) or '`<none>`'}",
        f"- Blocks without reason: `{justification.get('blocks_full_rebuild_without_reason')}`",
        f"- Acceptance rule: {justification.get('acceptance_rule', '')}",
    ])
    lines.extend(["", "## Candidate Actions", ""])
    for action in plan["candidate_actions"]:
        lines.append(f"- `{action['tool']}`: {action['why']}")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--goal", required=True)
    parser.add_argument("--intent", default="single_part")
    parser.add_argument("--runtime-budget", default="standard")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/workflow_plan.md")
    parser.add_argument("--json-out", default="tools/solidworks_codex/reports/workflow_plan.json")
    args = parser.parse_args()
    plan = build_plan(args.goal, args.intent, args.runtime_budget)
    out = resolve(args.out)
    jout = resolve(args.json_out)
    out.parent.mkdir(parents=True, exist_ok=True)
    jout.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(plan), encoding="utf-8")
    jout.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out), "json_out": str(jout), "stages": len(plan["stage_graph"])}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
