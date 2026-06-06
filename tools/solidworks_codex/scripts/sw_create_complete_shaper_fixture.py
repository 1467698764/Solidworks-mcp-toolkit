#!/usr/bin/env python3
"""Generate a retained native SolidWorks simple-mechanism regression fixture.

The earlier v4 display fixture proved feature creation, but its side-elevation
parts were dimensioned with the machine height in SolidWorks Z. That produced
misplaced parts and many interferences. This v5 generator treats the Front Plane
sketch as the visible side elevation: size_mm is (X length, Y height, Z thickness).
It records assembly mates, mass, native files, and interference callbacks so the
fixture can expose generic CAD-control gaps. Passing this fixture is not proof
that general mechanism assembly is solved.
"""
from __future__ import annotations

import argparse
import json
import math
import subprocess
import importlib.util
import traceback
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class FeatureSpec:
    kind: str
    count: int
    note: str


@dataclass(frozen=True)
class PartSpec:
    name: str
    kind: str
    size_mm: tuple[float, float, float]
    role: str
    features: tuple[FeatureSpec, ...]


@dataclass(frozen=True)
class CompleteShaperSpec:
    name: str
    quality_target: str
    output_dir: str
    reports_dir: str
    assembly_file: str
    parts: tuple[PartSpec, ...]
    acceptance_rules: tuple[str, ...]


def F(kind: str, count: int, note: str) -> FeatureSpec:
    return FeatureSpec(kind, count, note)


def build_complete_shaper_spec() -> CompleteShaperSpec:
    out = "tools/solidworks_codex/live_fixture/shaper_machine_v5"
    parts = (
        PartSpec("cast_bed_with_t_slots", "bed", (680, 240, 55), "cast base with feet, ribs, mounting holes and T-slots", (F("mounting_hole_pattern", 6, "floor mounting holes"), F("t_slot_cut", 3, "long top table slots"), F("rib", 5, "triangular side ribs"), F("cut", 9, "holes and slots"), F("hole", 12, "mounting and fastening holes"), F("slot", 3, "T-slots"))),
        PartSpec("column_frame_with_window", "frame", (155, 330, 42), "upright frame with large window and bearing bores", (F("frame_window_cut", 1, "arched service window"), F("bearing_bore", 2, "crank and rocker shaft bores"), F("rib", 4, "vertical web ribs"), F("hole", 8, "cover and bearing cap holes"), F("cut", 5, "window and bores"))),
        PartSpec("ram_with_dovetail_and_tool_mount", "ram", (330, 70, 58), "sliding ram with dovetail underside and tool-head bolt face", (F("dovetail_cut", 2, "lower dovetail ways"), F("bolt_hole_pattern", 6, "tool head mounting holes"), F("oil_groove", 2, "lubrication grooves"), F("hole", 8, "mounting and oil holes"), F("cut", 4, "dovetails and grooves"))),
        PartSpec("clapper_tool_head", "tool_head", (70, 105, 38), "clapper box and tool head with clamp holes", (F("bolt_hole_pattern", 4, "clapper cover bolts"), F("tool_slot_cut", 1, "vertical tool slot"), F("pin_bore", 1, "clapper pivot"), F("hole", 7, "bolts and pivot"), F("slot", 1, "tool slot"))),
        PartSpec("single_point_cutting_tool", "tool", (16, 115, 12), "visible cutting tool bit", (F("beveled_tip", 1, "angled cutting end"),)),
        PartSpec("bull_gear_crank_disk", "crank_disk", (155, 155, 22), "toothed bull gear crank disk with center bore, eccentric pin hole, and ordered lightening holes", (F("gear_tooth_profile", 32, "visible external gear teeth"), F("center_bore", 1, "main shaft hole"), F("eccentric_pin_hole", 1, "offset drive pin hole"), F("lightening_hole_pattern", 6, "ordered circular lightening holes"), F("hole", 8, "disk holes"), F("cut", 8, "bores and lightening cuts"))),
        PartSpec("eccentric_crank_pin", "pin", (22, 22, 70), "eccentric pin with washer stack", (F("pin_bore", 1, "cylindrical pin"),)),
        PartSpec("slotted_rocker_arm", "rocker", (70, 285, 22), "slotted rocker arm with rounded ends and pivot holes", (F("long_slot_cut", 1, "sliding die slot"), F("pin_bore", 3, "pivot and link holes"), F("rounded_end", 2, "rounded fork ends"), F("hole", 3, "pivot/link holes"), F("slot", 1, "main slot"), F("cut", 4, "slot and bores"))),
        PartSpec("bronze_sliding_die_block", "slider", (52, 38, 34), "die block in rocker slot with cross pin bore", (F("pin_bore", 1, "crank pin bore"), F("oil_groove", 1, "lubrication groove"), F("hole", 1, "pin hole"), F("cut", 2, "bore and groove"))),
        PartSpec("rocker_pivot_bracket", "bracket", (105, 115, 56), "forked bracket with pivot bore and bolt holes", (F("bearing_bore", 1, "rocker shaft bore"), F("bolt_hole_pattern", 4, "base bolts"), F("fork_slot_cut", 1, "fork relief"), F("hole", 5, "bore plus bolts"), F("slot", 1, "fork relief"))),
        PartSpec("ram_drive_link", "link", (210, 24, 20), "two-ended drive link with round eye holes", (F("pin_bore", 2, "end eye bores"), F("rounded_end", 2, "rounded link ends"), F("hole", 2, "eye holes"))),
        PartSpec("left_dovetail_way", "way", (390, 24, 32), "left dovetail guide rail with bolt holes", (F("dovetail_rail", 1, "angled guide rail"), F("bolt_hole_pattern", 6, "rail screws"), F("hole", 6, "rail screw holes"))),
        PartSpec("right_dovetail_way", "way", (390, 24, 32), "right dovetail guide rail with bolt holes", (F("dovetail_rail", 1, "angled guide rail"), F("bolt_hole_pattern", 6, "rail screws"), F("hole", 6, "rail screw holes"))),
        PartSpec("front_gib_plate", "gib", (260, 14, 18), "front gib strip with screws", (F("bolt_hole_pattern", 5, "adjusting screws"), F("hole", 5, "gib screw holes"))),
        PartSpec("rear_gib_plate", "gib", (260, 14, 18), "rear gib strip with screws", (F("bolt_hole_pattern", 5, "adjusting screws"), F("hole", 5, "gib screw holes"))),
        PartSpec("table_cross_slide", "slide", (250, 38, 150), "cross slide under work table", (F("t_slot_cut", 2, "cross slide slots"), F("dovetail_cut", 1, "cross dovetail"), F("hole", 4, "feed screw holes"), F("slot", 2, "slide slots"))),
        PartSpec("work_table_with_t_slots", "table", (310, 32, 175), "work table with multiple T-slots", (F("t_slot_cut", 4, "work holding T-slots"), F("bolt_hole_pattern", 4, "table mounting holes"), F("hole", 4, "mounting holes"), F("slot", 4, "T-slots"))),
        PartSpec("vise_jaw_fixed", "vise", (95, 45, 22), "fixed vise jaw", (F("bolt_hole_pattern", 2, "jaw screws"), F("serrated_face", 1, "jaw serrations"), F("hole", 2, "jaw screw holes"))),
        PartSpec("vise_jaw_movable", "vise", (95, 45, 22), "movable vise jaw", (F("bolt_hole_pattern", 2, "jaw screws"), F("serrated_face", 1, "jaw serrations"), F("hole", 2, "jaw screw holes"))),
        PartSpec("rocker_pivot_shaft", "shaft", (24, 24, 105), "rocker pivot shaft", (F("shaft", 1, "cylindrical shaft"),)),
        PartSpec("crank_center_shaft", "shaft", (30, 30, 115), "crank center shaft", (F("shaft", 1, "cylindrical shaft"),)),
        PartSpec("fastener_set_m6", "fasteners", (10, 10, 18), "visible M6 hex bolts distributed across model", (F("hex_bolt", 18, "hex head bolts"), F("fastener", 18, "bolt instances"))),
        PartSpec("washer_set", "washers", (16, 16, 3), "visible washers on shafts and bolts", (F("washer", 18, "washer instances"), F("fastener", 18, "washer instances"))),
        PartSpec("oil_cups", "details", (12, 12, 10), "small oil cups on ram and bearings", (F("oil_cup", 4, "lubrication cups"), F("fastener", 4, "small detail parts"))),
    )
    return CompleteShaperSpec(
        name="bullhead_shaper_complete",
        quality_target="mechanism_assembly_validation",
        output_dir=out,
        reports_dir="tools/solidworks_codex/reports/shaper_machine_v5",
        assembly_file=f"{out}/bullhead_shaper_complete.SLDASM",
        parts=parts,
        acceptance_rules=("no_plain_block_stack", "visible_holes_slots_and_fasteners", "named_gear_has_tooth_profile", "recognizable_bullhead_shaper_silhouette", "mechanism_profile_blocking_checks"),
    )


def spec_to_manifest(spec: CompleteShaperSpec) -> dict[str, Any]:
    counts: dict[str, int] = {"cut": 0, "hole": 0, "slot": 0, "fastener": 0}
    for part in spec.parts:
        for feat in part.features:
            if feat.kind in counts:
                counts[feat.kind] += feat.count
            if "hole" in feat.kind or "bore" in feat.kind:
                counts["hole"] += feat.count
            if "slot" in feat.kind:
                counts["slot"] += feat.count
            if feat.kind in {"mounting_hole_pattern", "bolt_hole_pattern", "center_bore", "pin_bore", "bearing_bore", "eccentric_pin_hole", "lightening_hole_pattern"}:
                counts["cut"] += feat.count
    data = asdict(spec)
    data["part_count"] = len(spec.parts)
    data["feature_counts"] = counts
    return data


def expected_live_feature_names() -> dict[str, tuple[str, ...]]:
    return {
        "cast_bed_with_t_slots": ("T_Slot_Cuts", "Floor_Mounting_Holes", "Web_Rib_1"),
        "column_frame_with_window": ("Frame_Window_Cut", "Bearing_Bores_And_Cover_Holes"),
        "ram_with_dovetail_and_tool_mount": ("Dovetail_And_Oil_Groove_Cuts", "Angled_Dovetail_Underside_Cut", "Tool_Mount_Bolt_Holes"),
        "single_point_cutting_tool": ("Beveled_Cutting_Tip",),
        "bull_gear_crank_disk": ("Gear_Tooth_Profile", "Center_Eccentric_And_Lightening_Holes"),
        "slotted_rocker_arm": ("Long_Sliding_Slot", "Rocker_Pin_Bores"),
        "work_table_with_t_slots": ("Work_Table_T_Slots", "Table_Mount_Holes"),
        "left_dovetail_way": ("Dovetail_Relief", "Left_Angled_Dovetail_Flank", "Right_Angled_Dovetail_Flank", "Rail_Screw_Holes"),
        "right_dovetail_way": ("Dovetail_Relief", "Left_Angled_Dovetail_Flank", "Right_Angled_Dovetail_Flank", "Rail_Screw_Holes"),
        "fastener_set_m6": ("Hex_Body_fastener_set_m6", "Hex_Socket_Drive"),
    }


def expected_shaper_mate_contract() -> dict[str, dict[str, Any]]:
    """Semantic interface mate network for the retained mechanism fixture.

    This is intentionally a real mate contract, not a layout-lock fixture. The
    fixture still restores authored transforms before solving so SolidWorks has
    a sensible starting pose, but acceptance requires coincident and concentric
    interface evidence for the recognizable shaper subassemblies.
    """
    pairs = {
        "Bed_Column_Parallel": ("parallel", ["cast_bed_with_t_slots", "column_frame_with_window"], "structure"),
        "Bed_Column_Contact": ("coincident", ["cast_bed_with_t_slots", "column_frame_with_window"], "structure"),
        "Column_Bed_Setback": ("distance", ["column_frame_with_window", "cast_bed_with_t_slots"], "structure"),
        "Column_Bed_Perpendicular": ("perpendicular", ["column_frame_with_window", "cast_bed_with_t_slots"], "structure"),
        "Left_Way_Column_Parallel": ("parallel", ["left_dovetail_way", "column_frame_with_window"], "ram_guidance"),
        "Left_Way_Column_Contact": ("distance", ["left_dovetail_way", "column_frame_with_window"], "ram_guidance"),
        "Right_Way_Column_Parallel": ("parallel", ["right_dovetail_way", "column_frame_with_window"], "ram_guidance"),
        "Right_Way_Column_Contact": ("distance", ["right_dovetail_way", "column_frame_with_window"], "ram_guidance"),
        "Way_Spacing_Distance": ("parallel", ["left_dovetail_way", "right_dovetail_way"], "ram_guidance"),
        "Ram_Left_Way_Parallel": ("parallel", ["ram_with_dovetail_and_tool_mount", "left_dovetail_way"], "ram_guidance"),
        "Ram_LeftWay_Guidance_Distance_Mate": ("distance", ["ram_with_dovetail_and_tool_mount", "left_dovetail_way"], "ram_guidance"),
        "Ram_Right_Way_Parallel": ("parallel", ["ram_with_dovetail_and_tool_mount", "right_dovetail_way"], "ram_guidance"),
        "Ram_Centered_Between_Ways": ("width", ["ram_with_dovetail_and_tool_mount", "left_dovetail_way", "right_dovetail_way"], "ram_guidance"),
        "Ram_Stroke_Limit": ("limit_distance", ["ram_with_dovetail_and_tool_mount", "column_frame_with_window"], "ram_guidance"),
        "Front_Gib_Ram_Parallel": ("parallel", ["front_gib_plate", "ram_with_dovetail_and_tool_mount"], "ram_guidance"),
        "Front_Gib_Ram_Clearance": ("limit_distance", ["front_gib_plate", "ram_with_dovetail_and_tool_mount"], "ram_guidance"),
        "Rear_Gib_Ram_Parallel": ("parallel", ["rear_gib_plate", "ram_with_dovetail_and_tool_mount"], "ram_guidance"),
        "Rear_Gib_Ram_Clearance": ("limit_distance", ["rear_gib_plate", "ram_with_dovetail_and_tool_mount"], "ram_guidance"),
        "Tool_Head_Ram_Parallel": ("parallel", ["clapper_tool_head", "ram_with_dovetail_and_tool_mount"], "tool_head"),
        "Tool_Head_Ram_Contact": ("coincident", ["clapper_tool_head", "ram_with_dovetail_and_tool_mount"], "tool_head"),
        "Tool_Tool_Head_Parallel": ("parallel", ["single_point_cutting_tool", "clapper_tool_head"], "tool_head"),
        "Tool_Tool_Head_Contact": ("distance", ["single_point_cutting_tool", "clapper_tool_head"], "tool_head"),
        "Table_Slide_Parallel": ("parallel", ["work_table_with_t_slots", "table_cross_slide"], "workholding"),
        "Table_Slide_Contact": ("coincident", ["work_table_with_t_slots", "table_cross_slide"], "workholding"),
        "Slide_Bed_Parallel": ("parallel", ["table_cross_slide", "cast_bed_with_t_slots"], "workholding"),
        "Slide_Bed_Contact": ("distance", ["table_cross_slide", "cast_bed_with_t_slots"], "workholding"),
        "Fixed_Jaw_Table_Parallel": ("parallel", ["vise_jaw_fixed", "work_table_with_t_slots"], "workholding"),
        "Fixed_Jaw_Table_Contact": ("coincident", ["vise_jaw_fixed", "work_table_with_t_slots"], "workholding"),
        "Movable_Jaw_Table_Parallel": ("parallel", ["vise_jaw_movable", "work_table_with_t_slots"], "workholding"),
        "Movable_Jaw_Table_Clearance": ("limit_distance", ["vise_jaw_movable", "work_table_with_t_slots"], "workholding"),
        "Bull_Gear_Crank_Shaft_Concentric": ("concentric", ["bull_gear_crank_disk", "crank_center_shaft"], "quick_return_drive"),
        "Crank_Shaft_Axial_Locator": ("limit_distance", ["bull_gear_crank_disk", "crank_center_shaft"], "quick_return_drive"),
        "Crank_Reference_Angle": ("limit_angle", ["bull_gear_crank_disk", "column_frame_with_window"], "quick_return_drive"),
        "Eccentric_Pin_Bull_Gear_Concentric": ("concentric", ["eccentric_crank_pin", "bull_gear_crank_disk"], "quick_return_drive"),
        "Eccentric_Pin_Axial_Locator": ("limit_distance", ["eccentric_crank_pin", "bull_gear_crank_disk"], "quick_return_drive"),
        "Rocker_Pivot_Shaft_Bracket_Concentric": ("concentric", ["rocker_pivot_shaft", "rocker_pivot_bracket"], "quick_return_drive"),
        "Rocker_Pivot_Shaft_Axial_Locator": ("limit_distance", ["rocker_pivot_shaft", "rocker_pivot_bracket"], "quick_return_drive"),
        "Rocker_Arm_Pivot_Shaft_Concentric": ("concentric", ["slotted_rocker_arm", "rocker_pivot_shaft"], "quick_return_drive"),
        "Rocker_Arm_Axial_Locator": ("limit_distance", ["slotted_rocker_arm", "rocker_pivot_shaft"], "quick_return_drive"),
        "Sliding_Die_Rocker_Concentric": ("concentric", ["bronze_sliding_die_block", "slotted_rocker_arm"], "quick_return_drive"),
        "Sliding_Die_Rocker_Slot_Clearance": ("limit_distance", ["bronze_sliding_die_block", "slotted_rocker_arm"], "quick_return_drive"),
        "Ram_Link_Ram_Concentric": ("concentric", ["ram_drive_link", "ram_with_dovetail_and_tool_mount"], "quick_return_drive"),
        "Ram_Link_Ram_Axial_Locator": ("limit_distance", ["ram_drive_link", "ram_with_dovetail_and_tool_mount"], "quick_return_drive"),
    }
    return {
        name: {"type": kind, "semantic_pair": pair, "functional_group": group}
        for name, (kind, pair, group) in pairs.items()
    }


