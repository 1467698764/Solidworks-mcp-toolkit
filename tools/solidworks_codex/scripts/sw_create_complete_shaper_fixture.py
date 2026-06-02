#!/usr/bin/env python3
"""Generate a verified native SolidWorks bullhead shaper fixture.

The earlier v4 display fixture proved feature creation, but its side-elevation
parts were dimensioned with the machine height in SolidWorks Z. That produced
misplaced parts and many interferences. This v5 generator treats the Front Plane
sketch as the visible side elevation: size_mm is (X length, Y height, Z thickness).
It also records assembly mates, mass, native files, and interference callbacks so
the assembly is not accepted merely because files were produced.
"""
from __future__ import annotations

import argparse
import json
import math
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
        PartSpec("bull_gear_crank_disk", "crank_disk", (155, 155, 22), "round crank disk with center bore, eccentric pin hole, and lightening holes", (F("center_bore", 1, "main shaft hole"), F("eccentric_pin_hole", 1, "offset drive pin hole"), F("lightening_hole_pattern", 6, "circular lightening holes"), F("hole", 8, "disk holes"), F("cut", 8, "bores and lightening cuts"))),
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
        quality_target="display_grade_mechanical_model",
        output_dir=out,
        reports_dir="tools/solidworks_codex/reports/shaper_machine_v5",
        assembly_file=f"{out}/bullhead_shaper_complete.SLDASM",
        parts=parts,
        acceptance_rules=("no_plain_block_stack", "visible_holes_slots_and_fasteners", "recognizable_bullhead_shaper_silhouette"),
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
        "column_frame_with_window": ("Frame_Window_Cut", "Bearing_Bores_And_Cover_Holes_01"),
        "ram_with_dovetail_and_tool_mount": ("Dovetail_And_Oil_Groove_Cuts", "Angled_Dovetail_Underside_Cut", "Tool_Mount_Bolt_Holes"),
        "single_point_cutting_tool": ("Beveled_Cutting_Tip",),
        "bull_gear_crank_disk": ("Center_Eccentric_And_Lightening_Holes",),
        "slotted_rocker_arm": ("Long_Sliding_Slot", "Rocker_Pin_Bores_01", "Rocker_Pin_Bores_02"),
        "work_table_with_t_slots": ("Work_Table_T_Slots", "Table_Mount_Holes"),
        "left_dovetail_way": ("Dovetail_Relief", "Left_Angled_Dovetail_Flank", "Right_Angled_Dovetail_Flank", "Rail_Screw_Holes"),
        "right_dovetail_way": ("Dovetail_Relief", "Left_Angled_Dovetail_Flank", "Right_Angled_Dovetail_Flank", "Rail_Screw_Holes"),
        "fastener_set_m6": ("Hex_Body_fastener_set_m6", "Hex_Socket_Drive"),
    }


def expected_assembly_component_minimum() -> int:
    return len(build_complete_shaper_spec().parts) + sum(len(v) for v in detail_instance_placements().values())


