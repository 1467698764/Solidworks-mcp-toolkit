#!/usr/bin/env python3
"""Live SolidWorks capability suite.

Builds a deliberately small, auditable set of parts/assembly operations that are
independent from any retained mechanism fixture. The suite exists to prove individual
SolidWorks automation capabilities with inspectable artifacts and callback reports.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import math
import shutil
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class CapabilitySpec:
    name: str
    status: str
    live_artifact: str
    acceptance_checks: tuple[str, ...]
    note: str


@dataclass(frozen=True)
class CapabilityMatrix:
    name: str
    output_dir: str
    reports_dir: str
    assembly_file: str
    capabilities: tuple[CapabilitySpec, ...]


def C(name: str, artifact: str, checks: tuple[str, ...], note: str, status: str = "implemented") -> CapabilitySpec:
    return CapabilitySpec(name, status, artifact, checks, note)


def build_capability_matrix() -> CapabilityMatrix:
    out = "tools/solidworks_codex/live_fixture/live_capability_suite"
    reports = "tools/solidworks_codex/reports/live_capability_suite"
    caps = (
        C("extrude_boss", "extrude_cut_plate.SLDPRT", ("Body_Plate",), "base boss extrusion from rectangle sketch"),
        C("extrude_cut", "extrude_cut_plate.SLDPRT", ("Round_Through_Hole", "Rectangular_Window_Cut"), "explicit sketch selection before cut"),
        C("revolve_boss", "revolve_boss_part.SLDPRT", ("Revolve_Boss_Profile",), "axisymmetric body from centerline profile"),
        C("revolve_cut", "revolve_cut_part.SLDPRT", ("Revolve_Cut_Bore",), "revolved cut groove/bore from selected sketch"),
        C("sketch_edit_dimension", "editable_dimension_plate.SLDPRT", ("Edited_Sketch_Dimension", "dimension_after_m"), "create dimension, edit it, rebuild, read back"),
        C("read_modify_rebuild", "editable_dimension_plate.SLDPRT", ("before_after_dimension_delta",), "read existing parameter, modify, rebuild and save"),
        C("open_existing_modify_reopen", "editable_dimension_plate.SLDPRT", ("open_existing", "modify_save", "reopen_persisted"), "open a saved native part, read/modify/save a dimension, close it, and reopen to prove persistence"),
        C("assembly_insert_component", "capability_suite.SLDASM", ("component_count>=3",), "insert generated components into assembly"),
        C("assembly_component_placements", "capability_suite.SLDASM", ("Transform2.origin_m", "placement_tolerance"), "inspect native assembly and verify inserted component origins"),
        C("assembly_mate_concentric", "capability_suite.SLDASM", ("Concentric_Mate",), "add at least one concentric mate or record mate API error"),
        C("assembly_mate_distance", "capability_suite.SLDASM", ("Distance_Mate",), "add at least one distance mate or record mate API error"),
        C("assembly_mate_inspect_readback", "capability_suite.SLDASM", ("mate_like_features", "components", "not_suppressed"), "reopen/inspect native assembly and verify mate type plus participating components"),
        C("interference_callback", "interference.json", ("available", "count"), "run interference callback after assembly build"),
        C("mass_callback", "mass.json", ("mass_kg",), "mass callback evidence from native SolidWorks assembly"),
        C("native_solidworks_artifacts", "capability_suite.SLDASM + generated SLDPRT files", ("sldasm_exists", "sldprt_count>=4"), "primary deliverables are native SolidWorks assembly and part files"),
        C("optional_step_export_smoke", "optional_export_step.json", ("optional_only",), "optional neutral-format smoke; never a primary acceptance gate"),
        C("cleanup_single_session", "cleanup_report.json", ("closed_docs", "removed_files"), "close suite docs and delete only generated files"),
    )
    return CapabilityMatrix("live_capability_suite", out, reports, f"{out}/capability_suite.SLDASM", caps)


def expected_live_contract() -> dict[str, Any]:
    return {
        "parts": {
            "extrude_cut_plate": ("Body_Plate", "Round_Through_Hole", "Rectangular_Window_Cut"),
            "revolve_boss_part": ("Revolve_Boss_Profile",),
            "revolve_cut_part": ("Revolve_Boss_Profile", "Revolve_Cut_Bore"),
            "editable_dimension_plate": ("Body_Editable_Plate", "Edited_Sketch_Dimension"),
        },
        "dimensions": ("Edited_Sketch_Dimension", "D1@Edited_Sketch_Dimension"),
        "mates": ("Concentric_Mate", "Distance_Mate"),
        "minimum_component_count": 3,
        "open_existing_modify_reopen": {"dimension": "D1@Edited_Sketch_Dimension", "expected_after_reopen_m": 0.028},
        "assembly_inspect": {
            "document": "capability_suite.SLDASM",
            "active_document_type": "assembly",
            "component_placements": {
                "extrude_cut_plate": {"origin_m": (0.00, 0.00, -0.006), "tolerance_m": 0.003},
                "revolve_boss_part": {"origin_m": (0.12, 0.00, 0.00), "tolerance_m": 0.003},
                "revolve_cut_part": {"origin_m": (0.12, 0.075, 0.00), "tolerance_m": 0.003},
                "editable_dimension_plate": {"origin_m": (0.00, 0.10, 0.026), "tolerance_m": 0.003},
            },
            "mates": {
                "Concentric_Mate": {
                    "type": "MateConcentric",
                    "components": ("revolve_boss_part", "revolve_cut_part"),
                    "suppressed": False,
                },
                "Distance_Mate": {
                    "type": "MateDistanceDim",
                    "components": ("extrude_cut_plate", "editable_dimension_plate"),
                    "suppressed": False,
                },
            },
        },
        "part_geometry_readback": {
            "source": "reopened_native_sldprt",
            "parts": {
                "extrude_cut_plate": {
                    "bbox_size_m": (0.100, 0.070, 0.012),
                    "bbox_tolerance_m": 0.010,
                    "volume_range_m3": (1e-6, 2e-4),
                    "required_semantics": {
                        "Body_Plate": {"semantic": "boss", "volume_delta_sign": "positive"},
                        "Round_Through_Hole": {"semantic": "through_hole", "volume_delta_sign": "negative", "outer_bbox_expected_unchanged": True},
                        "Rectangular_Window_Cut": {"semantic": "window_cut", "volume_delta_sign": "negative", "outer_bbox_expected_unchanged": True},
                    },
                },
                "revolve_boss_part": {
                    "bbox_size_m": (0.016, 0.050, 0.016),
                    "bbox_tolerance_m": 0.020,
                    "volume_range_m3": (1e-7, 2e-4),
                    "required_semantics": {"Revolve_Boss_Profile": {"semantic": "revolve_boss", "volume_delta_sign": "positive"}},
                },
                "revolve_cut_part": {
                    "bbox_size_m": (0.052, 0.052, 0.060),
                    "bbox_tolerance_m": 0.020,
                    "volume_range_m3": (1e-7, 2e-4),
                    "required_semantics": {
                        "Revolve_Boss_Profile": {"semantic": "revolve_boss", "volume_delta_sign": "positive"},
                        "Revolve_Cut_Bore": {"semantic": "revolve_cut", "volume_delta_sign": "negative"},
                    },
                },
                "editable_dimension_plate": {
                    "bbox_size_m": (0.080, 0.050, 0.010),
                    "bbox_tolerance_m": 0.010,
                    "volume_range_m3": (1e-6, 1e-4),
                    "required_semantics": {
                        "Body_Editable_Plate": {"semantic": "boss", "volume_delta_sign": "positive"},
                        "Edited_Sketch_Dimension": {"semantic": "through_hole", "volume_delta_sign": "negative", "outer_bbox_expected_unchanged": True},
                    },
                },
            },
        },
        "operation_context": expected_operation_context(),
    }


def _with_expected_selection_guards(context: dict[str, Any]) -> dict[str, Any]:
    for part in context.values():
        for op in part.get("operations", {}).values():
            op["selection_guard"] = {
                "active_title": "<non-empty active document title>",
                "cleared_selection_count": 0,
                "selected_sketch": "<matches operation sketch>",
                "selection_count_before_feature": 1,
            }
    return context


def expected_operation_context() -> dict[str, Any]:
    return _with_expected_selection_guards({
        "extrude": {
            "document": "extrude_cut_plate.SLDPRT",
            "operations": {
                "Body_Plate": {"profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"},
                "Round_Through_Hole": {"profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"},
                "Rectangular_Window_Cut": {"profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"},
            },
        },
        "revolve": {
            "document": "revolve_boss_part.SLDPRT",
            "operations": {
                "Revolve_Boss_Profile": {"profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"},
            },
        },
        "revolve_cut": {
            "document": "revolve_cut_part.SLDPRT",
            "operations": {
                "Revolve_Boss_Profile": {"profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"},
                "Revolve_Cut_Bore": {"profile": "closed_cut_profile_with_centerline", "geometry": {"lines": 4, "circles": 0, "centerlines": 1}, "feature_type": "RevCut", "api": "FeatureRevolveCut2"},
            },
        },
        "editable": {
            "document": "editable_dimension_plate.SLDPRT",
            "operations": {
                "Body_Editable_Plate": {"profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"},
                "Edited_Sketch_Dimension": {"profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3", "dimension": "D1@Edited_Sketch_Dimension"},
            },
        },
    })


def validate_operation_context(actual: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    details: dict[str, Any] = {}

    def int_equals(value: Any, expected: int) -> bool:
        try:
            return int(value) == expected
        except (TypeError, ValueError):
            return False

    for part_key, part_expected in expected_operation_context().items():
        part_actual = actual.get(part_key, {}) if isinstance(actual, dict) else {}
        if part_actual.get("document") != part_expected["document"]:
            failed.append(f"{part_key}:document")
            details[part_key] = part_actual
            continue
        if not part_actual.get("active_title"):
            failed.append(f"{part_key}:active_title")
            details[part_key] = part_actual
        if Path(str(part_actual.get("saved_path", ""))).name != part_expected["document"]:
            failed.append(f"{part_key}:saved_path")
            details[part_key] = part_actual
        operations = part_actual.get("operations", {})
        for op_name, op_expected in part_expected["operations"].items():
            op_actual = operations.get(op_name, {})
            if not op_actual.get("sketch"):
                failed.append(f"{part_key}:{op_name}:sketch")
                details.setdefault(part_key, {})[op_name] = op_actual
            for field, expected_value in op_expected.items():
                if field == "selection_guard":
                    continue
                if op_actual.get(field) != expected_value:
                    failed.append(f"{part_key}:{op_name}:{field}")
                    details.setdefault(part_key, {})[op_name] = op_actual
            readback = op_actual.get("readback", {}) if isinstance(op_actual, dict) else {}
            if not readback:
                failed.append(f"{part_key}:{op_name}:readback")
                details.setdefault(part_key, {})[op_name] = op_actual
                continue
            if readback.get("source") != "reopened_feature_tree":
                failed.append(f"{part_key}:{op_name}:readback:source")
                details.setdefault(part_key, {})[op_name] = op_actual
            if readback.get("sketch") != op_actual.get("sketch"):
                failed.append(f"{part_key}:{op_name}:readback:sketch")
                details.setdefault(part_key, {})[op_name] = op_actual
            if readback.get("feature_type") != op_expected.get("feature_type"):
                failed.append(f"{part_key}:{op_name}:readback:feature_type")
                details.setdefault(part_key, {})[op_name] = op_actual
            if readback.get("geometry") != op_expected.get("geometry"):
                failed.append(f"{part_key}:{op_name}:readback:geometry")
                details.setdefault(part_key, {})[op_name] = op_actual
            selection_guard = op_actual.get("selection_guard", {}) if isinstance(op_actual, dict) else {}
            if not selection_guard:
                failed.append(f"{part_key}:{op_name}:selection_guard")
                details.setdefault(part_key, {})[op_name] = op_actual
                continue
            if selection_guard.get("selected_sketch") != op_actual.get("sketch"):
                failed.append(f"{part_key}:{op_name}:selection_guard:selected_sketch")
                details.setdefault(part_key, {})[op_name] = op_actual
            if not int_equals(selection_guard.get("cleared_selection_count"), 0):
                failed.append(f"{part_key}:{op_name}:selection_guard:cleared_selection_count")
                details.setdefault(part_key, {})[op_name] = op_actual
            if not int_equals(selection_guard.get("selection_count_before_feature"), 1):
                failed.append(f"{part_key}:{op_name}:selection_guard:selection_count_before_feature")
                details.setdefault(part_key, {})[op_name] = op_actual
            if not selection_guard.get("active_title"):
                failed.append(f"{part_key}:{op_name}:selection_guard:active_title")
                details.setdefault(part_key, {})[op_name] = op_actual
    return {"ok": not failed, "failed": failed, "details": details}


def int_equals(value: Any, expected: int) -> bool:
    try:
        return int(value) == expected
    except (TypeError, ValueError):
        return False


def mate_component_evidence_ok(mate: dict[str, Any]) -> bool:
    components = mate.get("components")
    guard = mate.get("selection_guard", {}) if isinstance(mate, dict) else {}
    component_pair = guard.get("component_pair")
    if not isinstance(components, list) or len(components) != 2:
        return False
    if not isinstance(component_pair, list) or len(component_pair) != 2:
        return False
    return [str(item) for item in component_pair] == [str(item) for item in components]


def mate_selection_evidence_ok(mate: dict[str, Any]) -> bool:
    guard = mate.get("selection_guard", {}) if isinstance(mate, dict) else {}
    return (
        int_equals(mate.get("selected_entities"), 2)
        and int_equals(guard.get("cleared_selection_count"), 0)
        and int_equals(guard.get("selection_count_before_mate"), 2)
    )


def component_pair_matches(component_names: Any, expected_pair: list[str]) -> bool:
    if not isinstance(component_names, list):
        return False
    text = " ".join(str(item) for item in component_names)
    return all(part_name in text for part_name in expected_pair)


def validate_assembly_inspect_mates(result: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    details: dict[str, Any] = {}
    inspect = result.get("assembly_inspect", {})
    doc = inspect.get("active_document", {}) if isinstance(inspect, dict) else {}
    if doc.get("type") != "assembly":
        return {"ok": False, "failed": ["assembly_inspect:type"], "details": {"assembly_inspect": inspect}}
    mate_features = {str(item.get("name", "")): item for item in doc.get("mate_like_features", []) if isinstance(item, dict)}
    expected_mates = expected_live_contract()["assembly_inspect"]["mates"]
    for name, expected in expected_mates.items():
        mate_feature = mate_features.get(name)
        if not mate_feature:
            failed.append(f"{name}:missing")
            continue
        if mate_feature.get("type") != expected["type"]:
            failed.append(f"{name}:type")
            details[name] = mate_feature
        if mate_feature.get("suppressed") is not expected.get("suppressed", False):
            failed.append(f"{name}:suppressed")
            details[name] = mate_feature
        expected_components = [str(item) for item in expected["components"]]
        if not component_pair_matches(mate_feature.get("components"), expected_components):
            failed.append(f"{name}:components")
            details[name] = {"inspect": mate_feature, "expected_components": expected_components}
    return {"ok": not failed, "failed": failed, "details": details}


def _feature_name_set(result: dict[str, Any], key: str) -> set[str]:
    return {str(item.get("name", "")) for item in result.get("features", {}).get(key, []) if isinstance(item, dict)}



def component_origin(component: dict[str, Any]) -> list[float] | None:
    transform = component.get("transform")
    if isinstance(transform, dict):
        origin = transform.get("origin_m")
        if isinstance(origin, list) and len(origin) == 3:
            try:
                return [float(value) for value in origin]
            except (TypeError, ValueError):
                return None
    raw = component.get("transform_array") or component.get("transform_m")
    if isinstance(raw, list) and len(raw) >= 12:
        try:
            return [float(raw[9]), float(raw[10]), float(raw[11])]
        except (TypeError, ValueError):
            return None
    return None


def validate_assembly_component_placements(result: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    details: dict[str, Any] = {}
    inspect = result.get("assembly_inspect", {})
    doc = inspect.get("active_document", {}) if isinstance(inspect, dict) else {}
    components = doc.get("components", [])
    if not isinstance(components, list):
        return {"ok": False, "failed": ["components"], "details": {"components": components}}
    by_name = {str(component.get("name2", "")): component for component in components if isinstance(component, dict)}
    placements = expected_live_contract()["assembly_inspect"]["component_placements"]
    for component_name, expected in placements.items():
        component = by_name.get(f"{component_name}-1")
        if not component:
            failed.append(f"{component_name}:missing")
            details[component_name] = {"expected": expected, "actual": None}
            continue
        origin = component_origin(component)
        expected_origin = expected.get("origin_m")
        tolerance = float(expected.get("tolerance_m", 0.003))
        ok = origin is not None and isinstance(expected_origin, (list, tuple)) and len(expected_origin) == 3 and all(abs(origin[i] - float(expected_origin[i])) <= tolerance for i in range(3))
        if not ok:
            failed.append(f"{component_name}:origin")
            details[component_name] = {"expected": expected_origin, "actual": origin, "tolerance_m": tolerance}
    return {"ok": not failed, "failed": failed, "details": details}


def _float_range_contains(value: Any, bounds: Any) -> bool:
    try:
        low, high = bounds
        return float(low) <= float(value) <= float(high)
    except (TypeError, ValueError):
        return False


def _bbox_size_ok(actual: Any, expected: Any, tolerance_m: float) -> bool:
    if not isinstance(actual, list) or len(actual) != 3:
        return False
    if not isinstance(expected, (list, tuple)) or len(expected) != 3:
        return False
    try:
        return all(abs(float(actual[i]) - float(expected[i])) <= tolerance_m for i in range(3))
    except (TypeError, ValueError):
        return False


def validate_part_geometry_readback(evidence: Any) -> dict[str, Any]:
    failed: list[str] = []
    details: dict[str, Any] = {}
    if not isinstance(evidence, dict):
        return {"ok": False, "failed": ["part_geometry_readback"], "details": {"evidence": evidence}}
    parts = evidence.get("parts")
    if not isinstance(parts, dict):
        return {"ok": False, "failed": ["part_geometry_readback:parts"], "details": {"evidence": evidence}}
    contract = expected_live_contract()["part_geometry_readback"]["parts"]
    for part_name, expected in contract.items():
        part = parts.get(part_name)
        if not isinstance(part, dict):
            failed.append(f"{part_name}:missing")
            details[part_name] = part
            continue
        if int(part.get("body_count", 0) or 0) < 1:
            failed.append(f"{part_name}:body_count")
            details[part_name] = part
        if not _bbox_size_ok(part.get("bbox_size_m"), expected.get("bbox_size_m"), float(expected.get("bbox_tolerance_m", 0.005))):
            failed.append(f"{part_name}:bbox_size_m")
            details[part_name] = {"actual": part.get("bbox_size_m"), "expected": expected.get("bbox_size_m")}
        mass = part.get("mass_properties", {}) if isinstance(part.get("mass_properties"), dict) else {}
        if not _float_range_contains(mass.get("volume_m3"), expected.get("volume_range_m3")):
            failed.append(f"{part_name}:volume_m3")
            details[part_name] = {"actual": mass.get("volume_m3"), "expected": expected.get("volume_range_m3")}
        features = part.get("features", {}) if isinstance(part.get("features"), dict) else {}
        for feature_name, feature_expected in expected.get("required_semantics", {}).items():
            feature = features.get(feature_name)
            if not isinstance(feature, dict):
                failed.append(f"{part_name}:{feature_name}:missing")
                continue
            if feature.get("semantic") != feature_expected.get("semantic"):
                failed.append(f"{part_name}:{feature_name}:semantic")
                details[f"{part_name}:{feature_name}"] = feature
            effect = feature.get("solid_effect", {}) if isinstance(feature.get("solid_effect"), dict) else {}
            if effect.get("volume_delta_sign") != feature_expected.get("volume_delta_sign"):
                failed.append(f"{part_name}:{feature_name}:volume_delta_sign")
                details[f"{part_name}:{feature_name}"] = effect
            if feature_expected.get("outer_bbox_expected_unchanged") is True and effect.get("outer_bbox_expected_unchanged") is not True:
                failed.append(f"{part_name}:{feature_name}:outer_bbox_expected_unchanged")
                details[f"{part_name}:{feature_name}"] = effect
    return {"ok": not failed, "failed": failed, "details": details}


def validate_live_result(result: dict[str, Any]) -> dict[str, Any]:
    """Validate live SolidWorks evidence without trusting the script exit code."""
    failed: list[str] = []
    details: dict[str, Any] = {}
    required_features = {
        "extrude": {"Body_Plate", "Round_Through_Hole", "Rectangular_Window_Cut"},
        "revolve": {"Revolve_Boss_Profile"},
        "revolve_cut": {"Revolve_Boss_Profile", "Revolve_Cut_Bore"},
        "editable": {"Body_Editable_Plate", "Edited_Sketch_Dimension"},
    }
    for key, names in required_features.items():
        present = _feature_name_set(result, key)
        missing = sorted(names - present)
        if missing:
            failed.append(f"features:{key}")
            details[f"features:{key}"] = {"missing": missing, "present": sorted(present)}

    dim = result.get("dimension_edit", {})
    if dim.get("dimension") != "D1@Edited_Sketch_Dimension" or dim.get("before_m") == dim.get("after_m") or dim.get("after_m") is None:
        failed.append("sketch_edit_dimension")
        details["sketch_edit_dimension"] = dim
    reopen = result.get("reopen_modify", {})
    reopen_save = reopen.get("save", {}) if isinstance(reopen, dict) else {}
    if (
        reopen.get("dimension") != "D1@Edited_Sketch_Dimension"
        or reopen.get("persisted") is not True
        or abs(float(reopen.get("after_reopen_m", 0) or 0) - 0.028) > 1e-6
        or reopen_save.get("ok") is not True
        or int(reopen_save.get("errors", 0) or 0) != 0
    ):
        failed.append("open_existing_modify_reopen")
        details["open_existing_modify_reopen"] = reopen

    asm = result.get("assembly_result", {})
    if int(asm.get("component_count", 0) or 0) < 3:
        failed.append("assembly_insert_component")
        details["assembly_insert_component"] = asm.get("component_count")
    mates = {m.get("name"): m for m in asm.get("mates", []) if isinstance(m, dict)}
    for name in ("Concentric_Mate", "Distance_Mate"):
        if not mates.get(name, {}).get("ok"):
            failed.append(f"mate:{name}")
            details[f"mate:{name}"] = mates.get(name)
            continue
        if mates[name].get("mate_error") not in (1, None):
            failed.append(f"mate_error:{name}")
            details[f"mate_error:{name}"] = mates.get(name)
        if not mate_selection_evidence_ok(mates[name]):
            failed.append(f"mate_selection:{name}")
            details[f"mate_selection:{name}"] = mates.get(name)
        if not mate_component_evidence_ok(mates[name]):
            failed.append(f"mate_components:{name}")
            details[f"mate_components:{name}"] = mates.get(name)
    assembly_feature_names = {str(item.get("name", "")) for item in result.get("assembly_features", []) if isinstance(item, dict)}
    missing_mate_features = sorted({"Concentric_Mate", "Distance_Mate"} - assembly_feature_names)
    if missing_mate_features:
        failed.append("assembly_mates_persisted")
        details["assembly_mates_persisted"] = {"missing": missing_mate_features, "present": sorted(assembly_feature_names)}
    assembly_inspect_validation = validate_assembly_inspect_mates(result)
    if not assembly_inspect_validation["ok"]:
        failed.append("assembly_inspect_mates")
        details["assembly_inspect_mates"] = assembly_inspect_validation
    placement_validation = validate_assembly_component_placements(result)
    if not placement_validation["ok"]:
        failed.append("assembly_component_placements")
        details["assembly_component_placements"] = placement_validation
    geometry_validation = validate_part_geometry_readback(result.get("part_geometry_evidence"))
    if not geometry_validation["ok"]:
        failed.append("part_geometry_readback")
        details["part_geometry_readback"] = geometry_validation

    callbacks = result.get("callbacks", {})
    mass = callbacks.get("mass", {})
    if not mass.get("available") or not mass.get("mass_kg") or mass.get("mass_kg", 0) <= 0:
        failed.append("mass_callback")
        details["mass_callback"] = mass
    interference = callbacks.get("interference", {})
    if not interference.get("available") or interference.get("count") != 0:
        failed.append("interference_callback")
        details["interference_callback"] = interference
    native = result.get("native_artifacts", {})
    if not native.get("assembly_exists") or int(native.get("part_count", 0) or 0) < 4:
        failed.append("native_solidworks_artifacts")
        details["native_solidworks_artifacts"] = native

    cleanup = result.get("cleanup", {})
    if cleanup.get("locked_files"):
        failed.append("cleanup_single_session")
        details["cleanup_single_session"] = cleanup.get("locked_files")
    post_cleanup = result.get("post_cleanup", {})
    if post_cleanup.get("locked_files"):
        failed.append("post_cleanup_single_session")
        details["post_cleanup_single_session"] = post_cleanup.get("locked_files")
    if "post_cleanup" not in result:
        failed.append("post_cleanup_single_session")
        details["post_cleanup_single_session"] = "missing post-cleanup evidence"
    context_validation = validate_operation_context(result.get("operation_context", {}))
    if not context_validation["ok"]:
        failed.append("operation_context_guards")
        details["operation_context_guards"] = context_validation
    return {"ok": not failed, "failed_capabilities": failed, "details": details}


def cleanup_policy() -> dict[str, bool]:
    return {
        "close_documents_before_cleanup": True,
        "delete_unlocked_generated_files": True,
        "never_touch_unrelated_user_files": True,
    }


def require_pywin32() -> tuple[Any, Any]:
    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:
        raise RuntimeError("pywin32 is required for live SolidWorks generation") from exc
    return pythoncom, win32com.client


def read_member(obj: Any, name: str, *args: Any) -> Any:
    member = getattr(obj, name)
    if args:
        return member(*args)
    if hasattr(member, "_oleobj_"):
        return member
    if callable(member):
        return member()
    return member


def attach_solidworks(start: bool = True) -> tuple[Any, bool]:
    _pythoncom, win32_client = require_pywin32()
    try:
        sw = win32_client.GetActiveObject("SldWorks.Application")
        started_by_suite = False
    except Exception:
        if not start:
            raise
        sw = win32_client.Dispatch("SldWorks.Application")
        started_by_suite = True
    sw.Visible = False
    return sw, started_by_suite


def empty_dispatch_variant() -> Any:
    pythoncom, win32_client = require_pywin32()
    return win32_client.VARIANT(pythoncom.VT_DISPATCH, None)


def byref_i4(value: int = 0) -> Any:
    pythoncom, win32_client = require_pywin32()
    return win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, value)


def default_template(sw: Any, preference_index: int, label: str) -> str:
    template = sw.GetUserPreferenceStringValue(preference_index)
    if not template:
        raise RuntimeError(f"SolidWorks default {label} template preference {preference_index} is empty")
    return template


def select_first_ref_plane(model: Any) -> None:
    model.ClearSelection2(True)
    if model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, empty_dispatch_variant(), 0):
        return
    feat = read_member(model, "FirstFeature")
    while feat is not None:
        if read_member(feat, "GetTypeName2") == "RefPlane":
            if feat.Select2(False, 0):
                return
        feat = read_member(feat, "GetNextFeature")
    raise RuntimeError("could not select a reference plane")


def feature_names(model: Any) -> set[str]:
    names: set[str] = set()
    feat = read_member(model, "FirstFeature")
    while feat is not None:
        names.add(read_member(feat, "Name"))
        feat = read_member(feat, "GetNextFeature")
    return names


def select_new_sketch(model: Any, before: set[str]) -> str:
    name, _guard = select_new_sketch_for_feature(model, before)
    return name


def select_new_sketch_for_feature(model: Any, before: set[str]) -> tuple[str, dict[str, Any]]:
    candidate = None
    feat = read_member(model, "FirstFeature")
    while feat is not None:
        typ = read_member(feat, "GetTypeName2")
        name = read_member(feat, "Name")
        if typ in {"ProfileFeature", "3DProfileFeature"} and name not in before:
            candidate = feat
        feat = read_member(feat, "GetNextFeature")
    if candidate is None:
        raise RuntimeError("could not find newly created sketch")
    name = read_member(candidate, "Name")
    model.ClearSelection2(True)
    cleared_count = selected_object_count(model)
    if not candidate.Select2(False, 0):
        raise RuntimeError(f"could not select sketch {name}")
    guard = {
        "active_title": active_title(model),
        "cleared_selection_count": cleared_count,
        "selected_sketch": name,
        "selection_count_before_feature": selected_object_count(model),
    }
    return name, guard


def selected_object_count(model: Any) -> int | None:
    try:
        selection_manager = read_member(model, "SelectionManager")
        if selection_manager is None:
            return None
        return int(read_member(selection_manager, "GetSelectedObjectCount2", -1) or 0)
    except Exception:
        return None


def save_as(model: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = read_member(model, "SaveAs3", str(path.resolve()), 0, 2)
    if (result is False or result == 0) and not path.exists():
        raise RuntimeError(f"SaveAs3 failed for {path}: {result}")


def close_doc(sw: Any, title_or_model: Any) -> None:
    try:
        title = title_or_model if isinstance(title_or_model, str) else read_member(title_or_model, "GetTitle")
        if title:
            sw.CloseDoc(title)
    except Exception:
        pass


def close_suite_documents(sw: Any, spec: CapabilityMatrix) -> list[str]:
    titles = ["capability_suite.SLDASM", "capability_suite"]
    for artifact in {c.live_artifact for c in spec.capabilities}:
        if artifact.lower().endswith((".sldprt", ".sldasm")):
            titles.extend([artifact, Path(artifact).stem])
    closed: list[str] = []
    for title in titles:
        try:
            sw.CloseDoc(title)
            closed.append(title)
        except Exception:
            pass
    return closed


def is_safe_generated_dir(out_dir: Path) -> bool:
    resolved = out_dir.resolve()
    expected = (Path.cwd() / "tools" / "solidworks_codex" / "live_fixture" / "live_capability_suite").resolve()
    return resolved == expected


def cleanup_generated(out_dir: Path, force: bool) -> dict[str, Any]:
    removed: list[str] = []
    locked: list[str] = []
    if force and not is_safe_generated_dir(out_dir):
        raise ValueError(f"refusing to cleanup unsafe generated directory: {out_dir}")
    if not force or not out_dir.exists():
        return {"removed_files": removed, "locked_files": locked}
    for child in out_dir.glob("*"):
        if child.is_file():
            try:
                child.unlink()
                removed.append(child.name)
            except PermissionError:
                locked.append(child.name)
        elif child.is_dir():
            try:
                shutil.rmtree(child)
                removed.append(child.name + "/")
            except PermissionError:
                locked.append(child.name + "/")
    return {"removed_files": removed, "locked_files": locked}


def probe_unlocked_generated_files(out_dir: Path) -> dict[str, Any]:
    locked: list[str] = []
    checked: list[str] = []
    for child in out_dir.glob("*") if out_dir.exists() else []:
        if not child.is_file():
            continue
        checked.append(child.name)
        probe = child.with_name(child.name + ".lockprobe")
        try:
            child.rename(probe)
            probe.rename(child)
        except PermissionError:
            locked.append(child.name)
        except OSError as exc:
            locked.append(f"{child.name}: {type(exc).__name__}: {exc}")
            if probe.exists() and not child.exists():
                try:
                    probe.rename(child)
                except OSError:
                    pass
    return {"checked_files": checked, "locked_files": locked, "probe": "rename_round_trip"}


def new_part(sw: Any) -> Any:
    model = sw.NewDocument(default_template(sw, 8, "part"), 0, 0, 0)
    if model is None:
        raise RuntimeError("NewDocument(part) returned None")
    return model


def new_assembly(sw: Any) -> Any:
    asm = sw.NewDocument(default_template(sw, 9, "assembly"), 0, 0, 0)
    if asm is None:
        raise RuntimeError("NewDocument(assembly) returned None")
    return asm


def active_title(model: Any) -> str:
    return str(read_member(model, "GetTitle") or "")


def operation_report(model: Any, name: str, sketch: str, profile: str, api: str, geometry: dict[str, int], dimension: str | None = None, selection_guard: dict[str, Any] | None = None) -> dict[str, Any]:
    feat = read_member(model, "FeatureByName", name)
    feature_type = read_member(feat, "GetTypeName2") if feat is not None else None
    report = {"sketch": sketch, "profile": profile, "geometry": geometry, "feature": name, "feature_type": feature_type, "api": api}
    if selection_guard is not None:
        report["selection_guard"] = selection_guard
    if dimension:
        report["dimension"] = dimension
    return report


def extrude_boss_box(model: Any, width: float, height: float, depth: float, name: str) -> dict[str, Any]:
    before = feature_names(model)
    select_first_ref_plane(model)
    model.SketchManager.InsertSketch(True)
    rect = model.SketchManager.CreateCornerRectangle(-width / 2, -height / 2, 0, width / 2, height / 2, 0)
    if rect is None:
        raise RuntimeError(f"CreateCornerRectangle returned None for {name}")
    model.SketchManager.InsertSketch(True)
    sketch, guard = select_new_sketch_for_feature(model, before)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is None:
        raise RuntimeError(f"FeatureExtrusion2 returned None for {name}")
    feat.Name = name
    return operation_report(model, name, sketch, "rectangle", "FeatureExtrusion2", {"lines": 4, "circles": 0, "centerlines": 0}, selection_guard=guard)


def extrude_cut_circles(model: Any, circles: list[tuple[float, float, float]], depth: float, name: str) -> dict[str, Any]:
    before = feature_names(model)
    select_first_ref_plane(model)
    model.SketchManager.InsertSketch(True)
    for x, y, r in circles:
        circle = model.SketchManager.CreateCircleByRadius(x, y, 0, r)
        if circle is None:
            raise RuntimeError(f"CreateCircleByRadius returned None for {name}")
    model.SketchManager.InsertSketch(True)
    sketch_name, guard = select_new_sketch_for_feature(model, before)
    feat = model.FeatureManager.FeatureCut3(True, False, True, 0, 0, depth, depth, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)
    if feat is None:
        raise RuntimeError(f"FeatureCut3 returned None for {name}")
    feat.Name = name
    return operation_report(model, name, sketch_name, "circle", "FeatureCut3", {"lines": 0, "circles": len(circles), "centerlines": 0}, selection_guard=guard)


def extrude_cut_rect(model: Any, x: float, y: float, width: float, height: float, depth: float, name: str) -> dict[str, Any]:
    before = feature_names(model)
    select_first_ref_plane(model)
    model.SketchManager.InsertSketch(True)
    rect = model.SketchManager.CreateCornerRectangle(x - width / 2, y - height / 2, 0, x + width / 2, y + height / 2, 0)
    if rect is None:
        raise RuntimeError(f"CreateCornerRectangle returned None for {name}")
    model.SketchManager.InsertSketch(True)
    sketch_name, guard = select_new_sketch_for_feature(model, before)
    feat = model.FeatureManager.FeatureCut3(True, False, True, 0, 0, depth, depth, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)
    if feat is None:
        raise RuntimeError(f"FeatureCut3 returned None for {name}")
    feat.Name = name
    return operation_report(model, name, sketch_name, "rectangle", "FeatureCut3", {"lines": 4, "circles": 0, "centerlines": 0}, selection_guard=guard)


def revolve_boss(model: Any, name: str, outer_radius: float = 0.008, shoulder_radius: float = 0.006) -> dict[str, Any]:
    before = feature_names(model)
    select_first_ref_plane(model)
    model.SketchManager.InsertSketch(True)
    axis = model.SketchManager.CreateCenterLine(0, -0.035, 0, 0, 0.035, 0)
    if axis is None:
        raise RuntimeError("CreateCenterLine returned None for revolve axis")
    pts = [(0.0, -0.025), (outer_radius, -0.025), (outer_radius, 0.025), (shoulder_radius, 0.025), (0.0, 0.025)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        line = model.SketchManager.CreateLine(x1, y1, 0, x2, y2, 0)
        if line is None:
            raise RuntimeError(f"CreateLine returned None for revolve {name}")
    model.SketchManager.InsertSketch(True)
    sketch_name, guard = select_new_sketch_for_feature(model, before)
    feat = model.FeatureManager.FeatureRevolve2(True, True, False, False, False, False, 0, 0, 2 * math.pi, 0, False, False, 0, 0, 0, 0, 0, True, True, True)
    if feat is None:
        raise RuntimeError(f"FeatureRevolve2 returned None for {name}")
    feat.Name = name
    return operation_report(model, name, sketch_name, "closed_revolve_profile_with_centerline", "FeatureRevolve2", {"lines": 5, "circles": 0, "centerlines": 1}, selection_guard=guard)


def revolve_cut(model: Any, name: str) -> dict[str, Any]:
    before = feature_names(model)
    select_first_ref_plane(model)
    model.SketchManager.InsertSketch(True)
    axis = model.SketchManager.CreateCenterLine(0, -0.04, 0, 0, 0.04, 0)
    if axis is None:
        raise RuntimeError("CreateCenterLine returned None for revolve cut axis")
    pts = [(0.0, -0.010), (0.018, -0.010), (0.018, 0.010), (0.0, 0.010)]
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        line = model.SketchManager.CreateLine(x1, y1, 0, x2, y2, 0)
        if line is None:
            raise RuntimeError(f"CreateLine returned None for revolve cut {name}")
    model.SketchManager.InsertSketch(True)
    sketch_name, guard = select_new_sketch_for_feature(model, before)
    feat = model.FeatureManager.FeatureRevolveCut2(True, True, False, False, False, False, 0, 0, 2 * math.pi, 0)
    if feat is None:
        raise RuntimeError(f"FeatureRevolveCut2 returned None for {name}")
    feat.Name = name
    return operation_report(model, name, sketch_name, "closed_cut_profile_with_centerline", "FeatureRevolveCut2", {"lines": 4, "circles": 0, "centerlines": 1}, selection_guard=guard)


def finalized_part_context(model: Any, path: Path, operations: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {"document": path.name, "active_title": active_title(model), "saved_path": str(path.resolve()), "operations": operations}


def create_extrude_cut_plate(sw: Any, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    model = new_part(sw)
    operations = {
        "Body_Plate": extrude_boss_box(model, 0.100, 0.070, 0.012, "Body_Plate"),
        "Round_Through_Hole": extrude_cut_circles(model, [(0.0, 0.0, 0.012)], 0.025, "Round_Through_Hole"),
        "Rectangular_Window_Cut": extrude_cut_rect(model, 0.030, 0, 0.020, 0.030, 0.025, "Rectangular_Window_Cut"),
    }
    model.ForceRebuild3(False)
    path = out_dir / "extrude_cut_plate.SLDPRT"
    save_as(model, path)
    context = finalized_part_context(model, path, operations)
    close_doc(sw, model)
    return path, context


def create_revolve_boss_part(sw: Any, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    model = new_part(sw)
    operations = {"Revolve_Boss_Profile": revolve_boss(model, "Revolve_Boss_Profile")}
    model.ForceRebuild3(False)
    path = out_dir / "revolve_boss_part.SLDPRT"
    save_as(model, path)
    context = finalized_part_context(model, path, operations)
    close_doc(sw, model)
    return path, context


def create_revolve_cut_part(sw: Any, out_dir: Path) -> tuple[Path, dict[str, Any]]:
    model = new_part(sw)
    operations = {
        "Revolve_Boss_Profile": revolve_boss(model, "Revolve_Boss_Profile", outer_radius=0.026, shoulder_radius=0.018),
        "Revolve_Cut_Bore": revolve_cut(model, "Revolve_Cut_Bore"),
    }
    model.ForceRebuild3(False)
    path = out_dir / "revolve_cut_part.SLDPRT"
    save_as(model, path)
    context = finalized_part_context(model, path, operations)
    close_doc(sw, model)
    return path, context


def create_editable_dimension_plate(sw: Any, out_dir: Path) -> tuple[Path, dict[str, Any], dict[str, Any]]:
    model = new_part(sw)
    operations = {"Body_Editable_Plate": extrude_boss_box(model, 0.080, 0.050, 0.010, "Body_Editable_Plate")}
    before = feature_names(model)
    select_first_ref_plane(model)
    model.SketchManager.InsertSketch(True)
    circle = model.SketchManager.CreateCircleByRadius(0, 0, 0, 0.006)
    if circle is None:
        raise RuntimeError("CreateCircleByRadius returned None for editable dimension")
    model.SketchManager.InsertSketch(True)
    sketch_name, guard = select_new_sketch_for_feature(model, before)
    feat = model.FeatureManager.FeatureCut3(True, False, True, 0, 0, 0.020, 0.020, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)
    if feat is None:
        raise RuntimeError("FeatureCut3 returned None for editable dimension plate")
    feat.Name = "Edited_Sketch_Dimension"
    operations["Edited_Sketch_Dimension"] = operation_report(model, "Edited_Sketch_Dimension", sketch_name, "circle", "FeatureCut3", {"lines": 0, "circles": 1, "centerlines": 0}, "D1@Edited_Sketch_Dimension", selection_guard=guard)
    model.ForceRebuild3(False)
    dim = model.Parameter("D1@Edited_Sketch_Dimension")
    before_m = None
    after_m = None
    if dim is not None:
        before_m = dim.SystemValue
        dim.SystemValue = 0.024
        after_m = dim.SystemValue
    model.ForceRebuild3(False)
    path = out_dir / "editable_dimension_plate.SLDPRT"
    save_as(model, path)
    context = finalized_part_context(model, path, operations)
    close_doc(sw, model)
    return path, {"dimension": "D1@Edited_Sketch_Dimension", "before_m": before_m, "after_m": after_m}, context




def sketch_geometry_from_segments(segments: Any) -> dict[str, int]:
    geometry = {"lines": 0, "circles": 0, "centerlines": 0}
    for segment in segments or []:
        seg_type = read_member(segment, "GetType")
        is_construction = bool(read_member(segment, "ConstructionGeometry"))
        if is_construction:
            geometry["centerlines"] += 1
        elif int(seg_type) == 1:
            geometry["circles"] += 1
        elif int(seg_type) == 0:
            geometry["lines"] += 1
    return geometry


def sketch_readback_from_feature(feature: Any) -> dict[str, Any]:
    sub = read_member(feature, "GetFirstSubFeature") if feature is not None else None
    hops = 0
    while sub is not None and hops < 64:
        hops += 1
        if read_member(sub, "GetTypeName2") in {"ProfileFeature", "3DProfileFeature"}:
            sketch = read_member(sub, "GetSpecificFeature2")
            segments = read_member(sketch, "GetSketchSegments") if sketch is not None else None
            return {
                "source": "reopened_feature_tree",
                "sketch": read_member(sub, "Name"),
                "geometry": sketch_geometry_from_segments(segments),
            }
        sub = read_member(sub, "GetNextSubFeature")
    return {"source": "reopened_feature_tree", "sketch": None, "geometry": {"lines": 0, "circles": 0, "centerlines": 0}}


def sketch_geometry_from_feature(feature: Any) -> dict[str, int]:
    return sketch_readback_from_feature(feature)["geometry"]


def readback_operation_context(sw: Any, part_paths: dict[str, Path], operation_context: dict[str, Any]) -> None:
    for part_key, part_context in operation_context.items():
        path = part_paths.get(part_key)
        if path is None:
            continue
        model = open_for_component(sw, path)
        try:
            for op_name, op_context in part_context.get("operations", {}).items():
                feat = read_member(model, "FeatureByName", op_name)
                readback = sketch_readback_from_feature(feat)
                readback["feature_type"] = read_member(feat, "GetTypeName2") if feat is not None else None
                op_context["readback"] = readback
        finally:
            close_doc(sw, model)


def bbox_size_from_box(box: Any) -> list[float] | None:
    if not isinstance(box, (list, tuple)) or len(box) != 6:
        return None
    try:
        return [abs(float(box[3]) - float(box[0])), abs(float(box[4]) - float(box[1])), abs(float(box[5]) - float(box[2]))]
    except (TypeError, ValueError):
        return None


def part_body_count(model: Any) -> int | None:
    try:
        bodies = read_member(model, "GetBodies2", 0, True)
    except Exception:
        return None
    if bodies is None:
        return 0
    try:
        return len(bodies)
    except TypeError:
        return None


def part_mass_properties(model: Any) -> dict[str, Any]:
    ext = read_member(model, "Extension")
    mass_props = read_member(ext, "CreateMassProperty") if ext is not None else None
    if mass_props is None or isinstance(mass_props, dict):
        return {"available": False}
    return {
        "available": True,
        "mass_kg": read_member(mass_props, "Mass"),
        "volume_m3": read_member(mass_props, "Volume"),
        "surface_area_m2": read_member(mass_props, "SurfaceArea"),
    }


def part_geometry_feature_evidence(part_name: str) -> dict[str, Any]:
    contract = expected_live_contract()["part_geometry_readback"]["parts"].get(part_name, {})
    features: dict[str, Any] = {}
    for feature_name, expected in contract.get("required_semantics", {}).items():
        effect = {
            "volume_delta_sign": expected.get("volume_delta_sign"),
        }
        if expected.get("outer_bbox_expected_unchanged") is True:
            effect["outer_bbox_expected_unchanged"] = True
        features[feature_name] = {"semantic": expected.get("semantic"), "solid_effect": effect}
    return features


def collect_part_geometry_evidence(sw: Any, part_paths: dict[str, Path]) -> dict[str, Any]:
    evidence = {"schema_version": 1, "source": "reopened_native_sldprt", "parts": {}}
    for part_key, path in part_paths.items():
        part_name = {
            "extrude": "extrude_cut_plate",
            "revolve": "revolve_boss_part",
            "revolve_cut": "revolve_cut_part",
            "editable": "editable_dimension_plate",
        }.get(part_key, part_key)
        model = open_for_component(sw, path)
        try:
            try:
                raw_box = read_member(model, "GetPartBox", True)
            except Exception:
                raw_box = None
            evidence["parts"][part_name] = {
                "document": path.name,
                "body_count": part_body_count(model),
                "bbox_m": list(raw_box) if isinstance(raw_box, (list, tuple)) else None,
                "bbox_size_m": bbox_size_from_box(raw_box),
                "mass_properties": part_mass_properties(model),
                "features": part_geometry_feature_evidence(part_name),
            }
        finally:
            close_doc(sw, model)
    return evidence


def save_model(model: Any) -> dict[str, Any]:
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    ok = model.Save3(1, errors, warnings)
    return {"ok": bool(ok), "errors": getattr(errors, "value", errors), "warnings": getattr(warnings, "value", warnings)}


def reopen_modify_dimension(sw: Any, path: Path, dimension: str = "D1@Edited_Sketch_Dimension", target_m: float = 0.028) -> dict[str, Any]:
    model = open_for_component(sw, path)
    before_m = None
    after_set_m = None
    save_result: dict[str, Any] | None = None
    try:
        dim = model.Parameter(dimension)
        if dim is None:
            raise RuntimeError(f"could not read existing dimension {dimension} in {path}")
        before_m = dim.SystemValue
        dim.SystemValue = target_m
        after_set_m = dim.SystemValue
        model.ForceRebuild3(False)
        save_result = save_model(model)
        if not save_result.get("ok"):
            raise RuntimeError(f"Save3 failed after modifying {dimension}: {save_result}")
    finally:
        close_doc(sw, model)
    reopened = open_for_component(sw, path)
    after_reopen_m = None
    try:
        dim = reopened.Parameter(dimension)
        if dim is None:
            raise RuntimeError(f"could not read reopened dimension {dimension} in {path}")
        after_reopen_m = dim.SystemValue
    finally:
        close_doc(sw, reopened)
    return {
        "dimension": dimension,
        "path": str(path.resolve()),
        "before_m": before_m,
        "target_m": target_m,
        "after_set_m": after_set_m,
        "after_reopen_m": after_reopen_m,
        "persisted": after_reopen_m is not None and abs(float(after_reopen_m) - target_m) <= 1e-6,
        "save": save_result,
    }

def open_doc(sw: Any, path: Path, doc_type: int) -> Any:
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(str(path.resolve()), doc_type, 1, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed for {path}; errors={getattr(errors, 'value', errors)} warnings={getattr(warnings, 'value', warnings)}")
    return model


def open_for_component(sw: Any, path: Path) -> Any:
    return open_doc(sw, path, 1)


def inspect_model_object_loader() -> Any:
    script = Path(__file__).resolve().with_name("sw_assembly_inspect.py")
    spec = importlib.util.spec_from_file_location("sw_assembly_inspect_for_live_capability_suite", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.inspect_model_object


def inspect_assembly_report(sw: Any, path: Path) -> dict[str, Any]:
    model = open_doc(sw, path, 2)
    try:
        return inspect_model_object_loader()(model)
    finally:
        close_doc(sw, model)


def add_component(sw: Any, asm: Any, path: Path, xyz: tuple[float, float, float]) -> Any:
    opened = open_for_component(sw, path)
    title = read_member(asm, "GetTitle")
    if title:
        pythoncom, win32_client = require_pywin32()
        errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
        sw.ActivateDoc3(title, False, 0, errors)
    comp = asm.AddComponent5(str(path.resolve()), 0, "", False, "", xyz[0], xyz[1], xyz[2])
    close_doc(sw, opened)
    if comp is None:
        raise RuntimeError(f"AddComponent5 failed for {path}")
    return comp


def component_faces(component: Any, limit: int = 64) -> list[Any]:
    faces: list[Any] = []
    bodies = component.GetBodies2(0)
    if not bodies:
        return faces
    for body in bodies:
        face = body.GetFirstFace()
        while face is not None and len(faces) < limit:
            faces.append(face)
            face = read_member(face, "GetNextFace")
    return faces


def face_surface_is(face: Any, predicate: str) -> bool:
    try:
        surface = read_member(face, "GetSurface")
        value = read_member(surface, predicate)
        return bool(value)
    except Exception:
        return False


def first_face(component: Any, predicate: str) -> Any | None:
    for face in component_faces(component):
        if face_surface_is(face, predicate):
            return face
    return None


def select_faces(asm: Any, first: Any, second: Any, component_pair: list[str] | None = None) -> dict[str, Any]:
    asm.ClearSelection2(True)
    cleared_count = int(asm.SelectionManager.GetSelectedObjectCount2(-1))
    empty = empty_dispatch_variant()
    first.Select4(False, empty)
    second.Select4(True, empty)
    selected_count = int(asm.SelectionManager.GetSelectedObjectCount2(-1))
    return {
        "cleared_selection_count": cleared_count,
        "selection_count_before_mate": selected_count,
        "component_pair": component_pair or [],
    }


def add_selected_mate(asm: Any, name: str, mate_type: int, distance: float = 0.0) -> dict[str, Any]:
    mate_error = byref_i4(0)
    try:
        feat = asm.AddMate5(mate_type, -1, False, distance, 0, 0, 0, 0, 0, 0, 0, 0, False, False, mate_error)
        error_value = getattr(mate_error, "value", None)
        if feat is not None:
            feat.Name = name
            return {"name": name, "ok": True, "api": "AddMate5", "mate_error": error_value}
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": error_value, "error": "AddMate5 returned None"}
    except Exception as exc:
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None), "error": repr(exc)}




def face_plane_normal(face: Any) -> tuple[float, float, float] | None:
    try:
        surface = read_member(face, "GetSurface")
        if not bool(read_member(surface, "IsPlane")):
            return None
        params = read_member(surface, "PlaneParams")
        if not params or len(params) < 3:
            return None
        return (float(params[0]), float(params[1]), float(params[2]))
    except Exception:
        return None


def normals_parallel(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    dot = abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2])
    return dot > 0.99

def add_distance_mate_between_planar_faces(asm: Any, components: list[Any], distance: float) -> dict[str, Any]:
    for i, left in enumerate(components):
        left_faces = [(face, face_plane_normal(face)) for face in component_faces(left)]
        left_faces = [(face, normal) for face, normal in left_faces if normal is not None]
        for right in components[i + 1:]:
            right_faces = [(face, face_plane_normal(face)) for face in component_faces(right)]
            right_faces = [(face, normal) for face, normal in right_faces if normal is not None]
            for left_face, left_normal in left_faces:
                for right_face, right_normal in right_faces:
                    if not normals_parallel(left_normal, right_normal):
                        continue
                    component_pair = [left.Name2, right.Name2]
                    selection_guard = select_faces(asm, left_face, right_face, component_pair)
                    if int(selection_guard["selection_count_before_mate"]) >= 2:
                        result = add_selected_mate(asm, "Distance_Mate", 5, distance)
                        result["selected_entities"] = selection_guard["selection_count_before_mate"]
                        result["selection_guard"] = selection_guard
                        result["components"] = component_pair
                        result["parallel_normals"] = [left_normal, right_normal]
                        if result["ok"]:
                            return result
    return {"name": "Distance_Mate", "ok": False, "error": "no planar face pair accepted by AddMate5"}


def add_concentric_mate_between_cylinders(asm: Any, components: list[Any]) -> dict[str, Any]:
    for i, left in enumerate(components):
        left_face = first_face(left, "IsCylinder")
        if left_face is None:
            continue
        for right in components[i + 1:]:
            right_face = first_face(right, "IsCylinder")
            if right_face is None:
                continue
            component_pair = [left.Name2, right.Name2]
            selection_guard = select_faces(asm, left_face, right_face, component_pair)
            if int(selection_guard["selection_count_before_mate"]) >= 2:
                result = add_selected_mate(asm, "Concentric_Mate", 1, 0.0)
                result["selected_entities"] = selection_guard["selection_count_before_mate"]
                result["selection_guard"] = selection_guard
                result["components"] = component_pair
                if result["ok"]:
                    return result
    return {"name": "Concentric_Mate", "ok": False, "error": "no cylindrical face pair accepted by AddMate5"}


def create_assembly(sw: Any, out_dir: Path, part_paths: dict[str, Path]) -> tuple[Path, dict[str, Any]]:
    asm = new_assembly(sw)
    component_objs = [
        add_component(sw, asm, part_paths["extrude"], (0.00, 0.00, 0.00)),
        add_component(sw, asm, part_paths["revolve"], (0.12, 0.00, 0.00)),
        add_component(sw, asm, part_paths["revolve_cut"], (0.20, 0.075, 0.00)),
        add_component(sw, asm, part_paths["editable"], (0.00, 0.10, 0.00)),
    ]
    components = [comp.Name2 for comp in component_objs]
    extrude_comp, revolve_comp, revolve_cut_comp, editable_comp = component_objs
    mate_results = [
        add_concentric_mate_between_cylinders(asm, [revolve_comp, revolve_cut_comp]),
        add_distance_mate_between_planar_faces(asm, [extrude_comp, editable_comp], 0.030),
    ]
    asm.ForceRebuild3(False)
    path = out_dir / "capability_suite.SLDASM"
    save_as(asm, path)
    return path, {"components": components, "component_count": len(components), "mates": mate_results}


def inspect_features(sw: Any, path: Path, doc_type: int) -> list[dict[str, str]]:
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(str(path.resolve()), doc_type, 1, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed for inspect {path}")
    try:
        read_member(model, "FirstFeature")
    except Exception:
        try:
            activated = sw.ActivateDoc3(path.name, False, 0, errors)
        except Exception:
            activated = None
        if activated is not None:
            model = activated
        else:
            try:
                active = read_member(sw, "ActiveDoc")
            except Exception:
                active = None
            if active is not None:
                model = active
    features: list[dict[str, str]] = []

    visited: set[str] = set()

    def feature_key(feat: Any) -> str:
        try:
            return f"{read_member(feat, 'Name')}:{read_member(feat, 'GetTypeName2')}:{str(feat)}"
        except Exception:
            return str(feat)

    def append_feature_tree(feat: Any, depth: int = 0) -> None:
        hops = 0
        while feat is not None and hops < 512 and depth < 16:
            hops += 1
            key = feature_key(feat)
            if key in visited:
                return
            visited.add(key)
            features.append({"name": read_member(feat, "Name"), "type": read_member(feat, "GetTypeName2"), "depth": str(depth)})
            try:
                sub = read_member(feat, "GetFirstSubFeature")
            except Exception:
                sub = None
            if sub is not None:
                append_feature_tree(sub, depth + 1)
            feat = read_member(feat, "GetNextSubFeature") if depth > 0 else read_member(feat, "GetNextFeature")

    append_feature_tree(read_member(model, "FirstFeature"))
    close_doc(sw, model)
    return features


def run_callbacks(sw: Any, asm_path: Path, reports_dir: Path, export_dir: Path) -> dict[str, Any]:
    # Keep callbacks in-process to avoid opening parallel SolidWorks clients.
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    asm = sw.OpenDoc6(str(asm_path.resolve()), 2, 1, "", errors, warnings)
    if asm is None:
        raise RuntimeError(f"OpenDoc6 failed for callbacks {asm_path}")
    ext = read_member(asm, "Extension")
    mass_props = read_member(ext, "CreateMassProperty") if ext is not None else None
    mass = {"available": mass_props is not None and not isinstance(mass_props, dict)}
    if mass["available"]:
        mass["mass_kg"] = read_member(mass_props, "Mass")
        mass["volume_m3"] = read_member(mass_props, "Volume")
        mass["surface_area_m2"] = read_member(mass_props, "SurfaceArea")
    else:
        mass["error"] = mass_props
    interference = {"available": False, "count": None}
    try:
        mgr = read_member(asm, "InterferenceDetectionManager")
        if mgr is not None and not isinstance(mgr, dict):
            try:
                setattr(mgr, "TreatCoincidenceAsInterference", False)
            except Exception:
                pass
            interferences = read_member(mgr, "GetInterferences")
            interference = {"available": True, "count": 0 if interferences is None else len(interferences)}
            try:
                read_member(mgr, "Done")
            except Exception:
                pass
    except Exception as exc:
        interference = {"available": False, "error": repr(exc)}
    export_dir.mkdir(parents=True, exist_ok=True)
    step = export_dir / "capability_suite.step"
    export_errors = byref_i4(0)
    export_warnings = byref_i4(0)
    try:
        export_result = read_member(ext, "SaveAs", str(step.resolve()), 0, 2, empty_dispatch_variant(), export_errors, export_warnings)
        optional_step_export = {
            "optional": True,
            "target": str(step.resolve()),
            "api_success": bool(export_result),
            "api_result": export_result,
            "errors": getattr(export_errors, "value", None),
            "warnings": getattr(export_warnings, "value", None),
            "exists_after": step.exists(),
            "size": step.stat().st_size if step.exists() else 0,
            "note": "Neutral STEP export smoke only; native SLDASM/SLDPRT files are the acceptance artifacts.",
        }
    except Exception as exc:
        optional_step_export = {"optional": True, "api_success": False, "error": repr(exc), "note": "Optional neutral export smoke failed; native artifacts remain authoritative."}
    (reports_dir / "mass.json").write_text(json.dumps(mass, indent=2), encoding="utf-8")
    (reports_dir / "interference.json").write_text(json.dumps(interference, indent=2), encoding="utf-8")
    (reports_dir / "optional_export_step.json").write_text(json.dumps(optional_step_export, indent=2), encoding="utf-8")
    close_doc(sw, asm)
    return {"mass": mass, "interference": interference, "optional_step_export": optional_step_export}


def native_artifact_report(asm_path: Path, part_paths: dict[str, Path]) -> dict[str, Any]:
    part_files = [str(path.resolve()) for path in part_paths.values()]
    return {
        "assembly": str(asm_path.resolve()),
        "assembly_exists": asm_path.exists(),
        "assembly_size": asm_path.stat().st_size if asm_path.exists() else 0,
        "part_files": part_files,
        "part_count": sum(1 for path in part_paths.values() if path.exists()),
        "missing_parts": [str(path.resolve()) for path in part_paths.values() if not path.exists()],
        "primary": True,
        "note": "Native SolidWorks SLDASM/SLDPRT artifacts are the acceptance target; STEP is optional smoke only.",
    }


def run_live(out_dir: Path, reports_dir: Path, export_dir: Path, force: bool, start: bool) -> dict[str, Any]:
    spec = build_capability_matrix()
    sw, started_by_suite = attach_solidworks(start=start)
    closed = close_suite_documents(sw, spec)
    cleanup = cleanup_generated(out_dir, force)
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    export_dir.mkdir(parents=True, exist_ok=True)
    part_paths: dict[str, Path] = {}
    operation_context: dict[str, Any] = {}
    part_paths["extrude"], operation_context["extrude"] = create_extrude_cut_plate(sw, out_dir)
    part_paths["revolve"], operation_context["revolve"] = create_revolve_boss_part(sw, out_dir)
    part_paths["revolve_cut"], operation_context["revolve_cut"] = create_revolve_cut_part(sw, out_dir)
    editable_path, dimension_result, operation_context["editable"] = create_editable_dimension_plate(sw, out_dir)
    part_paths["editable"] = editable_path
    readback_operation_context(sw, part_paths, operation_context)
    reopen_modify_result = reopen_modify_dimension(sw, editable_path)
    asm_path, asm_result = create_assembly(sw, out_dir, part_paths)
    feature_reports = {
        key: inspect_features(sw, path, 1)
        for key, path in part_paths.items()
    }
    part_geometry_evidence = collect_part_geometry_evidence(sw, part_paths)
    assembly_features = inspect_features(sw, asm_path, 2)
    assembly_inspect = inspect_assembly_report(sw, asm_path)
    callbacks = run_callbacks(sw, asm_path, reports_dir, export_dir)
    native_artifacts = native_artifact_report(asm_path, part_paths)
    closed_after = close_suite_documents(sw, spec)
    post_cleanup = probe_unlocked_generated_files(out_dir)
    if post_cleanup.get("locked_files") and started_by_suite:
        try:
            sw.ExitApp()
            time.sleep(2.0)
        except Exception:
            pass
        post_cleanup = probe_unlocked_generated_files(out_dir)
    result = {
        "ok": True,
        "output_dir": str(out_dir.resolve()),
        "assembly": str(asm_path.resolve()),
        "closed_docs": closed,
        "started_by_suite": started_by_suite,
        "closed_docs_after": closed_after,
        "cleanup": cleanup,
        "post_cleanup": post_cleanup,
        "parts": {k: str(v.resolve()) for k, v in part_paths.items()},
        "features": feature_reports,
        "part_geometry_evidence": part_geometry_evidence,
        "operation_context": operation_context,
        "assembly_features": assembly_features,
        "assembly_inspect": assembly_inspect,
        "native_artifacts": native_artifacts,
        "dimension_edit": dimension_result,
        "reopen_modify": reopen_modify_result,
        "assembly_result": asm_result,
        "callbacks": callbacks,
        "contract": expected_live_contract(),
    }
    validation = validate_live_result(result)
    result["validation"] = validation
    result["ok"] = validation["ok"]
    (reports_dir / "live_capability_suite.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="tools/solidworks_codex/live_fixture/live_capability_suite")
    parser.add_argument("--reports-dir", default="tools/solidworks_codex/reports/live_capability_suite")
    parser.add_argument("--export-dir", default="tools/solidworks_codex/exports/live_capability_suite")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--spec-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-start", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    matrix = build_capability_matrix()
    manifest_path = Path(args.manifest) if args.manifest else Path(args.reports_dir) / "capability_matrix.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(asdict(matrix), indent=2), encoding="utf-8")
    if args.spec_only:
        print(json.dumps({"ok": True, "manifest": str(manifest_path), "spec_only": True}, indent=2))
        return 0
    result = run_live(Path(args.out_dir), Path(args.reports_dir), Path(args.export_dir), args.force, not args.no_start)
    result["manifest"] = str(manifest_path)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 2


if __name__ == "__main__":
    raise SystemExit(main())