def expected_shaper_functional_connection_contract() -> list[tuple[str, str]]:
    """Required physical adjacency/proximity pairs for the complete shaper.

    Mates prove constraint intent; this contract separately proves the visible
    assembly is not a cloud of parts. Every pair must be present in spatial
    near/overlap evidence from model-understand, independent of group inventory.
    """
    pairs: list[tuple[str, str]] = []
    for item in expected_shaper_mate_contract().values():
        semantic_pair = list(item["semantic_pair"])
        if len(semantic_pair) < 2:
            continue
        anchor = semantic_pair[0]
        pairs.extend((anchor, other) for other in semantic_pair[1:])
    return pairs


def expected_inspect_mate_type(kind: str) -> str:
    return {
        "coincident": "MateCoincident",
        "parallel": "MateParallel",
        "perpendicular": "MatePerpendicular",
        "distance": "MateDistanceDim",
        "limit_distance": "MateLimitDistanceDim",
        "angle": "MateAngleDim",
        "limit_angle": "MateLimitPlanarAngleDim",
        "width": "MateWidth",
        "concentric": "MateConcentric",
        "lock": "MateLock",
    }.get(kind, f"Mate:{kind}")


def component_pair_matches_semantic_pair(component_names: Any, semantic_pair: list[str]) -> bool:
    if not isinstance(component_names, list) or len(component_names) < 2:
        return False
    text = "\n".join(str(item) for item in component_names)
    return all(part_name in text for part_name in semantic_pair)


def int_equals(value: Any, expected: int) -> bool:
    try:
        return int(value) == expected
    except (TypeError, ValueError):
        return False


def part_size_m_by_name() -> dict[str, tuple[float, float, float]]:
    return {part.name: tuple(value / 1000.0 for value in part.size_mm) for part in build_complete_shaper_spec().parts}


def authored_component_origin(part_name: str) -> tuple[float, float, float]:
    return authored_primary_origins_for_shaper().get(part_name, (0.0, 0.0, 0.0))


def interface_origin_m(part_name: str, axis: str, side: str) -> list[float]:
    origin = list(authored_component_origin(part_name))
    size = part_size_m_by_name().get(part_name, (0.0, 0.0, 0.0))
    axis_index = {"x": 0, "y": 1, "z": 2}[axis]
    offset = size[axis_index] / 2.0
    origin[axis_index] += offset if side == "max" else -offset
    return [float(value) for value in origin]


def planar_intent_selector(part_name: str, axis: str, side: str, role: str = "interface") -> dict[str, Any]:
    return {
        "stable_id": f"{part_name}-1:face:{axis}_{side}:{role}",
        "component": f"{part_name}-1",
        "fallback": {
            "type": "bbox_planar_face",
            "normal": list(axis_vector(axis)),
            "origin_m": interface_origin_m(part_name, axis, side),
            "interface_axis": axis,
            "interface_side": side,
        },
    }


def cylindrical_intent_selector(part_name: str, role: str = "axis") -> dict[str, Any]:
    origin = list(authored_component_origin(part_name))
    size = part_size_m_by_name().get(part_name, (0.0, 0.0, 0.0))
    return {
        "stable_id": f"{part_name}-1:cylindrical_axis:{role}",
        "component": f"{part_name}-1",
        "fallback": {
            "type": "cylindrical_axis",
            "axis": [0.0, 0.0, 1.0],
            "origin_m": [float(value) for value in origin],
            "radius_m": max(size[0], size[1]) / 2.0 if size else 0.01,
        },
    }


def planar_intent_selectors_for_mate(name: str, semantic_pair: list[str]) -> list[dict[str, Any]]:
    left_selector, right_selector = shaper_planar_interface_selector(name, semantic_pair)
    return [
        planar_intent_selector(semantic_pair[0], left_selector[0], left_selector[1], name),
        planar_intent_selector(semantic_pair[1], right_selector[0], right_selector[1], name),
    ]


def direct_shaper_mate_intent(name: str, expected: dict[str, Any]) -> dict[str, Any]:
    semantic_pair = list(expected["semantic_pair"])
    kind = str(expected["type"])
    intent: dict[str, Any] = {
        "id": name,
        "kind": "direct_mate",
        "mate_type": kind,
        "expected_mate_name": name,
        "components": [f"{part_name}-1" for part_name in semantic_pair],
    }
    if kind == "concentric":
        intent["selection_selectors"] = [cylindrical_intent_selector(part, name) for part in semantic_pair[:2]]
    else:
        intent["selection_selectors"] = planar_intent_selectors_for_mate(name, semantic_pair)
    if kind in {"distance", "limit_distance"}:
        nominal = shaper_distance_mate_clearance(name)
        intent["distance_m"] = nominal
        if kind == "limit_distance":
            limit_min, limit_max = shaper_limit_distance_bounds(name)
            intent["distance_min_m"] = limit_min
            intent["distance_max_m"] = limit_max
    if kind in {"angle", "limit_angle"}:
        intent["angle_rad"] = math.radians(90.0)
        if kind == "limit_angle":
            intent["angle_min_rad"] = 0.0
            intent["angle_max_rad"] = math.pi
    return intent


def build_shaper_mate_intent_spec() -> dict[str, Any]:
    contract = expected_shaper_mate_contract()
    consumed: set[str] = set()
    intents: list[dict[str, Any]] = []

    def add_rigid_mount(intent_id: str, contact_name: str, orientation_name: str | None = None) -> None:
        contact = contract[contact_name]
        pair = list(contact["semantic_pair"])
        contact_selectors = planar_intent_selectors_for_mate(contact_name, pair)
        interfaces = {"mount_face": contact_selectors[0], "host_face": contact_selectors[1]}
        expected_names = {"contact": contact_name}
        if orientation_name is not None:
            orientation = contract[orientation_name]
            orientation_selectors = planar_intent_selectors_for_mate(orientation_name, list(orientation["semantic_pair"]))
            interfaces["orientation_face"] = orientation_selectors[0]
            interfaces["host_orientation_face"] = orientation_selectors[1]
            expected_names["orientation"] = orientation_name
            consumed.add(orientation_name)
        intents.append({
            "id": intent_id,
            "kind": "rigid_mount",
            "components": [f"{part_name}-1" for part_name in pair],
            "expected_mate_names": expected_names,
            "interfaces": interfaces,
        })
        consumed.add(contact_name)

    def add_revolute(intent_id: str, concentric_name: str, axial_name: str | None = None) -> None:
        concentric = contract[concentric_name]
        pair = list(concentric["semantic_pair"])
        interfaces = {
            "shaft_axis": cylindrical_intent_selector(pair[0], concentric_name),
            "bore_axis": cylindrical_intent_selector(pair[1], concentric_name),
        }
        expected_names = {"concentric": concentric_name}
        intent: dict[str, Any] = {
            "id": intent_id,
            "kind": "revolute",
            "components": [f"{part_name}-1" for part_name in pair],
            "expected_mate_names": expected_names,
            "interfaces": interfaces,
        }
        if axial_name is not None:
            axial = contract[axial_name]
            axial_pair = list(axial["semantic_pair"])
            axial_selectors = planar_intent_selectors_for_mate(axial_name, axial_pair)
            interfaces["shaft_axial_face"] = axial_selectors[0]
            interfaces["housing_axial_face"] = axial_selectors[1]
            expected_names["axial_locator"] = axial_name
            nominal = shaper_distance_mate_clearance(axial_name)
            limit_min, limit_max = shaper_limit_distance_bounds(axial_name)
            intent["axial_clearance_m"] = nominal
            intent["axial_min_m"] = limit_min
            intent["axial_max_m"] = limit_max
            consumed.add(axial_name)
        intents.append(intent)
        consumed.add(concentric_name)

    add_rigid_mount("bed_column_primary_mount", "Bed_Column_Contact", "Bed_Column_Parallel")
    add_rigid_mount("tool_head_to_ram_mount", "Tool_Head_Ram_Contact", "Tool_Head_Ram_Parallel")
    add_rigid_mount("tool_bit_to_clapper_mount", "Tool_Tool_Head_Contact", "Tool_Tool_Head_Parallel")
    add_rigid_mount("table_to_cross_slide_mount", "Table_Slide_Contact", "Table_Slide_Parallel")
    add_rigid_mount("fixed_jaw_to_table_mount", "Fixed_Jaw_Table_Contact", "Fixed_Jaw_Table_Parallel")

    width_selectors = shaper_width_interface_selector("Ram_Centered_Between_Ways")
    travel_min, travel_max = shaper_limit_distance_bounds("Ram_Stroke_Limit")
    travel_selectors = planar_intent_selectors_for_mate("Ram_Stroke_Limit", list(contract["Ram_Stroke_Limit"]["semantic_pair"]))
    intents.append({
        "id": "ram_guided_between_dovetail_ways",
        "kind": "prismatic",
        "components": ["ram_with_dovetail_and_tool_mount-1", "left_dovetail_way-1", "right_dovetail_way-1"],
        "distance_m": shaper_distance_mate_clearance("Ram_Stroke_Limit"),
        "distance_min_m": travel_min,
        "distance_max_m": travel_max,
        "expected_mate_names": {"width": "Ram_Centered_Between_Ways", "travel_limit": "Ram_Stroke_Limit"},
        "interfaces": {
            "guide_left_face": planar_intent_selector("left_dovetail_way", *width_selectors["left_way"], "Ram_Centered_Between_Ways"),
            "guide_right_face": planar_intent_selector("right_dovetail_way", *width_selectors["right_way"], "Ram_Centered_Between_Ways"),
            "slider_left_face": planar_intent_selector("ram_with_dovetail_and_tool_mount", *width_selectors["ram_left"], "Ram_Centered_Between_Ways"),
            "slider_right_face": planar_intent_selector("ram_with_dovetail_and_tool_mount", *width_selectors["ram_right"], "Ram_Centered_Between_Ways"),
            "travel_stop_face": travel_selectors[0],
            "travel_reference_face": travel_selectors[1],
        },
    })
    consumed.update({"Ram_Centered_Between_Ways", "Ram_Stroke_Limit"})

    add_revolute("bull_gear_on_crank_shaft", "Bull_Gear_Crank_Shaft_Concentric", "Crank_Shaft_Axial_Locator")
    add_revolute("eccentric_pin_in_bull_gear", "Eccentric_Pin_Bull_Gear_Concentric", "Eccentric_Pin_Axial_Locator")
    add_revolute("rocker_pivot_shaft_in_bracket", "Rocker_Pivot_Shaft_Bracket_Concentric", "Rocker_Pivot_Shaft_Axial_Locator")
    add_revolute("rocker_arm_on_pivot_shaft", "Rocker_Arm_Pivot_Shaft_Concentric", "Rocker_Arm_Axial_Locator")
    add_revolute("sliding_die_pin_in_rocker_slot", "Sliding_Die_Rocker_Concentric", "Sliding_Die_Rocker_Slot_Clearance")
    add_revolute("ram_drive_link_to_ram_pin", "Ram_Link_Ram_Concentric", "Ram_Link_Ram_Axial_Locator")

    for name, expected in contract.items():
        if name not in consumed:
            intents.append(direct_shaper_mate_intent(name, expected))

    return {
        "mode": "engineering_mate_intent",
        "document": {"kind": "solidworks_assembly", "name": "bullhead_shaper_complete"},
        "design_intent": {
            "fixture": "complete_bullhead_shaper",
            "assembly_strategy": "human-readable engineering joints expanded by the MCP mate intent executor",
        },
        "mate_intents": intents,
    }


def normalize_intent_executed_mate(row: dict[str, Any], contract: dict[str, dict[str, Any]]) -> dict[str, Any]:
    name = str(row.get("expected_mate_name") or row.get("name") or "")
    expected = contract.get(name, {})
    kind = str(row.get("mate_type") or row.get("kind") or expected.get("type") or "")
    semantic_pair = list(expected.get("semantic_pair", []))
    result = dict(row)
    result["name"] = name
    result["kind"] = kind
    result["semantic_pair"] = semantic_pair
    if "components" not in result or not result["components"]:
        result["components"] = [f"{part_name}-1" for part_name in semantic_pair]
    return result


def mate_selection_evidence_ok(mate: dict[str, Any]) -> bool:
    guard = mate.get("selection_guard", {}) if isinstance(mate, dict) else {}
    expected_count = 4 if mate.get("kind") == "width" else 2
    return (
        int_equals(mate.get("selected_entities"), expected_count)
        and int_equals(guard.get("cleared_selection_count"), 0)
        and guard.get("left_selected") is True
        and guard.get("right_selected") is True
        and int_equals(guard.get("selection_count_before_mate"), expected_count)
    )


def mate_component_evidence_ok(mate: dict[str, Any], semantic_pair: list[str]) -> bool:
    components = mate.get("components") if isinstance(mate, dict) else None
    guard = mate.get("selection_guard", {}) if isinstance(mate, dict) else {}
    component_pair = guard.get("component_pair")
    if not isinstance(components, list) or len(components) < 2:
        return False
    if not isinstance(component_pair, list) or len(component_pair) != len(components):
        return False
    if [str(item) for item in component_pair] != [str(item) for item in components]:
        return False
    return component_pair_matches_semantic_pair(components, semantic_pair)





def build_shaper_assembly_contract() -> dict[str, Any]:
    """Return a reusable offline assembly contract for the retained fixture.

    This mirrors the live fixture gates but uses the generic
    sw_assembly_contract.py schema so an inspect report can be validated without
    rerunning SolidWorks generation. The contract intentionally covers spatial
    placement, semantic mate participation, part feature evidence, and cleanup;
    file creation alone is not acceptance evidence, and this fixture is not a
    claim of full mechanism DOF.
    """
    placement_contract = expected_shaper_placement_contract(tolerance_m=0.004)
    return {
        "document_type": "assembly",
        "minimum_component_count": expected_assembly_component_minimum(),
        "default_origin_tolerance_m": 0.004,
        "components": {
            name: {"required": True, "origin_m": list(contract["expected_origin_m"]), "tolerance_m": contract["tolerance_m"]}
            for name, contract in placement_contract.items()
        },
        "mates": {
            name: {
                "type": expected_inspect_mate_type(expected["type"]),
                "semantic_pair": list(expected["semantic_pair"]),
                "functional_group": expected.get("functional_group"),
            }
            for name, expected in expected_shaper_mate_contract().items()
        },
        "part_features": {
            name: {"required": True, "required_names": list(required_names)}
            for name, required_names in expected_live_feature_names().items()
        },
    }


def validate_semantic_mate_network(mates: Any, contract: dict[str, dict[str, Any]]) -> list[str]:
    """Validate a generic semantic mate network from live mate evidence.

    This is deliberately not shaper-specific: any mechanical fixture can provide a
    contract mapping mate names to expected kind and semantic component pair. The
    live evidence must prove API success, selection isolation, and component
    readback for every required mate.
    """
    failed: list[str] = []
    if not isinstance(mates, list) or not mates:
        return ["mate:missing", "mate_network"]
    mate_by_name = {mate.get("name"): mate for mate in mates if isinstance(mate, dict)}
    missing_contract_mates = sorted(set(contract) - set(mate_by_name))
    if missing_contract_mates:
        failed.append("mate_network")
    for name, expected in contract.items():
        mate = mate_by_name.get(name)
        if not mate:
            continue
        semantic_pair = list(expected["semantic_pair"])
        if not mate.get("ok"):
            failed.append(f"mate:{name}")
        if mate.get("semantic_pair") != semantic_pair:
            failed.append(f"mate_semantics:{name}")
        if mate.get("kind") != expected["type"]:
            failed.append(f"mate_type:{name}")
        if mate.get("mate_error") not in (1, None):
            failed.append(f"mate_error:{name}")
        if not mate_selection_evidence_ok(mate):
            failed.append(f"mate_selection:{name}")
        if not mate_component_evidence_ok(mate, semantic_pair):
            failed.append(f"mate_components:{name}")
    return failed


def expected_shaper_spatial_contract() -> dict[str, list[str]]:
    return {
        "structural_stack": ["cast_bed_with_t_slots", "column_frame_with_window", "table_cross_slide", "work_table_with_t_slots"],
        "workholding_stack": ["table_cross_slide", "work_table_with_t_slots", "vise_jaw_fixed", "vise_jaw_movable"],
        "ram_guidance": ["left_dovetail_way", "right_dovetail_way", "ram_with_dovetail_and_tool_mount", "front_gib_plate", "rear_gib_plate"],
        "tool_head": ["ram_with_dovetail_and_tool_mount", "clapper_tool_head", "single_point_cutting_tool"],
        "quick_return_drive": ["bull_gear_crank_disk", "crank_center_shaft", "eccentric_crank_pin", "ram_drive_link", "bronze_sliding_die_block", "slotted_rocker_arm", "rocker_pivot_shaft"],
    }


def expected_shaper_mate_minimum() -> int:
    return len(expected_shaper_mate_contract())


def component_pair_text_matches_pair(text: str, pair: tuple[str, str]) -> bool:
    return pair[0] in text and pair[1] in text