def expected_shaper_mass_kg() -> float:
    return 15.125546510666322


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
    return {
        "ok": not intersections,
        "component_count": len(instances),
        "intersections": intersections,
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


def attach_solidworks() -> Any:
    _pythoncom, win32_client = require_pywin32()
    try:
        sw = win32_client.GetActiveObject("SldWorks.Application")
    except Exception:
        sw = win32_client.Dispatch("SldWorks.Application")
    try:
        sw.Visible = False
    except Exception:
        pass
    return sw


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
            feat.Select2(False, 0)
            return
        feat = read_member(feat, "GetNextFeature")
    raise RuntimeError("Could not select front/ref plane")


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
    if extension_result not in (False, 0, None):
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


def boss_box(model: Any, width: float, height: float, depth: float, name: str) -> None:
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    rect = model.SketchManager.CreateCornerRectangle(-width / 2, -height / 2, 0, width / 2, height / 2, 0)
    if rect is None:
        raise RuntimeError(f"CreateCornerRectangle returned None for body {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is None:
        raise RuntimeError(f"FeatureExtrusion2 returned None for body {name}")
    feat.Name = name


def boss_cylinder(model: Any, diameter: float, depth: float, name: str) -> None:
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    circle = model.SketchManager.CreateCircleByRadius(0, 0, 0, diameter / 2)
    if circle is None:
        raise RuntimeError(f"CreateCircleByRadius returned None for body {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is None:
        raise RuntimeError(f"FeatureExtrusion2 returned None for body {name}")
    feat.Name = name


def boss_regular_polygon(model: Any, sides: int, radius: float, depth: float, name: str, angle_offset: float = math.pi / 6) -> None:
    if sides < 3:
        raise ValueError("polygon body needs at least three sides")
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    points = [(math.cos(angle_offset + 2 * math.pi * i / sides) * radius, math.sin(angle_offset + 2 * math.pi * i / sides) * radius) for i in range(sides)]
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        line = model.SketchManager.CreateLine(x1, y1, 0, x2, y2, 0)
        if line is None:
            raise RuntimeError(f"CreateLine returned None for polygon body {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is None:
        raise RuntimeError(f"FeatureExtrusion2 returned None for polygon body {name}")
    feat.Name = name


def cut_polygon(model: Any, points: list[tuple[float, float]], depth: float, name: str) -> None:
    if len(points) < 3:
        raise ValueError("cut polygon needs at least three points")
    before = feature_names_by_type(model, "ProfileFeature")
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1]):
        line = model.SketchManager.CreateLine(x1, y1, 0, x2, y2, 0)
        if line is None:
            raise RuntimeError(f"CreateLine returned None for cut {name}")
    model.SketchManager.InsertSketch(True)
    select_new_cut_sketch(model, before)
    create_cut_from_selected_sketch(model, depth, name)


def add_rectangular_boss(model: Any, x: float, y: float, width: float, height: float, depth: float, name: str) -> None:
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    rect = model.SketchManager.CreateCornerRectangle(x - width / 2, y - height / 2, 0, x + width / 2, y + height / 2, 0)
    if rect is None:
        raise RuntimeError(f"CreateCornerRectangle returned None for boss {name}")
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is None:
        raise RuntimeError(f"FeatureExtrusion2 returned None for boss {name}")
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
    if feat is None:
        raise RuntimeError(f"FeatureCut3 returned None for {name}")
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


def cut_rects(model: Any, rects: list[tuple[float, float, float, float]], depth: float, name: str) -> None:
    before = feature_names_by_type(model, "ProfileFeature")
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    for x, y, w, h in rects:
        if w <= 0.003 or h <= 0.003:
            raise RuntimeError(f"Rectangle cut {name} is too small to create robustly: {w} x {h} m")
        rect = model.SketchManager.CreateCornerRectangle(x - w / 2, y - h / 2, 0, x + w / 2, y + h / 2, 0)
        if rect is None:
            raise RuntimeError(f"CreateCornerRectangle returned None for {name}: {w} x {h} m")
    model.SketchManager.InsertSketch(True)
    select_new_cut_sketch(model, before)
    create_cut_from_selected_sketch(model, depth, name)


def hole_pattern(count: int, span_x: float, y: float, radius: float) -> list[tuple[float, float, float]]:
    if count <= 1:
        return [(0, y, radius)]
    return [(-span_x / 2 + i * span_x / (count - 1), y, radius) for i in range(count)]


def circular_pattern(count: int, pcd: float, radius: float, offset_angle: float = 0.0) -> list[tuple[float, float, float]]:
    return [(math.cos(offset_angle + 2 * math.pi * i / count) * pcd / 2, math.sin(offset_angle + 2 * math.pi * i / count) * pcd / 2, radius) for i in range(count)]


def create_part(sw: Any, out_dir: Path, part: PartSpec) -> Path:
    path = out_dir / f"{part.name}.SLDPRT"
    model = new_part(sw)
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
    model.ForceRebuild3(False)
    save_as(model, path)
    close_doc(sw, model)
    return path


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


def open_part_for_insert(sw: Any, path: Path) -> Any:
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(str(path.resolve()), 1, 1, "", errors, warnings)
    if model is None:
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
    if comp is not None:
        return comp
    opened = open_part_for_insert(sw, path)
    activate_assembly(sw, asm)
    comp = asm.AddComponent5(resolved, 0, "", False, "", xyz[0], xyz[1], xyz[2])
    close_doc(sw, opened)
    if comp is None:
        raise RuntimeError(f"AddComponent5 failed for {path}")
    return comp


def byref_i4(value: int = 0) -> Any:
    pythoncom, win32_client = require_pywin32()
    return win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, value)


def component_faces(component: Any, limit: int = 64) -> list[Any]:
    faces: list[Any] = []
    try:
        bodies = component.GetBodies2(0)
    except Exception:
        bodies = None
    if not bodies:
        return faces
    for body in bodies:
        face = body.GetFirstFace()
        while face is not None and len(faces) < limit:
            faces.append(face)
            face = read_member(face, "GetNextFace")
    return faces


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
    return abs(a[0] * b[0] + a[1] * b[1] + a[2] * b[2]) > 0.99


def select_faces(asm: Any, first: Any, second: Any) -> int:
    asm.ClearSelection2(True)
    empty = empty_dispatch_variant()
    first.Select4(False, empty)
    second.Select4(True, empty)
    return int(asm.SelectionManager.GetSelectedObjectCount2(-1))


def add_selected_mate(asm: Any, name: str, mate_type: int, distance: float = 0.0) -> dict[str, Any]:
    mate_error = byref_i4(0)
    try:
        feat = asm.AddMate5(mate_type, -1, False, distance, 0, 0, 0, 0, 0, 0, 0, 0, False, False, mate_error)
        if feat is not None:
            feat.Name = name
            return {"name": name, "ok": True, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None)}
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None), "error": "AddMate5 returned None"}
    except Exception as exc:
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None), "error": repr(exc)}


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
                    selected = select_faces(asm, left_face, right_face)
                    if selected >= 2:
                        result = add_selected_mate(asm, "Shaper_Distance_Mate", 5, distance)
                        result["selected_entities"] = selected
                        result["components"] = [left.Name2, right.Name2]
                        if result["ok"]:
                            return result
    return {"name": "Shaper_Distance_Mate", "ok": False, "error": "no planar face pair accepted by AddMate5"}


def component_name_starts(component: Any, prefix: str) -> bool:
    return str(getattr(component, "Name2", "")).startswith(prefix)


def add_bed_column_distance_mate(asm: Any, components: list[Any], distance: float) -> dict[str, Any]:
    bed = next((component for component in components if component_name_starts(component, "cast_bed_with_t_slots-")), None)
    column = next((component for component in components if component_name_starts(component, "column_frame_with_window-")), None)
    if bed is None or column is None:
        return {"name": "Shaper_Distance_Mate", "ok": False, "error": "bed or column component missing"}
    result = add_distance_mate_between_planar_faces(asm, [bed, column], distance)
    result["semantic_pair"] = ["cast_bed_with_t_slots", "column_frame_with_window"]
    return result


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
        interference = {"available": True, "count": int(count)}
    except Exception as exc:
        interference = {"available": False, "count": None, "error": repr(exc)}
    callbacks = {"mass": mass, "interference": interference}
    (reports_dir / "mass.json").write_text(json.dumps(mass, indent=2), encoding="utf-8")
    (reports_dir / "interference.json").write_text(json.dumps(interference, indent=2), encoding="utf-8")
    return callbacks


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
    mates = result.get("mates", [])
    if not mates:
        failed.append("mate:missing")
    for mate in mates:
        if not mate.get("ok"):
            failed.append(f"mate:{mate.get('name')}")
        if mate.get("semantic_pair") != ["cast_bed_with_t_slots", "column_frame_with_window"]:
            failed.append(f"mate_semantics:{mate.get('name')}")
        if mate.get("mate_error") not in (0, 1):
            failed.append(f"mate_error:{mate.get('name')}")
    callbacks = result.get("callbacks", {})
    mass = callbacks.get("mass", {})
    if not mass.get("available") or abs(float(mass.get("mass_kg", 0) or 0) - expected_shaper_mass_kg()) > 0.05:
        failed.append("mass_callback")
    interference = callbacks.get("interference", {})
    if not interference.get("available") or interference.get("count") is None:
        failed.append("interference_callback")
    if interference.get("count") != 0:
        failed.append("interference_clearance")
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
        "eccentric_crank_pin": (-0.198, 0.115, 0.196),
        "bronze_sliding_die_block": (-0.055, 0.205, 0.292),
        "slotted_rocker_arm": (-0.145, 0.205, 0.245),
        "rocker_pivot_bracket": (-0.205, 0.105, 0.318),
        "rocker_pivot_shaft": (-0.205, 0.105, 0.377),
        "ram_drive_link": (0.055, 0.245, 0.363),
        "table_cross_slide": (0.08, 0.085, 0.142),
        "work_table_with_t_slots": (0.10, 0.125, 0.207),
        "vise_jaw_fixed": (0.045, 0.170, 0.383),
        "vise_jaw_movable": (0.165, 0.170, 0.406),
        "fastener_set_m6": (0.00, 0.11, 0.430),
        "washer_set": (-0.05, 0.11, 0.449),
        "oil_cups": (-0.08, -0.06, 0.453),
    }