def spatial_relation_texts(understanding: dict[str, Any]) -> list[str]:
    relation_sources: list[Any] = []
    spatial = ((understanding.get("cad_evidence_graph") or {}).get("spatial_evidence") or {})
    relation_sources.extend(spatial.get("near_or_overlap_pairs") or [])
    spatial_model = understanding.get("spatial_model") or {}
    relation_sources.extend(spatial_model.get("pairwise_relations") or [])
    texts: list[str] = []
    for relation in relation_sources:
        if not isinstance(relation, dict):
            continue
        if str(relation.get("relation", "near")) not in {"near", "overlap", "touching", "contact", "coincident"}:
            continue
        texts.append(f"{relation.get('a')} {relation.get('b')}")
    return texts


def verified_mate_connection_texts(mates: Any) -> list[str]:
    if not isinstance(mates, list):
        return []
    contract = expected_shaper_mate_contract()
    failed = validate_semantic_mate_network(mates, contract)
    if failed:
        return []
    texts = []
    for mate in mates:
        if not isinstance(mate, dict):
            continue
        pair = mate.get("semantic_pair")
        if isinstance(pair, list) and len(pair) == 2:
            texts.append(f"{pair[0]} {pair[1]}")
    return texts


def validate_functional_connection_evidence(understanding: dict[str, Any], mates: Any = None) -> list[str]:
    texts = spatial_relation_texts(understanding) + verified_mate_connection_texts(mates)
    missing = []
    for pair in expected_shaper_functional_connection_contract():
        if not any(component_pair_text_matches_pair(text, pair) for text in texts):
            missing.append(pair)
    return ["model_understanding:functional_connections"] if missing else []


def expected_assembly_component_minimum() -> int:
    return len(placements_for(build_complete_shaper_spec())) + sum(len(v) for v in detail_instance_placements().values())


def expected_shaper_mass_range_kg() -> tuple[float, float]:
    # Mass is a callback sanity signal, not a fixed design parameter. Different
    # successful mate networks can change included/solved body state slightly, so
    # gate on a physically plausible range while preserving the exact measured
    # value in the live report.
    return (10.0, 25.0)


def expected_shaper_mass_kg() -> float:
    low, high = expected_shaper_mass_range_kg()
    return (low + high) / 2


def part_bbox(part: PartSpec, xyz: tuple[float, float, float]) -> tuple[float, float, float, float, float, float]:
    """Return a conservative assembly bbox for the unrotated generated part.

    The SolidWorks construction sketches on Front Plane centered around X/Y and
    extrudes in +Z, so component insertion xyz is the part origin at the center of
    the side-elevation sketch and the front of the extrusion.
    """
    x, y, z = xyz
    sx, sy, sz = (value / 1000 for value in part.size_mm)
    return (x - sx / 2, x + sx / 2, y - sy / 2, y + sy / 2, z, z + sz)


def bbox_intersection_volume(
    left: tuple[float, float, float, float, float, float],
    right: tuple[float, float, float, float, float, float],
) -> float:
    dx = min(left[1], right[1]) - max(left[0], right[0])
    dy = min(left[3], right[3]) - max(left[2], right[2])
    dz = min(left[5], right[5]) - max(left[4], right[4])
    if dx <= 0 or dy <= 0 or dz <= 0:
        return 0.0
    return dx * dy * dz


def intentional_contact(left: dict[str, Any], right: dict[str, Any]) -> bool:
    parts = {left["part"], right["part"]}
    if "fastener_set_m6" in parts or "washer_set" in parts or "oil_cups" in parts:
        return True
    if parts in (
        {"bronze_sliding_die_block", "slotted_rocker_arm"},
        {"table_cross_slide", "work_table_with_t_slots"},
    ):
        return True
    return False


def nominal_component_instances(spec: CompleteShaperSpec) -> list[dict[str, Any]]:
    parts = {part.name: part for part in spec.parts}
    instances: list[dict[str, Any]] = []
    for name, xyz in placements_for(spec).items():
        part = parts[name]
        instances.append({"name": name, "part": name, "xyz": xyz, "bbox": part_bbox(part, xyz), "detail": False})
    for part_name, placements in detail_instance_placements().items():
        part = parts[part_name]
        for index, xyz in enumerate(placements, start=1):
            name = f"{part_name}_detail_{index:02d}"
            instances.append({"name": name, "part": part_name, "xyz": xyz, "bbox": part_bbox(part, xyz), "detail": True})
    return instances


def validate_detail_instance_layout(spec: CompleteShaperSpec, max_detached_gap_m: float = 0.030) -> dict[str, Any]:
    """Reject detail instances parked away from the machine as a display strip."""
    instances = nominal_component_instances(spec)
    machine = [item for item in instances if not item["detail"]]
    details = [item for item in instances if item["detail"]]
    if not machine:
        return {"ok": False, "detached_instances": [item["name"] for item in details], "reason": "no_machine_components"}
    y_min = min(item["bbox"][2] for item in machine)
    y_max = max(item["bbox"][3] for item in machine)
    detached = [
        {"name": item["name"], "xyz": item["xyz"], "machine_y_range_m": [y_min, y_max]}
        for item in details
        if item["xyz"][1] < y_min - max_detached_gap_m or item["xyz"][1] > y_max + max_detached_gap_m
    ]
    return {"ok": not detached, "detached_instances": detached, "max_detached_gap_m": max_detached_gap_m}


def validate_nominal_layout(spec: CompleteShaperSpec) -> dict[str, Any]:
    instances = nominal_component_instances(spec)
    intersections: list[dict[str, Any]] = []
    for index, left in enumerate(instances):
        for right in instances[index + 1:]:
            volume = bbox_intersection_volume(left["bbox"], right["bbox"])
            if volume <= 1e-8:
                continue
            if intentional_contact(left, right):
                continue
            intersections.append({"a": left["name"], "b": right["name"], "volume_m3": volume})
    detail_layout = validate_detail_instance_layout(spec)
    return {
        "ok": not intersections and detail_layout["ok"],
        "component_count": len(instances),
        "intersections": intersections,
        "detail_layout": detail_layout,
        "coordinate_contract": "Front Plane side elevation: X length, Y height, +Z thickness",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="tools/solidworks_codex/live_fixture/shaper_machine_v5")
    parser.add_argument("--reports-dir", default="tools/solidworks_codex/reports/shaper_machine_v5")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--spec-only", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser.parse_args()



# --- Live SolidWorks construction -------------------------------------------------


def solidworks_process_memory_snapshot() -> list[dict[str, Any]]:
    """Return a small SLDWORKS.exe memory snapshot without opening new windows."""
    if not str(Path.cwd().anchor).lower().startswith("c:"):
        return []
    try:
        proc = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-Process SLDWORKS -ErrorAction SilentlyContinue | "
                "Select-Object Id,PrivateMemorySize64,WorkingSet64,Responding,StartTime | ConvertTo-Json -Compress",
            ],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=10,
        )
    except Exception:
        return []
    if proc.returncode != 0 or not proc.stdout.strip():
        return []
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return []
    rows = data if isinstance(data, list) else [data]
    result: list[dict[str, Any]] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        result.append({
            "name": "SLDWORKS",
            "id": row.get("Id"),
            "private_memory_bytes": int(row.get("PrivateMemorySize64") or 0),
            "working_set_bytes": int(row.get("WorkingSet64") or 0),
            "responding": row.get("Responding"),
            "start_time": str(row.get("StartTime")),
        })
    return result


def probe_solidworks_com_attach_only() -> bool:
    _pythoncom, win32_client = require_pywin32()
    win32_client.GetActiveObject("SldWorks.Application")
    return True