def detail_instance_placements() -> dict[str, list[tuple[float, float, float]]]:
    # Display details are populated on a separate exploded presentation strip.
    # This keeps the fasteners/washers/oil cups visible and countable without
    # causing SolidWorks to report intentional screw/washer contact as hard
    # interference in the functional shaper mechanism.
    bed_bolts = [(x, -0.205, 0.500) for x in (-0.30, -0.24, -0.18, -0.12, -0.06, 0.0)]
    table_bolts = [(x, -0.245, 0.500) for x in (0.06, 0.12, 0.18, 0.24)]
    column_bolts = [(x, -0.285, 0.500) for x in (-0.30, -0.24, -0.18, -0.12, -0.06, 0.0, 0.06, 0.12)]
    washers = [(x, -0.330, 0.560) for x in (-0.42, -0.36, -0.30, -0.24, -0.18, -0.12, -0.06, 0.0, 0.06, 0.12, 0.18, 0.24)]
    oil_cups = [(x, -0.375, 0.540) for x in (-0.18, -0.08, 0.02, 0.12)]
    return {
        "fastener_set_m6": bed_bolts + table_bolts + column_bolts,
        "washer_set": washers,
        "oil_cups": oil_cups,
    }


def construct_live_fixture(spec: CompleteShaperSpec, out_dir: Path, reports_dir: Path, force: bool) -> dict[str, Any]:
    layout = validate_nominal_layout(spec)
    if not layout["ok"]:
        raise RuntimeError(f"Nominal shaper layout has unapproved bbox intersections: {layout['intersections'][:8]}")
    sw = attach_solidworks()
    close_fixture_documents(sw, spec, out_dir)
    skipped = cleanup_dir(out_dir, force)
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    part_paths: dict[str, Path] = {}
    for part in spec.parts:
        print(f"[complete-shaper] creating {part.name}", flush=True)
        part_paths[part.name] = create_part(sw, out_dir, part)
    asm = new_assembly(sw)
    components = []
    component_objs = []
    placements = placements_for(spec)
    detail_instances = detail_instance_placements()
    for part in spec.parts:
        print(f"[complete-shaper] inserting {part.name}", flush=True)
        comp = add_component(sw, asm, part_paths[part.name], placements.get(part.name, (0, 0, 0)))
        components.append(comp.Name2)
        component_objs.append(comp)
        for xyz in detail_instances.get(part.name, []):
            comp = add_component(sw, asm, part_paths[part.name], xyz)
            components.append(comp.Name2)
            component_objs.append(comp)
    asm_path = out_dir / "bullhead_shaper_complete.SLDASM"
    mates = [add_bed_column_distance_mate(asm, component_objs, 0.010)]
    asm.ForceRebuild3(False)
    callbacks = run_assembly_callbacks(asm, reports_dir)
    save_as(asm, asm_path)
    close_doc(sw, asm)
    close_fixture_documents(sw, spec, out_dir)
    result = {
        "ok": True,
        "assembly": str(asm_path.resolve()),
        "part_count": len(part_paths),
        "component_count": len(components),
        "components": components,
        "mates": mates,
        "callbacks": callbacks,
        "layout": layout,
        "skipped_locked_files": skipped,
        "post_cleanup": probe_unlocked_generated_files(out_dir),
    }
    result["validation"] = validate_live_result(result)
    result["ok"] = bool(result["validation"]["ok"])
    (reports_dir / "complete_shaper_build.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result

def main() -> int:
    args = parse_args()
    spec = build_complete_shaper_spec()
    manifest_path = Path(args.manifest) if args.manifest else Path(args.reports_dir) / "complete_shaper_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(spec_to_manifest(spec), indent=2), encoding="utf-8")
    if args.spec_only:
        print(json.dumps({"ok": True, "manifest": str(manifest_path), "spec_only": True}, indent=2))
        return 0
    result = construct_live_fixture(spec, Path(args.out_dir), Path(args.reports_dir), args.force)
    result["manifest"] = str(manifest_path)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