def preflight_solidworks_runtime(
    process_snapshots: list[dict[str, Any]] | None = None,
    max_private_memory_bytes: int = 1_900_000_000,
    com_attach_probe: Any | None = None,
    lock_files: list[str] | None = None,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Fail fast instead of building into an already unhealthy SolidWorks session.

    The fixture is intentionally heavy enough to exercise real CAD operations. If an
    existing SLDWORKS.exe is already near the low-memory condition reported by the
    user, continuing would create misleading half-built files and additional UI
    windows. No process is killed here; the report tells the operator to restart SW.
    """
    snapshots = process_snapshots if process_snapshots is not None else solidworks_process_memory_snapshot()
    if lock_files is None:
        scan_dir = out_dir or Path(build_complete_shaper_spec().output_dir)
        lock_files = [path.name for path in scan_dir.glob("~$*")] if scan_dir.exists() else []
    failed: list[str] = []
    if lock_files:
        failed.append("solidworks_stale_lock_files")
    high = [p for p in snapshots if int(p.get("private_memory_bytes", 0) or 0) > max_private_memory_bytes]
    hung = [p for p in snapshots if p.get("responding") is False]
    if high:
        failed.append("solidworks_memory_high")
    if hung:
        failed.append("solidworks_not_responding")
    if snapshots:
        try:
            (com_attach_probe or probe_solidworks_com_attach_only)()
        except Exception as exc:
            failed.append("solidworks_com_unreachable")
            diagnosis = "unhealthy_process_without_com" if high or hung else "responsive_process_without_com"
            return {
                "ok": False,
                "failed": failed,
                "processes": snapshots,
                "lock_files": lock_files,
                "com_error": f"{type(exc).__name__}: {exc}",
                "diagnosis": diagnosis,
                "recommended_action": "restart SolidWorks or close the stale SLDWORKS.exe before running live validation",
            }
    return {"ok": not failed, "failed": failed, "processes": snapshots, "lock_files": lock_files, "out_dir": str(out_dir) if out_dir is not None else None, "max_private_memory_bytes": max_private_memory_bytes}


def assert_solidworks_runtime_healthy(
    stage: str,
    process_snapshots: list[dict[str, Any]] | None = None,
    max_private_memory_bytes: int = 4_800_000_000,
) -> None:
    snapshots = process_snapshots if process_snapshots is not None else solidworks_process_memory_snapshot()
    high = [p for p in snapshots if int(p.get("private_memory_bytes", 0) or 0) > max_private_memory_bytes]
    hung = [p for p in snapshots if p.get("responding") is False]
    if high or hung:
        raise RuntimeError(
            f"SolidWorks unhealthy before {stage}: "
            f"high_memory_pids={[p.get('id') for p in high]} "
            f"not_responding_pids={[p.get('id') for p in hung]}"
        )


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


def attach_solidworks() -> tuple[Any, bool]:
    _pythoncom, win32_client = require_pywin32()
    try:
        sw = win32_client.GetActiveObject("SldWorks.Application")
        started_by_fixture = False
    except Exception:
        sw = win32_client.Dispatch("SldWorks.Application")
        started_by_fixture = True
    try:
        sw.Visible = False
    except Exception:
        pass
    return sw, started_by_fixture


def close_or_exit_solidworks(sw: Any, spec: CompleteShaperSpec, out_dir: Path, started_by_fixture: bool) -> None:
    try:
        close_fixture_documents(sw, spec, out_dir)
    except Exception:
        pass
    if started_by_fixture:
        try:
            sw.ExitApp()
        except Exception:
            pass


def default_template(sw: Any, preference_index: int, label: str) -> str:
    template = sw.GetUserPreferenceStringValue(preference_index)
    if not template:
        raise RuntimeError(f"SolidWorks default {label} template preference {preference_index} is empty")
    return template


def empty_dispatch_variant() -> Any:
    pythoncom, win32_client = require_pywin32()
    return win32_client.VARIANT(pythoncom.VT_DISPATCH, None)


def select_front_plane(model: Any) -> None:
    empty = empty_dispatch_variant()
    if model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, empty, 0):
        return
    feat = read_member(model, "FirstFeature")
    while feat is not None:
        if read_member(feat, "GetTypeName2") == "RefPlane":
            if feat.Select2(False, 0):
                return
        feat = read_member(feat, "GetNextFeature")
    raise RuntimeError("Could not select front/ref plane")


def new_part(sw: Any) -> Any:
    model = sw.NewDocument(default_template(sw, 8, "part"), 0, 0, 0)
    return require_com_created(model, "NewDocument(part)")


def new_assembly(sw: Any) -> Any:
    asm = sw.NewDocument(default_template(sw, 9, "assembly"), 0, 0, 0)
    return require_com_created(asm, "NewDocument(assembly)")



def save_as(model: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    extension_result: Any = None
    try:
        extension_result = model.Extension.SaveAs(str(path.resolve()), 0, 1, empty_dispatch_variant(), errors, warnings)
    except Exception:
        extension_result = None
    if extension_result not in (False, 0, None) and path.exists():
        return
    save_as3_result = read_member(model, "SaveAs3", str(path.resolve()), 0, 2)
    if save_as3_result is False or save_as3_result == 0 or not path.exists():
        raise RuntimeError(
            f"SaveAs failed for {path}; extension_result={extension_result} "
            f"save_as3_result={save_as3_result} errors={getattr(errors, 'value', errors)} "
            f"warnings={getattr(warnings, 'value', warnings)}"
        )


def close_doc(sw: Any, model: Any) -> None:
    try:
        title = read_member(model, "GetTitle")
        if title:
            sw.CloseDoc(title)
    except Exception:
        pass


def com_created(value: Any) -> bool:
    return value not in (None, False, 0)


def require_com_created(value: Any, label: str) -> Any:
    if not com_created(value):
        returned = "None" if value is None else repr(value)
        raise RuntimeError(f"{label} returned {returned}")
    return value


def require_rebuild_success(model: Any, label: str) -> Any:
    result = model.ForceRebuild3(False)
    return require_com_created(result, f"ForceRebuild3 for {label}")


def boss_box(model: Any, width: float, height: float, depth: float, name: str) -> None:
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    rect = model.SketchManager.CreateCornerRectangle(-width / 2, -height / 2, 0, width / 2, height / 2, 0)
    require_com_created(rect, f"CreateCornerRectangle for body {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    require_com_created(feat, f"FeatureExtrusion2 for body {name}")
    feat.Name = name


def boss_cylinder(model: Any, diameter: float, depth: float, name: str) -> None:
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    circle = model.SketchManager.CreateCircleByRadius(0, 0, 0, diameter / 2)
    require_com_created(circle, f"CreateCircleByRadius for body {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    require_com_created(feat, f"FeatureExtrusion2 for body {name}")
    feat.Name = name


def boss_regular_polygon(model: Any, sides: int, radius: float, depth: float, name: str, angle_offset: float = math.pi / 6) -> None:
    if sides < 3:
        raise ValueError("polygon body needs at least three sides")
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    points = [(math.cos(angle_offset + 2 * math.pi * i / sides) * radius, math.sin(angle_offset + 2 * math.pi * i / sides) * radius) for i in range(sides)]
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        line = model.SketchManager.CreateLine(x1, y1, 0, x2, y2, 0)
        require_com_created(line, f"CreateLine for polygon body {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    require_com_created(feat, f"FeatureExtrusion2 for polygon body {name}")
    feat.Name = name


def cut_gear_tooth_spaces(model: Any, teeth: int, root_radius: float, tip_radius: float, depth: float, name: str) -> None:
    if teeth < 8:
        raise ValueError("gear tooth cuts need enough teeth to read visually")
    for index in range(teeth):
        center_angle = (math.pi * 2 * index) / teeth
        flank = math.pi / teeth * 0.36
        points = [
            (math.cos(center_angle - flank) * tip_radius, math.sin(center_angle - flank) * tip_radius),
            (math.cos(center_angle) * root_radius, math.sin(center_angle) * root_radius),
            (math.cos(center_angle + flank) * tip_radius, math.sin(center_angle + flank) * tip_radius),
            (math.cos(center_angle) * tip_radius * 1.10, math.sin(center_angle) * tip_radius * 1.10),
        ]
        cut_polygon(model, points, depth, f"{name}_{index + 1:02d}")


def cut_polygon(model: Any, points: list[tuple[float, float]], depth: float, name: str) -> None:
    if len(points) < 3:
        raise ValueError("cut polygon needs at least three points")
    before = feature_names_by_type(model, "ProfileFeature")
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        line = model.SketchManager.CreateLine(x1, y1, 0, x2, y2, 0)
        require_com_created(line, f"CreateLine for cut {name}")
    model.SketchManager.InsertSketch(True)
    select_new_cut_sketch(model, before)
    create_cut_from_selected_sketch(model, depth, name)


def add_rectangular_boss(model: Any, x: float, y: float, width: float, height: float, depth: float, name: str) -> None:
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    rect = model.SketchManager.CreateCornerRectangle(x - width / 2, y - height / 2, 0, x + width / 2, y + height / 2, 0)
    require_com_created(rect, f"CreateCornerRectangle for boss {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    require_com_created(feat, f"FeatureExtrusion2 for boss {name}")
    feat.Name = name


SKETCH_FEATURE_TYPES = {"ProfileFeature", "3DProfileFeature"}


def feature_names_by_type(model: Any, type_name: str) -> set[str]:
    types = SKETCH_FEATURE_TYPES if type_name == "ProfileFeature" else {type_name}
    names: set[str] = set()
    feat = read_member(model, "FirstFeature")
    while feat is not None:
        if read_member(feat, "GetTypeName2") in types:
            names.add(read_member(feat, "Name"))
        feat = read_member(feat, "GetNextFeature")
    return names


def feature_tree_evidence(model: Any, limit: int = 300) -> list[dict[str, Any]]:
    features: list[dict[str, Any]] = []
    feat = read_member(model, "FirstFeature")
    while feat is not None and len(features) < limit:
        features.append({"name": str(read_member(feat, "Name")), "type": str(read_member(feat, "GetTypeName2"))})
        feat = read_member(feat, "GetNextFeature")
    return features


def find_new_feature_by_type(model: Any, type_name: str, before: set[str]) -> Any:
    types = SKETCH_FEATURE_TYPES if type_name == "ProfileFeature" else {type_name}
    feat = read_member(model, "FirstFeature")
    candidate = None
    last_of_type = None
    while feat is not None:
        if read_member(feat, "GetTypeName2") in types:
            last_of_type = feat
            if read_member(feat, "Name") not in before:
                candidate = feat
        feat = read_member(feat, "GetNextFeature")
    if candidate is not None:
        return candidate
    if last_of_type is not None and len(before) == 0:
        return last_of_type
    raise RuntimeError(f"Could not find newly created {type_name} feature")


def select_new_cut_sketch(model: Any, before: set[str]) -> None:
    sketch = find_new_feature_by_type(model, "ProfileFeature", before)
    model.ClearSelection2(True)
    if not sketch.Select2(False, 0):
        raise RuntimeError(f"Could not select cut sketch {read_member(sketch, 'Name')}")


def create_cut_from_selected_sketch(model: Any, depth: float, name: str) -> None:
    # SolidWorks 2025/Chinese UI returns None if the just-created sketch is not
    # explicitly selected. Direction=True cuts through the +Z body extruded from
    # Front Plane; ThroughAll is avoided so this stays stable for thin detail parts.
    feat = model.FeatureManager.FeatureCut3(True, False, True, 0, 0, depth, depth, False, False, False, False, 0, 0, False, False, False, False, False, True, True, True, True, False, 0, 0, False)
    require_com_created(feat, f"FeatureCut3 for {name}")
    feat.Name = name


def cut_circles_once(model: Any, circles: list[tuple[float, float, float]], depth: float, name: str) -> None:
    before = feature_names_by_type(model, "ProfileFeature")
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    for x, y, r in circles:
        model.SketchManager.CreateCircleByRadius(x, y, 0, r)
    model.SketchManager.InsertSketch(True)
    select_new_cut_sketch(model, before)
    create_cut_from_selected_sketch(model, depth, name)


def cut_circles(model: Any, circles: list[tuple[float, float, float]], depth: float, name: str) -> None:
    try:
        cut_circles_once(model, circles, depth, name)
        return
    except RuntimeError:
        # Multi-contour circular sketches can fail in SolidWorks COM even when each
        # circle is valid. Retry as individual cut features so real bores still exist.
        if len(circles) <= 1:
            raise
    for index, circle in enumerate(circles, start=1):
        cut_circles_once(model, [circle], depth, f"{name}_{index:02d}")


def cut_rects_once(model: Any, rects: list[tuple[float, float, float, float]], depth: float, name: str) -> None:
    before = feature_names_by_type(model, "ProfileFeature")
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    for x, y, w, h in rects:
        if w <= 0.003 or h <= 0.003:
            raise RuntimeError(f"Rectangle cut {name} is too small to create robustly: {w} x {h} m")
        rect = model.SketchManager.CreateCornerRectangle(x - w / 2, y - h / 2, 0, x + w / 2, y + h / 2, 0)
        require_com_created(rect, f"CreateCornerRectangle for {name}: {w} x {h} m")
    model.SketchManager.InsertSketch(True)
    select_new_cut_sketch(model, before)
    create_cut_from_selected_sketch(model, depth, name)


def cut_rects(model: Any, rects: list[tuple[float, float, float, float]], depth: float, name: str) -> None:
    try:
        cut_rects_once(model, rects, depth, name)
        return
    except RuntimeError:
        model.ClearSelection2(True)
        try:
            model.SketchManager.InsertSketch(False)
        except Exception:
            pass
        if len(rects) <= 1:
            raise
    for index, rect in enumerate(rects, start=1):
        cut_rects_once(model, [rect], depth, f"{name}_{index:02d}")


def hole_pattern(count: int, span_x: float, y: float, radius: float) -> list[tuple[float, float, float]]:
    if count <= 1:
        return [(0, y, radius)]
    return [(-span_x / 2 + i * span_x / (count - 1), y, radius) for i in range(count)]


def circular_pattern(count: int, pcd: float, radius: float, offset_angle: float = 0.0) -> list[tuple[float, float, float]]:
    return [(math.cos(offset_angle + 2 * math.pi * i / count) * pcd / 2, math.sin(offset_angle + 2 * math.pi * i / count) * pcd / 2, radius) for i in range(count)]


def create_part(sw: Any, out_dir: Path, part: PartSpec) -> Path:
    return create_part_with_feature_evidence(sw, out_dir, part)[0]


def create_part_with_feature_evidence(sw: Any, out_dir: Path, part: PartSpec) -> tuple[Path, dict[str, Any]]:
    path = out_dir / f"{part.name}.SLDPRT"
    model = new_part(sw)
    try:
        w, h, d = (v / 1000 for v in part.size_mm)
        if part.kind == "fasteners":
            boss_regular_polygon(model, 6, max(w, h) / 2, d, f"Hex_Body_{part.name}")
        elif part.kind in {"crank_disk", "pin", "shaft", "washers", "details"}:
            boss_cylinder(model, max(w, h), d, f"Body_{part.name}")
        else:
            boss_box(model, w, h, d, f"Body_{part.name}")
        depth = max(d * 1.6, 0.012)
        name = part.name
        if name == "cast_bed_with_t_slots":
            cut_rects(model, [(0, yy, w * 0.82, h * 0.045) for yy in (-h * .28, 0, h * .28)], depth, "T_Slot_Cuts")
            cut_circles(model, hole_pattern(3, w * .78, -h * .42, 0.008) + hole_pattern(3, w * .78, h * .42, 0.008), depth, "Floor_Mounting_Holes")
            for i, x in enumerate([-w*.34, -w*.17, 0, w*.17, w*.34]):
                add_rectangular_boss(model, x, 0, 0.012, h * .96, d * .35, f"Web_Rib_{i+1}")
        elif name == "column_frame_with_window":
            cut_rects(model, [(0, 0, w * .52, h * .56)], depth, "Frame_Window_Cut")
            cut_circles(model, [(0, h*.30, 0.020), (0, -h*.30, 0.016)] + hole_pattern(4, w*.72, h*.43, 0.004) + hole_pattern(4, w*.72, -h*.43, 0.004), depth, "Bearing_Bores_And_Cover_Holes")
        elif name == "ram_with_dovetail_and_tool_mount":
            cut_rects(model, [(0, -h*.42, w*.82, h*.08), (0, h*.42, w*.82, h*.08)], depth, "Dovetail_And_Oil_Groove_Cuts")
            cut_polygon(model, [(-w*.42, -h*.50), (w*.42, -h*.50), (w*.34, -h*.38), (-w*.34, -h*.38)], depth, "Angled_Dovetail_Underside_Cut")
            cut_circles(model, hole_pattern(3, w*.42, h*.20, 0.004) + hole_pattern(3, w*.42, -h*.20, 0.004), depth, "Tool_Mount_Bolt_Holes")
        elif name == "clapper_tool_head":
            cut_rects(model, [(0, 0, w*.28, h*.78)], depth, "Vertical_Tool_Slot")
            cut_circles(model, hole_pattern(2, w*.55, h*.35, 0.004) + hole_pattern(2, w*.55, -h*.35, 0.004) + [(0, 0, 0.009)], depth, "Clapper_Bolt_And_Pivot_Holes")
        elif name == "single_point_cutting_tool":
            cut_polygon(model, [(w*.12, -h*.50), (w*.50, -h*.50), (w*.50, h*.18)], depth, "Beveled_Cutting_Tip")
        elif name == "bull_gear_crank_disk":
            cut_gear_tooth_spaces(model, 32, max(w, h) * 0.43, max(w, h) * 0.53, depth, "Gear_Tooth_Profile")
            cut_circles(model, [(0, 0, 0.018), (w*.23, 0, 0.010)] + circular_pattern(6, w*.58, 0.009, math.pi/6), depth, "Center_Eccentric_And_Lightening_Holes")
        elif name == "slotted_rocker_arm":
            cut_rects(model, [(0, 0, w*.25, h*.72)], depth, "Long_Sliding_Slot")
            cut_circles(model, [(0, -h*.40, 0.010), (0, h*.40, 0.010)], depth, "Rocker_Pin_Bores")
        elif name == "bronze_sliding_die_block":
            cut_circles(model, [(0, 0, 0.011)], depth, "Cross_Pin_Bore")
            cut_rects(model, [(0, h*.30, w*.70, max(h*.12, 0.004))], depth, "Oil_Groove")
        elif name == "rocker_pivot_bracket":
            cut_rects(model, [(0, 0, w*.34, h*.72)], depth, "Fork_Relief_Slot")
            cut_circles(model, [(0, 0, 0.014)] + hole_pattern(2, w*.60, h*.38, 0.004) + hole_pattern(2, w*.60, -h*.38, 0.004), depth, "Pivot_And_Base_Bolt_Holes")
        elif name == "ram_drive_link":
            cut_circles(model, [(0, -h*.38, 0.011), (0, h*.38, 0.011)], depth, "Link_Eye_Bores")
        elif name in {"left_dovetail_way", "right_dovetail_way"}:
            cut_rects(model, [(0, 0, w*.30, max(h*.20, 0.004))], depth, "Dovetail_Relief")
            cut_polygon(model, [(-w*.50, -h*.50), (-w*.35, -h*.50), (-w*.45, h*.50)], depth, "Left_Angled_Dovetail_Flank")
            cut_polygon(model, [(w*.35, -h*.50), (w*.50, -h*.50), (w*.45, h*.50)], depth, "Right_Angled_Dovetail_Flank")
            cut_circles(model, hole_pattern(6, w*.82, 0, 0.0035), depth, "Rail_Screw_Holes")
        elif name in {"front_gib_plate", "rear_gib_plate"}:
            cut_circles(model, hole_pattern(5, w*.80, 0, 0.003), depth, "Gib_Adjuster_Holes")
        elif name == "table_cross_slide":
            cut_rects(model, [(0, -h*.24, w*.75, max(h*.055, 0.004)), (0, h*.24, w*.75, max(h*.055, 0.004)), (0, 0, w*.65, max(h*.08, 0.004))], depth, "Cross_Slide_T_And_Dovetail_Cuts")
            cut_circles(model, hole_pattern(4, w*.62, 0, 0.004), depth, "Cross_Slide_Holes")
        elif name == "work_table_with_t_slots":
            cut_rects(model, [(0, yy, w*.82, max(h*.045, 0.004)) for yy in (-h*.33, -h*.11, h*.11, h*.33)], depth, "Work_Table_T_Slots")
            cut_circles(model, hole_pattern(2, w*.70, h*.43, 0.004) + hole_pattern(2, w*.70, -h*.43, 0.004), depth, "Table_Mount_Holes")
        elif name in {"vise_jaw_fixed", "vise_jaw_movable"}:
            cut_circles(model, hole_pattern(2, w*.55, 0, 0.004), depth, "Jaw_Screw_Holes")
            cut_rects(model, [(x, h*.35, max(w*.05, 0.004), max(h*.16, 0.004)) for x in (-w*.30, -w*.15, 0, w*.15, w*.30)], depth, "Jaw_Serrations")
        elif name == "fastener_set_m6":
            cut_circles(model, [(0, 0, min(w, h) * .18)], depth, "Hex_Socket_Drive")
        elif name == "washer_set":
            cut_circles(model, [(0, 0, max(w, h)*.22)], depth, "Washer_Center_Hole")
        elif name == "oil_cups":
            cut_circles(model, [(0, 0, max(w, h)*.18)], depth, "Oil_Cup_Bore")
        require_rebuild_success(model, f"part {part.name}")
        evidence = {"ok": True, "part": part.name, "features": feature_tree_evidence(model)}
        save_as(model, path)
        return path, evidence
    finally:
        close_doc(sw, model)

def close_fixture_documents(sw: Any, spec: CompleteShaperSpec, out_dir: Path) -> None:
    titles = ["bullhead_shaper_complete.SLDASM", "bullhead_shaper_complete"]
    titles.extend(f"{part.name}.SLDPRT" for part in spec.parts)
    titles.extend(part.name for part in spec.parts)
    for title in titles:
        try:
            sw.CloseDoc(title)
        except Exception:
            pass


def cleanup_dir(path: Path, force: bool) -> list[str]:
    skipped: list[str] = []
    if not force or not path.exists():
        return skipped
    for child in path.glob("*"):
        if child.is_file():
            try:
                child.unlink()
            except PermissionError:
                skipped.append(child.name)
    return skipped


def probe_unlocked_generated_files(path: Path) -> dict[str, Any]:
    checked_files: list[str] = []
    locked_files: list[str] = []
    lock_files: list[str] = []
    if not path.exists():
        return {"checked_files": checked_files, "locked_files": locked_files, "lock_files": lock_files, "probe": "rename_round_trip"}
    for child in sorted(path.glob("*")):
        if child.is_file() and child.name.startswith("~$"):
            lock_files.append(child.name)
            continue
        if not child.is_file():
            continue
        checked_files.append(child.name)
        probe = child.with_name(child.name + ".lockprobe")
        try:
            child.rename(probe)
            probe.rename(child)
        except OSError:
            locked_files.append(child.name)
            if probe.exists() and not child.exists():
                try:
                    probe.rename(child)
                except OSError:
                    pass
    return {"checked_files": checked_files, "locked_files": locked_files, "lock_files": lock_files, "probe": "rename_round_trip"}


def wait_for_generated_files_unlocked(
    path: Path,
    probe: Any = probe_unlocked_generated_files,
    sleep: Any = time.sleep,
    attempts: int = 5,
    delay_seconds: float = 0.75,
) -> dict[str, Any]:
    """Poll generated files after CloseDoc/ExitApp until SW releases handles."""
    last: dict[str, Any] = {}
    for attempt in range(1, max(1, attempts) + 1):
        last = probe(path)
        last["attempts"] = attempt
        if not last.get("locked_files") and not last.get("lock_files"):
            return last
        if attempt < attempts:
            sleep(delay_seconds)
    return last


def open_part_for_insert(sw: Any, path: Path) -> Any:
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(str(path.resolve()), 1, 1, "", errors, warnings)
    if not com_created(model):
        returned = "None" if model is None else repr(model)
        raise RuntimeError(f"OpenDoc6 failed for {path}; errors={getattr(errors, 'value', errors)} warnings={getattr(warnings, 'value', warnings)}")
    return model


def activate_assembly(sw: Any, asm: Any) -> None:
    try:
        title = read_member(asm, "GetTitle")
        if title:
            pythoncom, win32_client = require_pywin32()
            errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            sw.ActivateDoc3(title, False, 0, errors)
    except Exception:
        pass


def add_component(sw: Any, asm: Any, path: Path, xyz: tuple[float, float, float]) -> Any:
    resolved = str(path.resolve())
    activate_assembly(sw, asm)
    comp = asm.AddComponent5(resolved, 0, "", False, "", xyz[0], xyz[1], xyz[2])
    if com_created(comp):
        return comp
    opened = open_part_for_insert(sw, path)
    try:
        activate_assembly(sw, asm)
        comp = asm.AddComponent5(resolved, 0, "", False, "", xyz[0], xyz[1], xyz[2])
    finally:
        close_doc(sw, opened)
    require_com_created(comp, f"AddComponent5 for {path}")
    return comp


def byref_i4(value: int = 0) -> Any:
    pythoncom, win32_client = require_pywin32()
    return win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, value)


def component_faces(component: Any, limit: int = 2048) -> list[Any]:
    faces: list[Any] = []
    try:
        bodies = component.GetBodies2(0)
    except Exception:
        bodies = None
    if not bodies:
        return faces
    for body in bodies:
        face = body.GetFirstFace()
        seen: set[int] = set()
        while face is not None and len(faces) < limit and id(face) not in seen:
            seen.add(id(face))
            faces.append(face)
            face = read_member(face, "GetNextFace")
    return faces


def face_plane_normal(face: Any) -> tuple[float, float, float] | None:
    try:
        surface = read_member(face, "GetSurface")
        if not bool(read_member(surface, "IsPlane")):
            return None
        params = read_member(surface, "PlaneParams")
        if not params or len(params) < 6:
            return None
        return normalize_vector((float(params[0]), float(params[1]), float(params[2])))
    except Exception:
        return None


def face_plane_offset(face: Any, normal: tuple[float, float, float]) -> float | None:
    """Return a comparable plane offset for choosing intentional distance mates.

    SolidWorks face iteration order is not stable enough for engineering mates.
    For generated planar faces we can use the planar surface point/normal form to
    estimate distance between parallel faces and pick the pair already near the
    requested mate clearance instead of the first arbitrary parallel pair.
    """
    try:
        surface = read_member(face, "GetSurface")
        params = read_member(surface, "PlaneParams")
        if params and len(params) >= 6:
            point = (float(params[3]), float(params[4]), float(params[5]))
            return normal[0] * point[0] + normal[1] * point[1] + normal[2] * point[2]
        box = read_member(face, "GetBox")
        if box and len(box) >= 6:
            center = ((float(box[0]) + float(box[3])) / 2, (float(box[1]) + float(box[4])) / 2, (float(box[2]) + float(box[5])) / 2)
            return normal[0] * center[0] + normal[1] * center[1] + normal[2] * center[2]
    except Exception:
        return None
    return None


def component_translation(component: Any) -> tuple[float, float, float]:
    try:
        transform = read_member(component, "Transform2")
        data = list(read_member(transform, "ArrayData")) if transform is not None else []
        if len(data) >= 12:
            return (float(data[9]), float(data[10]), float(data[11]))
    except Exception:
        pass
    return (0.0, 0.0, 0.0)


def component_face_plane_offset(component: Any, face: Any, normal: tuple[float, float, float]) -> float | None:
    offset = face_plane_offset(face, normal)
    if offset is None:
        return None
    translation = component_translation(component)
    return offset + normal[0] * translation[0] + normal[1] * translation[1] + normal[2] * translation[2]


def axis_vector(axis: str) -> tuple[float, float, float]:
    return {
        "x": (1.0, 0.0, 0.0),
        "y": (0.0, 1.0, 0.0),
        "z": (0.0, 0.0, 1.0),
    }[axis]


def explicit_planar_interface_face(component: Any, axis: str, side: str) -> Any | None:
    """Select a designed interface face by component axis and side.

    This is the fixture equivalent of a human engineer selecting the known
    mounting face / datum side / guide face. It deliberately does not rank
    arbitrary nearby faces between components.
    """
    normal_hint = axis_vector(axis)
    candidates: list[tuple[float, Any]] = []
    for face in component_faces(component):
        normal = face_plane_normal(face)
        if normal is None or not normal_matches_hint(normal, normal_hint):
            continue
        offset = component_face_plane_offset(component, face, normal_hint)
        if offset is None:
            continue
        candidates.append((offset, face))
    if not candidates:
        return None
    return (max if side == "max" else min)(candidates, key=lambda item: item[0])[1]


def shaper_planar_interface_selector(name: str, semantic_pair: list[str]) -> tuple[tuple[str, str], tuple[str, str]]:
    """Explicit engineering interface map for each planar shaper mate.

    Values are (axis, side) selectors in each component's authored coordinate
    system. This keeps assembly intent reviewable: bed top to column bottom,
    ram underside to way tops, table bottom to slide top, etc.
    """
    selectors = {
        "Bed_Column_Parallel": (("z", "max"), ("z", "min")),
        "Bed_Column_Contact": (("z", "max"), ("z", "min")),
        "Column_Bed_Setback": (("x", "min"), ("x", "max")),
        "Column_Bed_Perpendicular": (("x", "max"), ("z", "max")),
        "Left_Way_Column_Parallel": (("z", "min"), ("z", "max")),
        "Left_Way_Column_Contact": (("z", "min"), ("z", "max")),
        "Right_Way_Column_Parallel": (("z", "min"), ("z", "max")),
        "Right_Way_Column_Contact": (("z", "min"), ("z", "max")),
        "Way_Spacing_Distance": (("z", "max"), ("z", "min")),
        "Ram_Left_Way_Parallel": (("z", "min"), ("z", "max")),
        "Ram_LeftWay_Guidance_Distance_Mate": (("z", "min"), ("z", "max")),
        "Ram_Right_Way_Parallel": (("z", "min"), ("z", "max")),
        "Ram_Stroke_Limit": (("x", "min"), ("x", "max")),
        "Front_Gib_Ram_Parallel": (("z", "min"), ("z", "max")),
        "Front_Gib_Ram_Clearance": (("z", "min"), ("z", "max")),
        "Rear_Gib_Ram_Parallel": (("z", "min"), ("z", "max")),
        "Rear_Gib_Ram_Clearance": (("z", "min"), ("z", "max")),
        "Tool_Head_Ram_Parallel": (("x", "min"), ("x", "max")),
        "Tool_Head_Ram_Contact": (("x", "min"), ("x", "max")),
        "Tool_Tool_Head_Parallel": (("z", "min"), ("z", "max")),
        "Tool_Tool_Head_Contact": (("z", "min"), ("z", "max")),
        "Table_Slide_Parallel": (("y", "min"), ("y", "max")),
        "Table_Slide_Contact": (("y", "min"), ("y", "max")),
        "Slide_Bed_Parallel": (("z", "min"), ("z", "max")),
        "Slide_Bed_Contact": (("z", "min"), ("z", "max")),
        "Fixed_Jaw_Table_Parallel": (("y", "min"), ("y", "max")),
        "Fixed_Jaw_Table_Contact": (("y", "min"), ("y", "max")),
        "Movable_Jaw_Table_Parallel": (("y", "min"), ("y", "max")),
        "Movable_Jaw_Table_Clearance": (("x", "min"), ("x", "max")),
        "Crank_Shaft_Axial_Locator": (("z", "min"), ("z", "max")),
        "Crank_Reference_Angle": (("x", "max"), ("x", "min")),
        "Eccentric_Pin_Axial_Locator": (("z", "min"), ("z", "max")),
        "Rocker_Pivot_Shaft_Axial_Locator": (("z", "min"), ("z", "max")),
        "Rocker_Arm_Axial_Locator": (("z", "min"), ("z", "max")),
        "Sliding_Die_Rocker_Slot_Clearance": (("z", "min"), ("z", "max")),
        "Ram_Link_Ram_Axial_Locator": (("z", "min"), ("z", "max")),
    }
    return selectors.get(name, (("z", "max"), ("z", "min")))


def shaper_width_interface_selector(name: str) -> dict[str, tuple[str, str]]:
    """Explicit four-face interface map for centered width mates.

    A width mate is not a cosmetic spacing mate. For the ram guide it represents
    the human-selected opposing guideway cheeks and the two ram side cheeks that
    center the sliding member laterally between the ways.
    """
    selectors = {
        "Ram_Centered_Between_Ways": {
            "left_way": ("z", "max"),
            "right_way": ("z", "min"),
            "ram_left": ("z", "min"),
            "ram_right": ("z", "max"),
        }
    }
    return selectors[name]


def explicit_planar_face_pair(left: Any, right: Any, name: str, semantic_pair: list[str]) -> tuple[Any, Any, float] | None:
    left_selector, right_selector = shaper_planar_interface_selector(name, semantic_pair)
    left_face = explicit_planar_interface_face(left, left_selector[0], left_selector[1])
    right_face = explicit_planar_interface_face(right, right_selector[0], right_selector[1])
    if left_face is None or right_face is None:
        return None
    normal = axis_vector(left_selector[0])
    left_offset = component_face_plane_offset(left, left_face, normal)
    right_offset = component_face_plane_offset(right, right_face, normal)
    actual_distance = abs((left_offset or 0.0) - (right_offset or 0.0))
    return left_face, right_face, actual_distance


def normals_parallel(a: tuple[float, float, float], b: tuple[float, float, float]) -> bool:
    return abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) > 0.99


def normal_matches_hint(normal: tuple[float, float, float], hint: tuple[float, float, float] | None) -> bool:
    if hint is None:
        return True
    return abs(normal[0] * hint[0] + normal[1] * hint[1] + normal[2] * hint[2]) > 0.97


def planar_mate_normal_hint(name: str) -> tuple[float, float, float] | None:
    """Declared interface axis for each planar mate in the shaper contract."""
    x_axis = (1.0, 0.0, 0.0)
    y_axis = (0.0, 1.0, 0.0)
    z_axis = (0.0, 0.0, 1.0)
    hints = {
        "Bed_Column_Parallel": z_axis,
        "Bed_Column_Contact": z_axis,
        "Column_Bed_Setback": x_axis,
        "Column_Bed_Perpendicular": x_axis,
        "Left_Way_Column_Parallel": z_axis,
        "Left_Way_Column_Contact": z_axis,
        "Right_Way_Column_Parallel": z_axis,
        "Right_Way_Column_Contact": z_axis,
        "Way_Spacing_Distance": z_axis,
        "Ram_Left_Way_Parallel": z_axis,
        "Ram_LeftWay_Guidance_Distance_Mate": z_axis,
        "Ram_Right_Way_Parallel": z_axis,
        "Ram_Stroke_Limit": x_axis,
        "Front_Gib_Ram_Parallel": z_axis,
        "Front_Gib_Ram_Clearance": z_axis,
        "Rear_Gib_Ram_Parallel": z_axis,
        "Rear_Gib_Ram_Clearance": z_axis,
        "Tool_Head_Ram_Parallel": x_axis,
        "Tool_Head_Ram_Contact": x_axis,
        "Tool_Tool_Head_Parallel": z_axis,
        "Tool_Tool_Head_Contact": z_axis,
        "Table_Slide_Parallel": y_axis,
        "Table_Slide_Contact": y_axis,
        "Slide_Bed_Parallel": z_axis,
        "Slide_Bed_Contact": z_axis,
        "Fixed_Jaw_Table_Parallel": y_axis,
        "Fixed_Jaw_Table_Contact": y_axis,
        "Movable_Jaw_Table_Parallel": y_axis,
        "Movable_Jaw_Table_Clearance": x_axis,
        "Crank_Shaft_Axial_Locator": z_axis,
        "Crank_Reference_Angle": x_axis,
        "Eccentric_Pin_Axial_Locator": z_axis,
        "Rocker_Pivot_Shaft_Axial_Locator": z_axis,
        "Rocker_Arm_Axial_Locator": z_axis,
        "Sliding_Die_Rocker_Slot_Clearance": z_axis,
        "Ram_Link_Ram_Axial_Locator": z_axis,
    }
    return hints.get(name)


def select_faces(asm: Any, first: Any, second: Any, component_pair: list[str] | None = None) -> dict[str, Any]:
    asm.ClearSelection2(True)
    cleared_count = int(asm.SelectionManager.GetSelectedObjectCount2(-1))
    empty = empty_dispatch_variant()
    left_selected = bool(first.Select4(False, empty))
    right_selected = bool(second.Select4(True, empty))
    selected_count = int(asm.SelectionManager.GetSelectedObjectCount2(-1))
    return {
        "cleared_selection_count": cleared_count,
        "left_selected": left_selected,
        "right_selected": right_selected,
        "selection_count_before_mate": selected_count,
        "component_pair": component_pair or [],
    }


def select_data_with_mark(asm: Any, mark: int) -> Any:
    try:
        manager = read_member(asm, "SelectionManager")
        create_select_data = getattr(manager, "CreateSelectData", None)
        if callable(create_select_data):
            data = create_select_data()
            try:
                data.Mark = int(mark)
            except Exception:
                pass
            return data
    except Exception:
        pass
    return empty_dispatch_variant()


def select_face_with_mark(face: Any, append: bool, asm: Any, mark: int) -> bool:
    select_data = select_data_with_mark(asm, mark)
    try:
        return bool(face.Select4(bool(append), select_data))
    except TypeError:
        return bool(face.Select4(bool(append), select_data, mark))


def add_selected_mate(
    asm: Any,
    name: str,
    mate_type: int,
    distance: float = 0.0,
    distance_min: float | None = None,
    distance_max: float | None = None,
    angle: float = 0.0,
    angle_min: float | None = None,
    angle_max: float | None = None,
) -> dict[str, Any]:
    mate_error = byref_i4(0)
    try:
        feat = asm.AddMate5(
            mate_type,
            -1,
            False,
            distance,
            distance_max if distance_max is not None else distance,
            distance_min if distance_min is not None else distance,
            0,
            0,
            angle,
            angle_max if angle_max is not None else angle,
            angle_min if angle_min is not None else angle,
            0,
            False,
            False,
            mate_error,
        )
        if com_created(feat):
            feat.Name = name
            return {"name": name, "ok": True, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None)}
        returned = "None" if feat is None else repr(feat)
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None), "error": f"AddMate5 returned {returned}"}
    except Exception as exc:
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None), "error": repr(exc)}


def best_parallel_planar_face_pair(
    left: Any,
    right: Any,
    distance: float,
    normal_hint: tuple[float, float, float] | None = None,
) -> tuple[Any, Any, float] | None:
    candidates: list[tuple[float, Any, Any, float]] = []
    left_faces = [(face, face_plane_normal(face)) for face in component_faces(left)]
    left_faces = [(face, normal) for face, normal in left_faces if normal is not None]
    right_faces = [(face, face_plane_normal(face)) for face in component_faces(right)]
    right_faces = [(face, normal) for face, normal in right_faces if normal is not None]
    for left_face, left_normal in left_faces:
        if not normal_matches_hint(left_normal, normal_hint):
            continue
        left_offset = component_face_plane_offset(left, left_face, left_normal)
        if left_offset is None:
            continue
        for right_face, right_normal in right_faces:
            if not normals_parallel(left_normal, right_normal):
                continue
            right_offset = component_face_plane_offset(right, right_face, left_normal)
            if right_offset is None:
                continue
            actual_distance = abs(left_offset - right_offset)
            candidates.append((abs(actual_distance - distance), left_face, right_face, actual_distance))
    if not candidates:
        return None
    _, left_face, right_face, actual_distance = min(candidates, key=lambda item: item[0])
    return left_face, right_face, actual_distance


def add_distance_mate_between_planar_faces(asm: Any, components: list[Any], distance: float, name: str = "Shaper_Distance_Mate") -> dict[str, Any]:
    for i, left in enumerate(components):
        for right in components[i + 1:]:
            semantic_pair = [str(getattr(left, "Name2", "")).split("-")[0], str(getattr(right, "Name2", "")).split("-")[0]]
            best = explicit_planar_face_pair(left, right, name, semantic_pair)
            if best is None:
                continue
            left_face, right_face, actual_distance = best
            component_pair = [left.Name2, right.Name2]
            selection_guard = select_faces(asm, left_face, right_face, component_pair)
            if int(selection_guard["selection_count_before_mate"]) >= 2:
                # Preserve the already-authored assembly layout. The requested
                # distance is only a selector hint for choosing a sensible planar
                # face pair; forcing every semantic mate to an arbitrary display
                # clearance can tear a recognizable mechanism apart.
                mate_distance = actual_distance
                result = add_selected_mate(asm, name, 5, mate_distance)
                result["selected_entities"] = selection_guard["selection_count_before_mate"]
                result["selection_guard"] = selection_guard
                result["components"] = component_pair
                result["requested_selector_distance_m"] = distance
                result["face_pair_actual_distance_m"] = actual_distance
                result["preserved_layout_distance_m"] = mate_distance
                return result
    return {"name": name, "ok": False, "error": "no planar face pair accepted by AddMate5"}


def component_name_starts(component: Any, prefix: str) -> bool:
    return str(getattr(component, "Name2", "")).startswith(prefix)


def component_by_part_name(components: list[Any], part_name: str) -> Any | None:
    return next((component for component in components if component_name_starts(component, f"{part_name}-")), None)


def add_semantic_distance_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str], distance: float) -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": "distance", "semantic_pair": semantic_pair, "error": "component missing"}
    result = add_distance_mate_between_planar_faces(asm, [left, right], distance, name)
    result["kind"] = "distance"
    result["semantic_pair"] = semantic_pair
    return result


def add_semantic_limit_distance_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str]) -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": "limit_distance", "semantic_pair": semantic_pair, "error": "component missing"}
    nominal = shaper_distance_mate_clearance(name)
    best = explicit_planar_face_pair(left, right, name, semantic_pair)
    if best is None:
        return {"name": name, "ok": False, "kind": "limit_distance", "semantic_pair": semantic_pair, "error": "parallel planar face missing"}
    left_face, right_face, actual_distance = best
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_faces(asm, left_face, right_face, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {"name": name, "ok": False, "kind": "limit_distance", "semantic_pair": semantic_pair, "selected_entities": selected, "selection_guard": selection_guard, "components": component_pair, "error": "planar faces not selected"}
    limit_min, limit_max = shaper_limit_distance_bounds(name)
    result = add_selected_mate(
        asm,
        name,
        5,
        nominal,
        distance_min=limit_min,
        distance_max=limit_max,
    )
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["requested_selector_distance_m"] = nominal
    result["face_pair_actual_distance_m"] = actual_distance
    result["limit_distance_range_m"] = [limit_min, limit_max]
    result["kind"] = "limit_distance"
    result["semantic_pair"] = semantic_pair
    return result


def add_semantic_coincident_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str]) -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": "coincident", "semantic_pair": semantic_pair, "error": "component missing"}
    best = explicit_planar_face_pair(left, right, name, semantic_pair)
    if best is None:
        return {"name": name, "ok": False, "kind": "coincident", "semantic_pair": semantic_pair, "error": "parallel planar face missing"}
    left_face, right_face, actual_distance = best
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_faces(asm, left_face, right_face, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {
            "name": name,
            "ok": False,
            "kind": "coincident",
            "semantic_pair": semantic_pair,
            "selected_entities": selected,
            "selection_guard": selection_guard,
            "components": component_pair,
            "error": "planar faces not selected",
        }
    result = add_selected_mate(asm, name, 0, 0.0)
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["face_pair_actual_distance_m"] = actual_distance
    result["kind"] = "coincident"
    result["semantic_pair"] = semantic_pair
    return result


def add_semantic_perpendicular_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str]) -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": "perpendicular", "semantic_pair": semantic_pair, "error": "component missing"}
    left_hint = planar_mate_normal_hint(name)
    right_hint = (0.0, 0.0, 1.0) if left_hint == (1.0, 0.0, 0.0) else (1.0, 0.0, 0.0)
    left_faces = [(face, face_plane_normal(face)) for face in component_faces(left)]
    right_faces = [(face, face_plane_normal(face)) for face in component_faces(right)]
    candidates: list[tuple[float, Any, Any]] = []
    for left_face, left_normal in left_faces:
        if left_normal is None or not normal_matches_hint(left_normal, left_hint):
            continue
        for right_face, right_normal in right_faces:
            if right_normal is None or not normal_matches_hint(right_normal, right_hint):
                continue
            dot = abs(left_normal[0] * right_normal[0] + left_normal[1] * right_normal[1] + left_normal[2] * right_normal[2])
            candidates.append((dot, left_face, right_face))
    if not candidates:
        return {"name": name, "ok": False, "kind": "perpendicular", "semantic_pair": semantic_pair, "error": "perpendicular planar face pair missing"}
    _dot, left_face, right_face = min(candidates, key=lambda item: item[0])
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_faces(asm, left_face, right_face, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {"name": name, "ok": False, "kind": "perpendicular", "semantic_pair": semantic_pair, "selected_entities": selected, "selection_guard": selection_guard, "components": component_pair, "error": "planar faces not selected"}
    result = add_selected_mate(asm, name, 2, 0.0)
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["kind"] = "perpendicular"
    result["semantic_pair"] = semantic_pair
    return result


def add_semantic_parallel_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str]) -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": "parallel", "semantic_pair": semantic_pair, "error": "component missing"}
    best = explicit_planar_face_pair(left, right, name, semantic_pair)
    if best is None:
        return {"name": name, "ok": False, "kind": "parallel", "semantic_pair": semantic_pair, "error": "parallel planar face missing"}
    left_face, right_face, actual_distance = best
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_faces(asm, left_face, right_face, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {
            "name": name,
            "ok": False,
            "kind": "parallel",
            "semantic_pair": semantic_pair,
            "selected_entities": selected,
            "selection_guard": selection_guard,
            "components": component_pair,
            "error": "planar faces not selected",
        }
    # swMatePARALLEL = 3. This constrains planar interface orientation without
    # collapsing intentionally spaced guide/table/tool components into collision.
    result = add_selected_mate(asm, name, 3, 0.0)
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["face_pair_actual_distance_m"] = actual_distance
    result["kind"] = "parallel"
    result["semantic_pair"] = semantic_pair
    return result


def face_surface_is(face: Any, predicate: str) -> bool:
    try:
        surface = read_member(face, "GetSurface")
        return bool(read_member(surface, predicate))
    except Exception:
        return False


def face_cylinder_axis(face: Any) -> tuple[tuple[float, float, float], tuple[float, float, float], float] | None:
    """Return approximate cylinder axis point, direction, and radius.

    SolidWorks exposes cylinder parameters differently across COM wrappers. This
    helper uses CylinderParams when available and falls back to the face bbox
    center with a neutral Z axis so the mate selector still has deterministic
    evidence instead of taking the first cylindrical face.
    """
    try:
        surface = read_member(face, "GetSurface")
        if not bool(read_member(surface, "IsCylinder")):
            return None
        params = None
        for attr in ("CylinderParams", "CylinderParam"):
            try:
                params = read_member(surface, attr)
                if params:
                    break
            except Exception:
                params = None
        if params and len(params) >= 7:
            point = (float(params[0]), float(params[1]), float(params[2]))
            direction = normalize_vector((float(params[3]), float(params[4]), float(params[5])))
            radius = abs(float(params[6]))
            return point, direction, radius
        box = read_member(face, "GetBox")
        if box and len(box) >= 6:
            center = ((float(box[0]) + float(box[3])) / 2, (float(box[1]) + float(box[4])) / 2, (float(box[2]) + float(box[5])) / 2)
            radius = max(float(box[3]) - float(box[0]), float(box[4]) - float(box[1]), float(box[5]) - float(box[2])) / 2
            return center, (0.0, 0.0, 1.0), abs(radius)
    except Exception:
        return None
    return None


def normalize_vector(vector: tuple[float, float, float]) -> tuple[float, float, float]:
    length = math.sqrt(vector[0] ** 2 + vector[1] ** 2 + vector[2] ** 2)
    if length <= 1e-12:
        return (0.0, 0.0, 1.0)
    return (vector[0] / length, vector[1] / length, vector[2] / length)


def vector_subtract(a: tuple[float, float, float], b: tuple[float, float, float]) -> tuple[float, float, float]:
    return (a[0] - b[0], a[1] - b[1], a[2] - b[2])


def cross_length(a: tuple[float, float, float], b: tuple[float, float, float]) -> float:
    return math.sqrt(
        (a[1] * b[2] - a[2] * b[1]) ** 2
        + (a[2] * b[0] - a[0] * b[2]) ** 2
        + (a[0] * b[1] - a[1] * b[0]) ** 2
    )


def axis_distance(
    left: tuple[tuple[float, float, float], tuple[float, float, float], float],
    right: tuple[tuple[float, float, float], tuple[float, float, float], float],
) -> float:
    left_point, left_dir, _left_radius = left
    right_point, right_dir, _right_radius = right
    cross = (
        left_dir[1] * right_dir[2] - left_dir[2] * right_dir[1],
        left_dir[2] * right_dir[0] - left_dir[0] * right_dir[2],
        left_dir[0] * right_dir[1] - left_dir[1] * right_dir[0],
    )
    cross_norm = math.sqrt(cross[0] ** 2 + cross[1] ** 2 + cross[2] ** 2)
    delta = vector_subtract(right_point, left_point)
    if cross_norm <= 1e-6:
        return cross_length(delta, left_dir)
    return abs(delta[0] * cross[0] + delta[1] * cross[1] + delta[2] * cross[2]) / cross_norm


def best_cylindrical_face_pair(left: Any, right: Any) -> tuple[Any, Any, float] | None:
    candidates: list[tuple[float, float, Any, Any]] = []
    left_faces = [(face, face_cylinder_axis(face)) for face in component_faces(left)]
    left_faces = [(face, axis) for face, axis in left_faces if axis is not None]
    right_faces = [(face, face_cylinder_axis(face)) for face in component_faces(right)]
    right_faces = [(face, axis) for face, axis in right_faces if axis is not None]
    for left_face, left_axis in left_faces:
        for right_face, right_axis in right_faces:
            centerline_gap = axis_distance(left_axis, right_axis)
            radius_gap = abs(float(left_axis[2]) - float(right_axis[2]))
            candidates.append((centerline_gap + radius_gap * 10.0, centerline_gap, left_face, right_face))
    if not candidates:
        return None
    _score, distance, left_face, right_face = min(candidates, key=lambda item: item[0])
    return left_face, right_face, distance


def first_face(component: Any, predicate: str) -> Any | None:
    for face in component_faces(component):
        if face_surface_is(face, predicate):
            return face
    return None


def add_semantic_concentric_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str]) -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": "concentric", "semantic_pair": semantic_pair, "error": "component missing"}
    best = best_cylindrical_face_pair(left, right)
    if best is None:
        return {"name": name, "ok": False, "kind": "concentric", "semantic_pair": semantic_pair, "error": "cylindrical face missing"}
    left_face, right_face, face_pair_axis_distance_m = best
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_faces(asm, left_face, right_face, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {"name": name, "ok": False, "kind": "concentric", "semantic_pair": semantic_pair, "selected_entities": selected, "selection_guard": selection_guard, "components": component_pair, "error": "cylindrical faces not selected"}
    result = add_selected_mate(asm, name, 1, 0.0)
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["face_pair_axis_distance_m"] = face_pair_axis_distance_m
    result["kind"] = "concentric"
    result["semantic_pair"] = semantic_pair
    return result


def add_semantic_angle_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str], kind: str = "angle") -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": kind, "semantic_pair": semantic_pair, "error": "component missing"}
    best = explicit_planar_face_pair(left, right, name, semantic_pair)
    if best is None:
        return {"name": name, "ok": False, "kind": kind, "semantic_pair": semantic_pair, "error": "planar face pair missing"}
    left_face, right_face, actual_distance = best
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_faces(asm, left_face, right_face, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {"name": name, "ok": False, "kind": kind, "semantic_pair": semantic_pair, "selected_entities": selected, "selection_guard": selection_guard, "components": component_pair, "error": "planar faces not selected"}
    angle = math.radians(90.0)
    result = add_selected_mate(asm, name, 6, 0.0, angle=angle, angle_min=math.radians(0.0), angle_max=math.radians(180.0))
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["face_pair_actual_distance_m"] = actual_distance
    result["angle_rad"] = angle
    result["angle_range_rad"] = [0.0, math.pi]
    result["kind"] = kind
    result["semantic_pair"] = semantic_pair
    return result


def select_width_faces(asm: Any, width_faces: list[Any], tab_faces: list[Any], component_pair: list[str]) -> dict[str, Any]:
    asm.ClearSelection2(True)
    cleared_count = int(asm.SelectionManager.GetSelectedObjectCount2(-1))
    selections: list[bool] = []
    marked: list[int] = []
    for index, face in enumerate(width_faces):
        selections.append(select_face_with_mark(face, index > 0, asm, 1))
        marked.append(1)
    for index, face in enumerate(tab_faces, start=len(width_faces)):
        selections.append(select_face_with_mark(face, index > 0, asm, 16))
        marked.append(16)
    selected_count = int(asm.SelectionManager.GetSelectedObjectCount2(-1))
    return {
        "cleared_selection_count": cleared_count,
        "left_selected": all(selections[:2]),
        "right_selected": all(selections[2:]),
        "selection_count_before_mate": selected_count,
        "component_pair": component_pair,
        "width_selected": selections[:2],
        "tab_selected": selections[2:],
        "selection_marks": marked,
    }


def width_selection_variants(width_faces: list[Any], tab_faces: list[Any]) -> list[dict[str, Any]]:
    pythoncom, win32_client = require_pywin32()
    variants: list[dict[str, Any]] = [
        {
            "selection_variant": "variant_dispatch_array",
            "width_value": win32_client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, tuple(width_faces)),
            "tab_value": win32_client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_DISPATCH, tuple(tab_faces)),
        },
        {
            "selection_variant": "plain_dispatch_list",
            "width_value": width_faces,
            "tab_value": tab_faces,
        },
        {
            "selection_variant": "plain_dispatch_tuple",
            "width_value": tuple(width_faces),
            "tab_value": tuple(tab_faces),
        },
    ]
    return variants


def create_width_mate(asm: Any, name: str, width_faces: list[Any], tab_faces: list[Any], component_pair: list[str]) -> dict[str, Any]:
    selection_guard = select_width_faces(asm, width_faces, tab_faces, component_pair)
    if int(selection_guard["selection_count_before_mate"]) < 4:
        return {"name": name, "ok": False, "kind": "width", "components": component_pair, "selected_entities": selection_guard["selection_count_before_mate"], "selection_guard": selection_guard, "error": "width mate requires four selected faces"}
    addmate_result = add_selected_mate(asm, name, 11, 0.0)
    addmate_result["kind"] = "width"
    addmate_result["components"] = component_pair
    addmate_result["selected_entities"] = selection_guard["selection_count_before_mate"]
    addmate_result["selection_guard"] = selection_guard
    if addmate_result.get("ok"):
        return addmate_result
    try:
        create_data = getattr(asm, "CreateMateData", None)
        create_mate = getattr(asm, "CreateMate", None)
        if not callable(create_data) or not callable(create_mate):
            addmate_result["error"] = f"{addmate_result.get('error', 'AddMate5 failed')}; CreateMateData/CreateMate unavailable"
            return addmate_result
        create_attempts: list[dict[str, Any]] = []
        for variant in width_selection_variants(width_faces, tab_faces):
            try:
                data = create_data(11)
                data.WidthSelection = variant["width_value"]
                data.TabSelection = variant["tab_value"]
                data.ConstraintType = 0
                feat = create_mate(data)
                attempt = {
                    "selection_variant": variant["selection_variant"],
                    "ok": com_created(feat),
                    "returned": "None" if feat is None else repr(feat),
                }
                create_attempts.append(attempt)
                if com_created(feat):
                    feat.Name = name
                    return {
                        "name": name,
                        "ok": True,
                        "api": "CreateMateData/CreateMate",
                        "mate_error": 1,
                        "kind": "width",
                        "components": component_pair,
                        "selected_entities": selection_guard["selection_count_before_mate"],
                        "selection_guard": selection_guard,
                        "create_mate_attempts": create_attempts,
                    }
            except Exception as exc:
                create_attempts.append({
                    "selection_variant": variant["selection_variant"],
                    "ok": False,
                    "error": repr(exc),
                })
        addmate_result["api_fallback"] = "CreateMateData/CreateMate"
        addmate_result["create_mate_attempts"] = create_attempts
        addmate_result["error"] = f"{addmate_result.get('error', 'AddMate5 failed')}; CreateMate returned None"
        return addmate_result
    except Exception as exc:
        addmate_result["api_fallback"] = "CreateMateData/CreateMate"
        addmate_result["error"] = f"{addmate_result.get('error', 'AddMate5 failed')}; {repr(exc)}"
        return addmate_result


def add_semantic_width_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str]) -> dict[str, Any]:
    ram = component_by_part_name(components, semantic_pair[0])
    left_way = component_by_part_name(components, semantic_pair[1])
    right_way = component_by_part_name(components, semantic_pair[2]) if len(semantic_pair) > 2 else None
    if ram is None or left_way is None or right_way is None:
        return {"name": name, "ok": False, "kind": "width", "semantic_pair": semantic_pair, "error": "component missing"}
    selectors = shaper_width_interface_selector(name)
    left_way_face = explicit_planar_interface_face(left_way, *selectors["left_way"])
    right_way_face = explicit_planar_interface_face(right_way, *selectors["right_way"])
    ram_left_face = explicit_planar_interface_face(ram, *selectors["ram_left"])
    ram_right_face = explicit_planar_interface_face(ram, *selectors["ram_right"])
    if left_way_face is None or right_way_face is None or ram_left_face is None or ram_right_face is None:
        return {"name": name, "ok": False, "kind": "width", "semantic_pair": semantic_pair, "error": "width/tab planar faces missing"}
    component_pair = [left_way.Name2, right_way.Name2, ram.Name2]
    result = create_width_mate(asm, name, [left_way_face, right_way_face], [ram_left_face, ram_right_face], component_pair)
    result["semantic_pair"] = semantic_pair
    result["engineered_interfaces"] = [
        f"left_way:{selectors['left_way'][0]}_{selectors['left_way'][1]}",
        f"right_way:{selectors['right_way'][0]}_{selectors['right_way'][1]}",
        f"ram:{selectors['ram_left'][0]}_{selectors['ram_left'][1]}",
        f"ram:{selectors['ram_right'][0]}_{selectors['ram_right'][1]}",
    ]
    return result


def select_components(asm: Any, left: Any, right: Any, component_pair: list[str] | None = None) -> dict[str, Any]:
    asm.ClearSelection2(True)
    empty = empty_dispatch_variant()
    left_selected = bool(left.Select4(False, empty, False))
    right_selected = bool(right.Select4(True, empty, False))
    selected_count = int(asm.SelectionManager.GetSelectedObjectCount2(-1))
    return {
        "cleared_selection_count": 0,
        "left_selected": left_selected,
        "right_selected": right_selected,
        "selection_count_before_mate": selected_count,
        "component_pair": component_pair or [],
    }


def add_semantic_lock_mate(asm: Any, components: list[Any], name: str, semantic_pair: list[str]) -> dict[str, Any]:
    left = component_by_part_name(components, semantic_pair[0])
    right = component_by_part_name(components, semantic_pair[1])
    if left is None or right is None:
        return {"name": name, "ok": False, "kind": "lock", "semantic_pair": semantic_pair, "error": "component missing"}
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_components(asm, left, right, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {"name": name, "ok": False, "kind": "lock", "semantic_pair": semantic_pair, "selected_entities": selected, "selection_guard": selection_guard, "components": component_pair, "error": "components not selected"}
    # swMateLOCK = 16. Used here as explicit fixture-layout stabilization, not as
    # a substitute for real kinematic hinge/slider validation.
    result = add_selected_mate(asm, name, 16, 0.0)
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["kind"] = "lock"
    result["semantic_pair"] = semantic_pair
    result["layout_stabilizer"] = True
    return result


def shaper_distance_mate_clearance(name: str) -> float:
    clearances = {
        "Column_Bed_Setback": 0.142,
        "Left_Way_Column_Contact": 0.012,
        "Right_Way_Column_Contact": 0.052,
        "Way_Spacing_Distance": 0.008,
        "Ram_LeftWay_Guidance_Distance_Mate": 0.048,
        "Ram_RightWay_Guidance_Distance_Mate": 0.008,
        "Front_Gib_Ram_Clearance": 0.021,
        "Rear_Gib_Ram_Clearance": 0.021,
        "Tool_Head_Ram_Contact": 0.015,
        "Tool_Tool_Head_Contact": 0.017,
        "Slide_Bed_Contact": 0.0395,
        "Movable_Jaw_Table_Clearance": 0.025,
        "Crank_Shaft_Axial_Locator": 0.018,
        "Eccentric_Pin_Axial_Locator": 0.017,
        "Rocker_Pivot_Shaft_Axial_Locator": 0.018,
        "Rocker_Arm_Axial_Locator": 0.018,
        "Sliding_Die_Rocker_Slot_Clearance": 0.014,
        "Ram_Link_Ram_Axial_Locator": 0.018,
    }
    return clearances.get(name, 0.010)


def shaper_limit_distance_bounds(name: str) -> tuple[float, float]:
    nominal = shaper_distance_mate_clearance(name)
    tolerance = max(0.002, min(0.004, nominal * 0.1))
    return max(0.0, nominal - tolerance), nominal + tolerance


def restore_component_origin(sw: Any, component: Any, origin: tuple[float, float, float]) -> dict[str, Any]:
    """Move a component back to the accepted design origin before fixing it."""
    name = str(getattr(component, "Name2", ""))
    try:
        pythoncom, win32_client = require_pywin32()
        transform = read_member(component, "Transform2")
        data = list(read_member(transform, "ArrayData")) if transform is not None else [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        if len(data) < 16:
            data = [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0]
        data[9], data[10], data[11] = float(origin[0]), float(origin[1]), float(origin[2])
        variant_data = win32_client.VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, data)
        errors: list[str] = []
        if transform is not None:
            for candidate in (variant_data, data, tuple(data)):
                try:
                    setattr(transform, "ArrayData", candidate)
                    setattr(component, "Transform2", transform)
                    return {"component": name, "restored": True, "restored_origin_m": list(origin), "restore_api": "Transform2.ArrayData"}
                except Exception as exc:
                    errors.append(f"Transform2.ArrayData:{repr(exc)}")
                try:
                    solve_result = read_member(component, "SetTransformAndSolve2", transform)
                    if com_created(solve_result):
                        return {"component": name, "restored": True, "restored_origin_m": list(origin), "restore_api": "SetTransformAndSolve2(existing)", "api_result": solve_result}
                    returned = "None" if solve_result is None else repr(solve_result)
                    errors.append(f"SetTransformAndSolve2(existing) returned {returned}")
                except Exception as exc:
                    errors.append(f"SetTransformAndSolve2(existing):{repr(exc)}")
        try:
            math_util = read_member(sw, "GetMathUtility")
            new_transform = None
            for candidate in (variant_data, data):
                try:
                    created = math_util.CreateTransform(candidate)
                    if com_created(created):
                        new_transform = created
                        break
                    returned = "None" if created is None else repr(created)
                    errors.append(f"CreateTransform returned {returned}")
                except Exception as exc:
                    errors.append(f"CreateTransform:{repr(exc)}")
                try:
                    created = read_member(math_util, "CreateTransform", candidate)
                    if com_created(created):
                        new_transform = created
                        break
                    returned = "None" if created is None else repr(created)
                    errors.append(f"read_member(CreateTransform) returned {returned}")
                except Exception as exc:
                    errors.append(f"read_member(CreateTransform):{repr(exc)}")
            if com_created(new_transform):
                setattr(component, "Transform2", new_transform)
                return {"component": name, "restored": True, "restored_origin_m": list(origin), "restore_api": "CreateTransform"}
        except Exception as exc:
            errors.append(f"GetMathUtility/CreateTransform:{repr(exc)}")
        raise RuntimeError("; ".join(errors))
    except Exception as exc:
        return {"component": name, "restored": False, "restored_origin_m": list(origin), "error": repr(exc)}


def structural_reference_parts_for_shaper() -> set[str]:
    """Parts that may be fixed as assembly ground/reference geometry.

    These are intentionally boring structure. Moving mechanism members (ram,
    crank, pins, rocker, link, die block, tool head/tool bit) must remain free to
    be constrained by mates; fixing them makes the mate network decorative and
    hides bad assemblies behind forced transforms.
    """
    return {
        "cast_bed_with_t_slots",
        "column_frame_with_window",
    }


def functional_motion_parts_for_shaper() -> set[str]:
    return set(solved_primary_origins_for_shaper()) - structural_reference_parts_for_shaper()


def validate_design_layout_fixed_components(evidence: Any) -> list[str]:
    if not isinstance(evidence, list):
        return ["design_layout_fixed_components"]
    failed: list[str] = []
    fixed = {
        str(item.get("component", "")).split("-")[0]
        for item in evidence
        if isinstance(item, dict) and item.get("ok") is True
    }
    if not structural_reference_parts_for_shaper().issubset(fixed):
        failed.append("design_layout_fixed_components")
    forbidden = fixed & functional_motion_parts_for_shaper()
    if forbidden:
        failed.append("functional_components_fixed")
    return failed


def restore_primary_design_layout_components(sw: Any, components: list[Any]) -> list[dict[str, Any]]:
    """Restore all primary shaper components to the authored design layout."""
    primary_origins = authored_primary_origins_for_shaper()
    restored: list[dict[str, Any]] = []
    for component in components:
        name = str(getattr(component, "Name2", ""))
        prefix = name.split("-")[0]
        if prefix not in primary_origins:
            continue
        restored.append(restore_component_origin(sw, component, primary_origins[prefix]))
    return restored



def fix_primary_design_layout_components(sw: Any, asm: Any, components: list[Any]) -> list[dict[str, Any]]:
    """Fix only structural reference components, never the moving mechanism.

    This fixture is a stress test for real SolidWorks assembly behavior. The bed
    and column may act as ground references, but the ram, quick-return train,
    rocker, pins, links, tool head, and workholding details must not be fixed just
    to keep a picture together. If the mate network cannot keep those parts in a
    coherent machine layout, validation should fail and expose the defect.
    """
    primary_origins = authored_primary_origins_for_shaper()
    fixed_names = structural_reference_parts_for_shaper()
    fixed: list[dict[str, Any]] = []
    empty = empty_dispatch_variant()
    for component in components:
        name = str(getattr(component, "Name2", ""))
        prefix = name.split("-")[0]
        if prefix not in fixed_names:
            continue
        try:
            restore = restore_component_origin(sw, component, primary_origins[prefix])
            asm.ClearSelection2(True)
            selected = bool(component.Select4(False, empty, False))
            result = read_member(asm, "FixComponent") if selected else None
            fixed_readback = bool(read_member(component, "IsFixed")) if selected else False
            api_allows_success = result is None or com_created(result)
            fixed_ok = bool(selected) and bool(restore.get("restored")) and api_allows_success and fixed_readback
            error = None
            if not selected:
                error = "component selection returned False"
            elif result is False or result == 0:
                returned = "None" if result is None else repr(result)
                error = f"FixComponent returned {returned}"
            elif result is None and not fixed_readback:
                error = "FixComponent returned None and IsFixed readback was not true"
            elif not fixed_readback:
                error = "IsFixed readback was not true"
            row = {"component": name, "ok": fixed_ok, "selected": selected, "api_result": result, "fixed_readback": fixed_readback, **restore}
            if error is not None:
                row["error"] = error
            fixed.append(row)
        except Exception as exc:
            fixed.append({"component": name, "ok": False, "error": repr(exc)})
    return fixed




def add_shaper_mate_network(asm: Any, components: list[Any]) -> list[dict[str, Any]]:
    contract = expected_shaper_mate_contract()
    intent_executor = load_sibling_module("sw_mate_intent_execute")
    result = intent_executor.execute_intent(build_shaper_mate_intent_spec(), asm)
    executed = result.get("executed_mates", []) if isinstance(result, dict) else []
    mates = [
        normalize_intent_executed_mate(row, contract)
        for row in executed
        if isinstance(row, dict)
    ]
    seen = {mate.get("name") for mate in mates}
    for name, expected in contract.items():
        if name not in seen:
            mates.append({
                "name": name,
                "ok": False,
                "kind": expected["type"],
                "semantic_pair": list(expected["semantic_pair"]),
                "components": [f"{part_name}-1" for part_name in expected["semantic_pair"]],
                "error": "mate intent executor did not return this expected mate",
                "executor_ok": result.get("ok") if isinstance(result, dict) else False,
            })
    return mates


def add_bed_column_distance_mate(asm: Any, components: list[Any], distance: float) -> dict[str, Any]:
    return add_semantic_distance_mate(asm, components, "Bed_Column_Distance_Mate", ["cast_bed_with_t_slots", "column_frame_with_window"], distance)



def load_sibling_module(module_name: str) -> Any:
    import sys

    path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(path.parent))
    spec.loader.exec_module(module)
    return module


def prepare_assembly_for_inspect(asm: Any) -> None:
    """Resolve lightweight components and rebuild before sampling assembly state."""
    try:
        read_member(asm, "ResolveAllLightWeightComponents", True)
    except Exception:
        pass
    try:
        read_member(asm, "ForceRebuild3", False)
    except Exception:
        pass


def inspect_live_assembly_model(asm: Any, sw: Any, reports_dir: Path) -> dict[str, Any]:
    inspect_mod = load_sibling_module("sw_assembly_inspect")
    prepare_assembly_for_inspect(asm)
    report = inspect_mod.inspect_model_object(
        asm,
        started_by_probe=False,
        revision_number=read_member(sw, "RevisionNumber"),
        visible=read_member(sw, "Visible"),
    )
    report["ok"] = bool((report.get("active_document") or {}).get("type") == "assembly")
    out = reports_dir / "complete_shaper_inspect.json"
    out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return report


def understand_saved_assembly(inspect_report: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    understand_mod = load_sibling_module("sw_model_understand")
    task = "retained simple mechanism fixture: check ram guidance, quick-return drive, tool head, workholding, mate participation, spatial adjacency, and scattered components"
    report = understand_mod.understand(inspect_report, task, 160, 80, "spatial-assembly")
    report["ok"] = True
    json_out = reports_dir / "complete_shaper_model_understanding.json"
    md_out = reports_dir / "complete_shaper_model_understanding.md"
    json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_out.write_text(understand_mod.markdown(report), encoding="utf-8")
    return report

def component_name_from_interference_entity(entity: Any) -> str | None:
    try:
        comp = read_member(entity, "Component")
        if comp is not None:
            name = read_member(comp, "Name2")
            if name:
                return str(name)
    except Exception:
        pass
    try:
        name = read_member(entity, "Name2")
        if name:
            return str(name)
    except Exception:
        pass
    return None


def interference_component_pairs(interferences: Any) -> list[list[str]]:
    pairs: list[list[str]] = []
    if not interferences:
        return pairs
    for item in interferences:
        comps: list[str] = []
        raw_components = None
        for attr_name in ("GetComponents", "Components"):
            try:
                raw_components = read_member(item, attr_name)
            except Exception:
                raw_components = None
            if raw_components:
                break
        if raw_components:
            for comp in raw_components:
                try:
                    name = read_member(comp, "Name2")
                    if name:
                        comps.append(str(name))
                except Exception:
                    pass
        if len(comps) < 2:
            for attr in ("GetEntities", "Entities"):
                try:
                    raw_entities = read_member(item, attr)
                except Exception:
                    raw_entities = None
                if raw_entities:
                    for entity in raw_entities:
                        name = component_name_from_interference_entity(entity)
                        if name:
                            comps.append(name)
                if len(comps) >= 2:
                    break
        unique = []
        for name in comps:
            if name not in unique:
                unique.append(name)
        if len(unique) >= 2:
            pairs.append(unique[:2])
    return pairs


def run_assembly_callbacks(asm: Any, reports_dir: Path) -> dict[str, Any]:
    mass: dict[str, Any]
    interference: dict[str, Any]
    try:
        ext = read_member(asm, "Extension")
        mass_prop = read_member(ext, "CreateMassProperty") if ext is not None else None
        if mass_prop is None or isinstance(mass_prop, dict):
            raise RuntimeError(f"CreateMassProperty unavailable: {mass_prop}")
        mass_value = read_member(mass_prop, "Mass")
        mass = {"available": True, "mass_kg": float(mass_value)}
    except Exception as exc:
        mass = {"available": False, "error": repr(exc)}
    try:
        mgr = read_member(asm, "InterferenceDetectionManager")
        try:
            setattr(mgr, "TreatCoincidenceAsInterference", False)
        except Exception:
            pass
        try:
            setattr(mgr, "MakeInterferingPartsTransparent", False)
        except Exception:
            pass
        interferences = read_member(mgr, "GetInterferences")
        count = len(interferences) if interferences is not None else 0
        interference = {"available": True, "count": int(count), "pairs": interference_component_pairs(interferences)}
    except Exception as exc:
        interference = {"available": False, "count": None, "error": repr(exc)}
    callbacks = {"mass": mass, "interference": interference}
    (reports_dir / "mass.json").write_text(json.dumps(mass, indent=2), encoding="utf-8")
    (reports_dir / "interference.json").write_text(json.dumps(interference, indent=2), encoding="utf-8")
    return callbacks



def sample_expected_shaper_inspect_evidence() -> dict[str, Any]:
    comps = []
    placement_contract = expected_shaper_placement_contract()
    for part in build_complete_shaper_spec().parts:
        name = part.name
        origin = placement_contract.get(name, {}).get("expected_origin_m", (0.0, 0.0, 0.0))
        comps.append({
            "name2": f"{name}-1",
            "fixed": name == "cast_bed_with_t_slots",
            "suppressed": False,
            "bbox_m": [0, 0, 0, 0.01, 0.01, 0.01],
            "transform": {
                "origin_m": list(origin),
                "local_axes": {"x": [1, 0, 0], "y": [0, 1, 0], "z": [0, 0, 1]},
                "scale": 1,
            },
        })
    return {
        "ok": True,
        "active_document": {
            "type": "assembly",
            "component_count_sampled": expected_assembly_component_minimum(),
            "components": comps,
            "mate_like_features": [
                {
                    "name": name,
                    "type": expected_inspect_mate_type(expected["type"]),
                    "components": [f"{part_name}-1" for part_name in expected["semantic_pair"]],
                    "suppressed": False,
                }
                for name, expected in expected_shaper_mate_contract().items()
            ],
        },
    }


def sample_expected_shaper_understanding_evidence() -> dict[str, Any]:
    pairs = []
    seen: set[tuple[str, str]] = set()
    for left, right in expected_shaper_functional_connection_contract():
        key = tuple(sorted((left, right)))
        if key not in seen:
            pairs.append({"a": f"{left}-1", "b": f"{right}-1", "relation": "near", "gap_m": 0.002})
            seen.add(key)
    components = [{"name": f"{part.name}-1"} for part in build_complete_shaper_spec().parts]
    return {
        "ok": True,
        "baseline": {"inventory": {"component_count": expected_assembly_component_minimum(), "floating_components": []}},
        "cad_evidence_graph": {
            "components_index": components,
            "spatial_evidence": {"near_or_overlap_pairs": pairs, "missing_spatial_evidence": []},
        },
        "spatial_model": {"components": components, "pairwise_relations": pairs, "missing_spatial_evidence": []},
    }


def component_prefixes_from_inspect(inspect: dict[str, Any]) -> set[str]:
    doc = inspect.get("active_document") if isinstance(inspect, dict) else {}
    comps = doc.get("components", []) if isinstance(doc, dict) else []
    prefixes: set[str] = set()
    for comp in comps if isinstance(comps, list) else []:
        name = str(comp.get("name2", "")) if isinstance(comp, dict) else ""
        prefixes.add(name.split("-")[0])
    return prefixes


def authored_primary_origins_for_shaper() -> dict[str, tuple[float, float, float]]:
    """Stable pre-mate Transform2 origins for authored shaper layout.

    These values are the insertion/restoration pose that lets the execution
    layer select the intended interfaces before SolidWorks solves the mate
    network. They are deliberately separate from post-solve inspect readback so
    a successful solve cannot feed back into the next run and create drift.
    """
    return {
        "cast_bed_with_t_slots": (0.0, 0.0, -0.0275),
        "column_frame_with_window": (-0.22, 0.095, 0.035),
        "left_dovetail_way": (0.03, 0.245, 0.089),
        "right_dovetail_way": (0.03, 0.245, 0.129),
        "ram_with_dovetail_and_tool_mount": (0.10, 0.285, 0.169),
        "front_gib_plate": (0.10, 0.222, 0.223),
        "rear_gib_plate": (0.10, 0.222, 0.243),
        "clapper_tool_head": (0.315, 0.255, 0.255),
        "single_point_cutting_tool": (0.350, 0.160, 0.310),
        "bull_gear_crank_disk": (-0.245, 0.115, 0.091),
        "crank_center_shaft": (-0.245, 0.115, 0.0675),
        "eccentric_crank_pin": (-0.2093, 0.115, 0.190),
        "bronze_sliding_die_block": (-0.1735, 0.1487, 0.310),
        "slotted_rocker_arm": (-0.1735, 0.0347, 0.274),
        "rocker_pivot_bracket": (-0.205, 0.105, 0.378),
        "rocker_pivot_shaft": (-0.1735, 0.1487, 0.4525),
        "ram_drive_link": (0.100, 0.28012, 0.353),
        "table_cross_slide": (0.08, 0.085, 0.067),
        "work_table_with_t_slots": (0.10, 0.125, 0.1195),
        "vise_jaw_fixed": (0.045, 0.170, 0.372),
        "vise_jaw_movable": (0.165, 0.170, 0.395),
    }


def desired_primary_origins_for_shaper() -> dict[str, tuple[float, float, float]]:
    """Backward-compatible alias for the authored pre-mate layout contract."""
    return authored_primary_origins_for_shaper()


def solved_primary_origins_for_shaper() -> dict[str, tuple[float, float, float]]:
    """Expected primary origins for strict inspect placement validation."""
    return {
        "cast_bed_with_t_slots": (0.0, 0.0, -0.0275),
        "column_frame_with_window": (-0.22, 0.095, 0.035),
        "left_dovetail_way": (0.03, 0.245, 0.0965),
        "right_dovetail_way": (0.03, 0.245, 0.1365),
        "ram_with_dovetail_and_tool_mount": (0.10, 0.285, 0.1765),
        "front_gib_plate": (0.10, 0.222, 0.2025),
        "rear_gib_plate": (0.10, 0.222, 0.2505),
        "clapper_tool_head": (0.30, 0.255, 0.255),
        "single_point_cutting_tool": (0.350, 0.160, 0.310),
        "bull_gear_crank_disk": (-0.245, 0.115, 0.091),
        "crank_center_shaft": (-0.245, 0.115, 0.0675),
        "eccentric_crank_pin": (-0.20935, 0.115, 0.190),
        "bronze_sliding_die_block": (-0.1735, 0.1487, 0.310),
        "slotted_rocker_arm": (-0.1735, 0.0347, 0.274),
        "rocker_pivot_bracket": (-0.205, 0.105, 0.378),
        "rocker_pivot_shaft": (-0.1735, 0.1487, 0.4525),
        "ram_drive_link": (0.100, 0.28012, 0.3605),
        "table_cross_slide": (0.08, 0.090, 0.067),
        "work_table_with_t_slots": (0.10, 0.125, 0.1195),
        "vise_jaw_fixed": (0.045, 0.1635, 0.372),
        "vise_jaw_movable": (0.22745, 0.170, 0.395),
    }


def expected_shaper_placement_contract(tolerance_m: float = 0.003) -> dict[str, dict[str, Any]]:
    """Expected primary component origins for the solved live shaper assembly.

    Component count and mate names do not prove that the machine is assembled
    instead of scattered. This contract ties inspect Transform2 readback to the
    post-mate solved assembly positions for the primary functional components.
    Detail-strip fasteners/washers/oil-cups remain countable visual evidence but
    are excluded from the hard spatial placement check.
    """
    return {
        part_name: {
            "component": f"{part_name}-1",
            "expected_origin_m": origin,
            "tolerance_m": tolerance_m,
        }
        for part_name, origin in solved_primary_origins_for_shaper().items()
    }


def component_origin_from_inspect_item(component: dict[str, Any]) -> list[float] | None:
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


def origin_within_tolerance(origin: list[float], expected: tuple[float, float, float], tolerance_m: float) -> bool:
    return all(abs(float(origin[index]) - float(expected[index])) <= tolerance_m for index in range(3))


def validate_component_placement_evidence(inspect: dict[str, Any]) -> list[str]:
    doc = inspect.get("active_document") if isinstance(inspect, dict) else {}
    comps = doc.get("components", []) if isinstance(doc, dict) else []
    if not isinstance(comps, list):
        return ["inspect_report:component_placements"]
    by_name = {str(comp.get("name2", "")): comp for comp in comps if isinstance(comp, dict)}
    failed: list[str] = []
    for part_name, contract in expected_shaper_placement_contract().items():
        component_name = contract["component"]
        comp = by_name.get(component_name)
        if not comp:
            failed.append(part_name)
            continue
        origin = component_origin_from_inspect_item(comp)
        if origin is None:
            failed.append(part_name)
            continue
        if not origin_within_tolerance(origin, contract["expected_origin_m"], contract["tolerance_m"]):
            failed.append(part_name)
    return ["inspect_report:component_placements"] if failed else []


def validate_inspect_evidence(inspect: Any) -> list[str]:
    failed: list[str] = []
    if not isinstance(inspect, dict):
        return ["inspect_report"]
    doc = inspect.get("active_document") or {}
    if doc.get("type") != "assembly":
        failed.append("inspect_report:type")
    if int(doc.get("component_count_sampled", 0) or 0) < expected_assembly_component_minimum():
        failed.append("inspect_report:component_count")
    prefixes = component_prefixes_from_inspect(inspect)
    missing_parts = sorted({p.name for p in build_complete_shaper_spec().parts} - prefixes)
    if missing_parts:
        failed.append("inspect_report:components")
    failed.extend(validate_component_placement_evidence(inspect))
    mate_features = [m for m in doc.get("mate_like_features", []) if isinstance(m, dict)]
    mate_by_name = {str(m.get("name", "")): m for m in mate_features}
    if not set(expected_shaper_mate_contract()).issubset(set(mate_by_name)):
        failed.append("inspect_report:mate_like_features")
    for name, expected in expected_shaper_mate_contract().items():
        mate = mate_by_name.get(name)
        if not mate:
            continue
        if mate.get("type") != expected_inspect_mate_type(expected["type"]):
            failed.append("inspect_report:mate_details")
            continue
        if mate.get("suppressed") is True:
            failed.append("inspect_report:mate_details")
            continue
        if not component_pair_matches_semantic_pair(mate.get("components"), list(expected["semantic_pair"])):
            failed.append("inspect_report:mate_details")
            continue
    return failed


def validate_part_feature_evidence(evidence: Any) -> list[str]:
    if not isinstance(evidence, dict):
        return ["part_feature_evidence"]
    failed: list[str] = []
    for part_name, required_names in expected_live_feature_names().items():
        part_evidence = evidence.get(part_name)
        if not isinstance(part_evidence, dict) or part_evidence.get("ok") is not True:
            failed.append(f"part_feature_evidence:{part_name}")
            continue
        feature_names = {
            str(item.get("name", ""))
            for item in part_evidence.get("features", [])
            if isinstance(item, dict)
        }
        if not all(any(required in actual for actual in feature_names) for required in required_names):
            failed.append(f"part_feature_evidence:{part_name}")
    return failed or []


def validate_model_understanding_evidence(understanding: Any, mates: Any = None) -> list[str]:
    failed: list[str] = []
    if not isinstance(understanding, dict):
        return ["model_understanding"]
    inv = ((understanding.get("baseline") or {}).get("inventory") or {})
    if int(inv.get("component_count", 0) or 0) < expected_assembly_component_minimum():
        failed.append("model_understanding:component_count")
    failed.extend(validate_functional_connection_evidence(understanding, mates))
    spatial = ((understanding.get("cad_evidence_graph") or {}).get("spatial_evidence") or {})
    relations = spatial.get("near_or_overlap_pairs") or []
    relation_texts = [f"{r.get('a')} {r.get('b')}" for r in relations if isinstance(r, dict)] + verified_mate_connection_texts(mates)
    text = "\n".join(relation_texts)
    component_sources = []
    graph_components = (understanding.get("cad_evidence_graph") or {}).get("components_index") or []
    spatial_components = (understanding.get("spatial_model") or {}).get("components") or []
    component_sources.extend(graph_components if isinstance(graph_components, list) else [])
    component_sources.extend(spatial_components if isinstance(spatial_components, list) else [])
    if not component_sources:
        failed.append("model_understanding:spatial_contract")
    component_text = "\n".join(
        str(item.get("name", item.get("name2", item))) if isinstance(item, dict) else str(item)
        for item in component_sources
    )
    for group, members in expected_shaper_spatial_contract().items():
        hits = sum(1 for member in members if member in text)
        if hits < min(2, len(members)):
            failed.append(f"model_understanding:spatial_contract:{group}")
    if failed and not any(x == "model_understanding:spatial_contract" for x in failed):
        # Preserve a stable coarse failure code for callers/tests while still
        # keeping group-specific diagnostics in the report.
        if any(x.startswith("model_understanding:spatial_contract:") for x in failed):
            failed.append("model_understanding:spatial_contract")
    return failed

def validate_live_result(result: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    if not result.get("ok"):
        failed.append("build")
    if int(result.get("part_count", 0) or 0) != len(build_complete_shaper_spec().parts):
        failed.append("part_count")
    if int(result.get("component_count", 0) or 0) != expected_assembly_component_minimum():
        failed.append("component_count")
    if result.get("layout", {}).get("ok") is not True:
        failed.append("nominal_layout")
    failed.extend(validate_semantic_mate_network(result.get("mates", []), expected_shaper_mate_contract()))
    failed.extend(validate_design_layout_fixed_components(result.get("design_layout_fixed_components")))
    callbacks = result.get("callbacks", {})
    mass = callbacks.get("mass", {})
    mass_kg = float(mass.get("mass_kg", 0) or 0)
    mass_low, mass_high = expected_shaper_mass_range_kg()
    if not mass.get("available") or not (mass_low <= mass_kg <= mass_high):
        failed.append("mass_callback")
    interference = callbacks.get("interference", {})
    if not interference.get("available") or interference.get("count") is None:
        failed.append("interference_callback")
    if interference.get("count") != 0:
        failed.append("interference_clearance")
    failed.extend(validate_inspect_evidence(result.get("inspect")))
    failed.extend(validate_part_feature_evidence(result.get("part_feature_evidence")))
    failed.extend(validate_model_understanding_evidence(result.get("model_understanding"), result.get("mates", [])))
    post_cleanup = result.get("post_cleanup", {})
    if post_cleanup.get("locked_files") or post_cleanup.get("lock_files"):
        failed.append("post_cleanup_single_session")
    if "post_cleanup" not in result:
        failed.append("post_cleanup_single_session")
    return {"ok": not failed, "failed": failed}


def placements_for(spec: CompleteShaperSpec) -> dict[str, tuple[float, float, float]]:
    return {
        "cast_bed_with_t_slots": (0.00, 0.00, 0.000),
        "column_frame_with_window": (-0.22, 0.095, 0.056),
        "left_dovetail_way": (0.03, 0.245, 0.105),
        "right_dovetail_way": (0.03, 0.245, 0.145),
        "ram_with_dovetail_and_tool_mount": (0.10, 0.285, 0.198),
        "front_gib_plate": (0.10, 0.222, 0.232),
        "rear_gib_plate": (0.10, 0.222, 0.252),
        "clapper_tool_head": (0.315, 0.255, 0.274),
        "single_point_cutting_tool": (0.350, 0.160, 0.316),
        "bull_gear_crank_disk": (-0.245, 0.115, 0.102),
        "crank_center_shaft": (-0.245, 0.115, 0.125),
        "eccentric_crank_pin": (-0.198, 0.115, 0.190),
        "bronze_sliding_die_block": (-0.055, 0.205, 0.310),
        "slotted_rocker_arm": (-0.145, 0.205, 0.285),
        "rocker_pivot_bracket": (-0.205, 0.105, 0.406),
        "rocker_pivot_shaft": (-0.205, 0.105, 0.505),
        "ram_drive_link": (0.055, 0.245, 0.363),
        "table_cross_slide": (0.08, 0.085, 0.142),
        "work_table_with_t_slots": (0.10, 0.125, 0.207),
        "vise_jaw_fixed": (0.045, 0.170, 0.383),
        "vise_jaw_movable": (0.165, 0.170, 0.406),
    }


def detail_instance_placements() -> dict[str, list[tuple[float, float, float]]]:
    # Detail parts are attached around the actual machine envelope, not parked on
    # an exploded presentation strip. They remain slightly proud of the nearest
    # surfaces to avoid false hard interferences while still reading visually as
    # bolts, washers, and oil cups belonging to the shaper.
    bed_bolts = [(x, -0.078, 0.062) for x in (-0.30, -0.22, -0.14, 0.14, 0.22, 0.30)]
    table_bolts = [(x, 0.058, 0.392) for x in (0.005, 0.065, 0.135, 0.195)]
    column_bolts = [(x, y, 0.155) for x in (-0.285, -0.155) for y in (0.000, 0.065, 0.145, 0.225)]
    shaft_washers = [
        (-0.245, 0.115, 0.242),
        (-0.198, 0.115, 0.268),
        (-0.205, 0.105, 0.566),
        (-0.055, 0.205, 0.336),
    ]
    bolt_washers = [(x, -0.078, 0.082) for x in (-0.30, -0.22, -0.14, 0.14, 0.22, 0.30)] + [(x, 0.151, 0.412) for x in (0.005, 0.065)]
    oil_cups = [(-0.070, 0.284, 0.265), (0.080, 0.284, 0.265), (-0.245, 0.210, 0.145), (-0.205, 0.180, 0.535)]
    return {
        "fastener_set_m6": bed_bolts + table_bolts + column_bolts,
        "washer_set": shaft_washers + bolt_washers,
        "oil_cups": oil_cups,
    }


def construct_live_fixture(spec: CompleteShaperSpec, out_dir: Path, reports_dir: Path, force: bool) -> dict[str, Any]:
    layout = validate_nominal_layout(spec)
    if not layout["ok"]:
        raise RuntimeError(f"Nominal shaper layout has unapproved bbox intersections: {layout['intersections'][:8]}")
    stage = "attach_solidworks"
    sw = None
    started_by_fixture = False
    result: dict[str, Any] | None = None
    skipped: list[str] = []
    try:
        if force:
            sw, started_by_fixture = attach_solidworks()
            stage = "close_existing_fixture_documents"
            close_fixture_documents(sw, spec, out_dir)
            stage = "cleanup_output_dir"
            skipped = cleanup_dir(out_dir, force)
        runtime_preflight = preflight_solidworks_runtime(
            out_dir=out_dir,
            com_attach_probe=(lambda sw=sw: sw) if sw is not None else None,
        )
        if not runtime_preflight["ok"]:
            reports_dir.mkdir(parents=True, exist_ok=True)
            result = {
                "ok": False,
                "error": "SolidWorks runtime preflight failed; restart SolidWorks before live fixture generation",
                "runtime_preflight": runtime_preflight,
                "layout": layout,
                "validation": {"ok": False, "failed": list(runtime_preflight.get("failed", []))},
                "post_cleanup": probe_unlocked_generated_files(out_dir),
            }
            (reports_dir / "complete_shaper_build.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            return result
        if sw is None:
            sw, started_by_fixture = attach_solidworks()
        if not force:
            stage = "close_existing_fixture_documents"
            close_fixture_documents(sw, spec, out_dir)
            stage = "cleanup_output_dir"
            skipped = cleanup_dir(out_dir, force)
        out_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        part_paths: dict[str, Path] = {}
        part_feature_evidence: dict[str, Any] = {}
        for part in spec.parts:
            stage = f"create_part:{part.name}"
            assert_solidworks_runtime_healthy(stage)
            part_path, feature_evidence = create_part_with_feature_evidence(sw, out_dir, part)
            part_paths[part.name] = part_path
            part_feature_evidence[part.name] = feature_evidence
        stage = "new_assembly"
        asm = new_assembly(sw)
        components = []
        component_objs = []
        placements = placements_for(spec)
        detail_instances = detail_instance_placements()
        try:
            for part in spec.parts:
                stage = f"insert_component:{part.name}"
                assert_solidworks_runtime_healthy(stage)
                if part.name in placements:
                    comp = add_component(sw, asm, part_paths[part.name], placements[part.name])
                    components.append(comp.Name2)
                    component_objs.append(comp)
                for xyz in detail_instances.get(part.name, []):
                    comp = add_component(sw, asm, part_paths[part.name], xyz)
                    components.append(comp.Name2)
                    component_objs.append(comp)
            asm_path = out_dir / "bullhead_shaper_complete.SLDASM"
            stage = "assembly_rebuild"
            assert_solidworks_runtime_healthy(stage)
            require_rebuild_success(asm, "complete shaper assembly")
            stage = "restore_primary_design_layout_components"
            assert_solidworks_runtime_healthy(stage)
            design_layout_restored_components = restore_primary_design_layout_components(sw, component_objs)
            stage = "add_shaper_mate_network"
            assert_solidworks_runtime_healthy(stage)
            mates = add_shaper_mate_network(asm, component_objs)
            stage = "fix_primary_design_layout_components"
            assert_solidworks_runtime_healthy(stage)
            design_layout_fixed_components = fix_primary_design_layout_components(sw, asm, component_objs)
            stage = "assembly_callbacks"
            assert_solidworks_runtime_healthy(stage)
            callbacks = run_assembly_callbacks(asm, reports_dir)
            stage = "save_assembly"
            save_as(asm, asm_path)
            stage = "inspect_live_assembly_model"
            inspect_report = inspect_live_assembly_model(asm, sw, reports_dir)
            stage = "understand_saved_assembly"
            model_understanding = understand_saved_assembly(inspect_report, reports_dir)
        finally:
            close_doc(sw, asm)
        result = {
            "ok": True,
            "assembly": str((out_dir / "bullhead_shaper_complete.SLDASM").resolve()),
            "part_count": len(part_paths),
            "component_count": len(components),
            "components": components,
            "design_layout_restored_components": design_layout_restored_components,
            "design_layout_fixed_components": design_layout_fixed_components,
            "mates": mates,
            "callbacks": callbacks,
            "part_feature_evidence": part_feature_evidence,
            "inspect": inspect_report,
            "model_understanding": model_understanding,
            "layout": layout,
            "runtime_preflight": runtime_preflight,
            "skipped_locked_files": skipped,
        }
        return result
    except Exception as exc:
        reports_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "ok": False,
            "error": f"{type(exc).__name__}: {exc}",
            "stage": stage,
            "traceback": traceback.format_exc(),
            "layout": layout,
            "validation": {"ok": False, "failed": ["build", f"stage:{stage}"]},
        }
        return result
    finally:
        already_closed = False
        try:
            if sw is not None:
                close_or_exit_solidworks(sw, spec, out_dir, started_by_fixture)
            already_closed = True
        finally:
            if result is not None:
                result["post_cleanup"] = wait_for_generated_files_unlocked(out_dir)
                if "validation" not in result or result.get("ok") is True:
                    result["validation"] = validate_live_result(result)
                    result["ok"] = bool(result["validation"]["ok"])
                result["already_closed"] = already_closed
                reports_dir.mkdir(parents=True, exist_ok=True)
                (reports_dir / "complete_shaper_build.json").write_text(json.dumps(result, indent=2), encoding="utf-8")


def main() -> int:
    args = parse_args()
    spec = build_complete_shaper_spec()
    manifest_path = Path(args.manifest) if args.manifest else Path(args.reports_dir) / "complete_shaper_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(spec_to_manifest(spec), indent=2), encoding="utf-8")
    assembly_contract_path = Path(args.reports_dir) / "complete_shaper_assembly_contract.json"
    assembly_contract_path.parent.mkdir(parents=True, exist_ok=True)
    assembly_contract_path.write_text(json.dumps(build_shaper_assembly_contract(), indent=2, ensure_ascii=False), encoding="utf-8")
    if args.spec_only:
        print(json.dumps({"ok": True, "manifest": str(manifest_path), "assembly_contract": str(assembly_contract_path), "spec_only": True}, indent=2))
        return 0
    result = construct_live_fixture(spec, Path(args.out_dir), Path(args.reports_dir), args.force)
    result["manifest"] = str(manifest_path)
    result["assembly_contract"] = str(assembly_contract_path)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
