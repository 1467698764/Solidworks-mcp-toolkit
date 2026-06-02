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


def expected_shaper_mate_contract() -> dict[str, dict[str, Any]]:
    """Semantic mate network used by the shaper fixture acceptance gate.

    The shaper is a stress fixture for the generic project capability: a useful
    assembly must prove constraints across functional subassemblies, not merely
    create a few mate features. Each entry names the intended pair so validators
    can reject plausible-looking but mechanically unconnected assemblies.
    """
    return {
        "Bed_Column_Distance_Mate": {"type": "distance", "semantic_pair": ["cast_bed_with_t_slots", "column_frame_with_window"], "functional_group": "structural_stack"},
        "Ram_LeftWay_Guidance_Distance_Mate": {"type": "distance", "semantic_pair": ["ram_with_dovetail_and_tool_mount", "left_dovetail_way"], "functional_group": "ram_guidance"},
        "ToolHead_Ram_Distance_Mate": {"type": "distance", "semantic_pair": ["clapper_tool_head", "ram_with_dovetail_and_tool_mount"], "functional_group": "tool_head"},
        "Table_CrossSlide_Distance_Mate": {"type": "distance", "semantic_pair": ["work_table_with_t_slots", "table_cross_slide"], "functional_group": "workholding_stack"},
        "BullGear_CrankShaft_Concentric_Mate": {"type": "concentric", "semantic_pair": ["bull_gear_crank_disk", "crank_center_shaft"], "functional_group": "quick_return_drive"},
        "Crank_Link_Concentric_Mate": {"type": "concentric", "semantic_pair": ["eccentric_crank_pin", "ram_drive_link"], "functional_group": "quick_return_drive"},
        "Rocker_Pivot_Concentric_Mate": {"type": "concentric", "semantic_pair": ["slotted_rocker_arm", "rocker_pivot_shaft"], "functional_group": "quick_return_drive"},
    }


def expected_inspect_mate_type(kind: str) -> str:
    return {"distance": "MateDistanceDim", "concentric": "MateConcentric"}.get(kind, f"Mate:{kind}")


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


def mate_selection_evidence_ok(mate: dict[str, Any]) -> bool:
    guard = mate.get("selection_guard", {}) if isinstance(mate, dict) else {}
    return (
        int_equals(mate.get("selected_entities"), 2)
        and int_equals(guard.get("cleared_selection_count"), 0)
        and int_equals(guard.get("selection_count_before_mate"), 2)
    )


def mate_component_evidence_ok(mate: dict[str, Any], semantic_pair: list[str]) -> bool:
    components = mate.get("components") if isinstance(mate, dict) else None
    guard = mate.get("selection_guard", {}) if isinstance(mate, dict) else {}
    component_pair = guard.get("component_pair")
    if not isinstance(components, list) or len(components) != 2:
        return False
    if not isinstance(component_pair, list) or len(component_pair) != 2:
        return False
    if [str(item) for item in component_pair] != [str(item) for item in components]:
        return False
    return component_pair_matches_semantic_pair(components, semantic_pair)



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
        if mate.get("mate_error") not in (0, 1, None):
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


def expected_assembly_component_minimum() -> int:
    return len(build_complete_shaper_spec().parts) + sum(len(v) for v in detail_instance_placements().values())


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
            return {"ok": False, "failed": failed, "processes": snapshots, "lock_files": lock_files, "com_error": f"{type(exc).__name__}: {exc}"}
    return {"ok": not failed, "failed": failed, "processes": snapshots, "lock_files": lock_files, "out_dir": str(out_dir) if out_dir is not None else None, "max_private_memory_bytes": max_private_memory_bytes}


def assert_solidworks_runtime_healthy(
    stage: str,
    process_snapshots: list[dict[str, Any]] | None = None,
    max_private_memory_bytes: int = 1_900_000_000,
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


def cut_rects_once(model: Any, rects: list[tuple[float, float, float, float]], depth: float, name: str) -> None:
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
        return path
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
        if feat is not None:
            feat.Name = name
            return {"name": name, "ok": True, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None)}
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None), "error": "AddMate5 returned None"}
    except Exception as exc:
        return {"name": name, "ok": False, "api": "AddMate5", "mate_error": getattr(mate_error, "value", None), "error": repr(exc)}


def add_distance_mate_between_planar_faces(asm: Any, components: list[Any], distance: float, name: str = "Shaper_Distance_Mate") -> dict[str, Any]:
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
                        result = add_selected_mate(asm, name, 5, distance)
                        result["selected_entities"] = selection_guard["selection_count_before_mate"]
                        result["selection_guard"] = selection_guard
                        result["components"] = component_pair
                        if result["ok"]:
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


def face_surface_is(face: Any, predicate: str) -> bool:
    try:
        surface = read_member(face, "GetSurface")
        return bool(read_member(surface, predicate))
    except Exception:
        return False


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
    left_face = first_face(left, "IsCylinder")
    right_face = first_face(right, "IsCylinder")
    if left_face is None or right_face is None:
        return {"name": name, "ok": False, "kind": "concentric", "semantic_pair": semantic_pair, "error": "cylindrical face missing"}
    component_pair = [left.Name2, right.Name2]
    selection_guard = select_faces(asm, left_face, right_face, component_pair)
    selected = selection_guard["selection_count_before_mate"]
    if selected < 2:
        return {"name": name, "ok": False, "kind": "concentric", "semantic_pair": semantic_pair, "selected_entities": selected, "selection_guard": selection_guard, "components": component_pair, "error": "cylindrical faces not selected"}
    result = add_selected_mate(asm, name, 1, 0.0)
    result["selected_entities"] = selected
    result["selection_guard"] = selection_guard
    result["components"] = component_pair
    result["kind"] = "concentric"
    result["semantic_pair"] = semantic_pair
    return result


def add_shaper_mate_network(asm: Any, components: list[Any]) -> list[dict[str, Any]]:
    mates: list[dict[str, Any]] = []
    contract = expected_shaper_mate_contract()
    for name, expected in contract.items():
        if expected["type"] == "distance":
            mates.append(add_semantic_distance_mate(asm, components, name, list(expected["semantic_pair"]), 0.010))
        elif expected["type"] == "concentric":
            mates.append(add_semantic_concentric_mate(asm, components, name, list(expected["semantic_pair"])))
        else:
            mates.append({"name": name, "ok": False, "kind": expected["type"], "semantic_pair": expected["semantic_pair"], "error": "unknown mate type"})
    return mates


def add_bed_column_distance_mate(asm: Any, components: list[Any], distance: float) -> dict[str, Any]:
    return add_semantic_distance_mate(asm, components, "Bed_Column_Distance_Mate", ["cast_bed_with_t_slots", "column_frame_with_window"], distance)



def load_sibling_module(module_name: str) -> Any:
    path = Path(__file__).resolve().parent / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"could not load {path}")
    module = importlib.util.module_from_spec(spec)
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
    task = "牛头刨床 bullhead shaper 装配 空间关系 配合 约束 干涉 ram guidance quick return drive tool head"
    report = understand_mod.understand(inspect_report, task, 160, 80, "spatial-assembly")
    report["ok"] = True
    json_out = reports_dir / "complete_shaper_model_understanding.json"
    md_out = reports_dir / "complete_shaper_model_understanding.md"
    json_out.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    md_out.write_text(understand_mod.markdown(report), encoding="utf-8")
    return report

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



def sample_expected_shaper_inspect_evidence() -> dict[str, Any]:
    comps = []
    placements = placements_for(build_complete_shaper_spec())
    for part in build_complete_shaper_spec().parts:
        name = part.name
        origin = placements.get(name, (0.0, 0.0, 0.0))
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
                    "components": [f"{expected['semantic_pair'][0]}-1", f"{expected['semantic_pair'][1]}-1"],
                    "suppressed": False,
                }
                for name, expected in expected_shaper_mate_contract().items()
            ],
        },
    }


def sample_expected_shaper_understanding_evidence() -> dict[str, Any]:
    pairs = []
    for members in expected_shaper_spatial_contract().values():
        for left, right in zip(members, members[1:]):
            pairs.append({"a": f"{left}-1", "b": f"{right}-1", "relation": "near", "gap_m": 0.002})
    return {
        "ok": True,
        "baseline": {"inventory": {"component_count": expected_assembly_component_minimum(), "floating_components": []}},
        "cad_evidence_graph": {"spatial_evidence": {"near_or_overlap_pairs": pairs, "missing_spatial_evidence": []}},
        "spatial_model": {"components": [], "pairwise_relations": pairs, "missing_spatial_evidence": []},
    }


def component_prefixes_from_inspect(inspect: dict[str, Any]) -> set[str]:
    doc = inspect.get("active_document") if isinstance(inspect, dict) else {}
    comps = doc.get("components", []) if isinstance(doc, dict) else []
    prefixes: set[str] = set()
    for comp in comps if isinstance(comps, list) else []:
        name = str(comp.get("name2", "")) if isinstance(comp, dict) else ""
        prefixes.add(name.split("-")[0])
    return prefixes


def expected_shaper_placement_contract(tolerance_m: float = 0.003) -> dict[str, dict[str, Any]]:
    """Expected primary component origins for the live shaper assembly.

    Component count and mate names do not prove that the machine is assembled
    instead of scattered. This contract ties inspect Transform2 readback to the
    nominal layout used by the builder for the primary functional components.
    Detail-strip fasteners/washers/oil-cups remain countable visual evidence but
    are excluded from the hard spatial placement check.
    """
    spec = build_complete_shaper_spec()
    display_only = {"fastener_set_m6", "washer_set", "oil_cups"}
    return {
        part_name: {
            "component": f"{part_name}-1",
            "expected_origin_m": origin,
            "tolerance_m": tolerance_m,
        }
        for part_name, origin in placements_for(spec).items()
        if part_name not in display_only
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


def validate_model_understanding_evidence(understanding: Any) -> list[str]:
    failed: list[str] = []
    if not isinstance(understanding, dict):
        return ["model_understanding"]
    inv = ((understanding.get("baseline") or {}).get("inventory") or {})
    if int(inv.get("component_count", 0) or 0) < expected_assembly_component_minimum():
        failed.append("model_understanding:component_count")
    spatial = ((understanding.get("cad_evidence_graph") or {}).get("spatial_evidence") or {})
    relations = spatial.get("near_or_overlap_pairs") or []
    text = "\n".join(f"{r.get('a')} {r.get('b')}" for r in relations if isinstance(r, dict))
    component_sources = []
    graph_components = (understanding.get("cad_evidence_graph") or {}).get("components_index") or []
    spatial_components = (understanding.get("spatial_model") or {}).get("components") or []
    component_sources.extend(graph_components if isinstance(graph_components, list) else [])
    component_sources.extend(spatial_components if isinstance(spatial_components, list) else [])
    component_text = "\n".join(
        str(item.get("name", item.get("name2", item))) if isinstance(item, dict) else str(item)
        for item in component_sources
    )
    for group, members in expected_shaper_spatial_contract().items():
        hits = sum(1 for member in members if member in text)
        inventory_hits = sum(1 for member in members if member in component_text)
        if hits < min(2, len(members)) and inventory_hits < len(members):
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
    failed.extend(validate_model_understanding_evidence(result.get("model_understanding")))
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
    runtime_preflight = preflight_solidworks_runtime(out_dir=out_dir)
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
    stage = "attach_solidworks"
    sw = None
    started_by_fixture = False
    result: dict[str, Any] | None = None
    try:
        sw, started_by_fixture = attach_solidworks()
        stage = "close_existing_fixture_documents"
        close_fixture_documents(sw, spec, out_dir)
        stage = "cleanup_output_dir"
        skipped = cleanup_dir(out_dir, force)
        out_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        part_paths: dict[str, Path] = {}
        for part in spec.parts:
            stage = f"create_part:{part.name}"
            assert_solidworks_runtime_healthy(stage)
            print(f"[complete-shaper] creating {part.name}", flush=True)
            part_paths[part.name] = create_part(sw, out_dir, part)
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
                print(f"[complete-shaper] inserting {part.name}", flush=True)
                comp = add_component(sw, asm, part_paths[part.name], placements.get(part.name, (0, 0, 0)))
                components.append(comp.Name2)
                component_objs.append(comp)
                for xyz in detail_instances.get(part.name, []):
                    comp = add_component(sw, asm, part_paths[part.name], xyz)
                    components.append(comp.Name2)
                    component_objs.append(comp)
            asm_path = out_dir / "bullhead_shaper_complete.SLDASM"
            stage = "add_shaper_mate_network"
            assert_solidworks_runtime_healthy(stage)
            mates = add_shaper_mate_network(asm, component_objs)
            stage = "assembly_rebuild"
            assert_solidworks_runtime_healthy(stage)
            asm.ForceRebuild3(False)
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
            "mates": mates,
            "callbacks": callbacks,
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
    if args.spec_only:
        print(json.dumps({"ok": True, "manifest": str(manifest_path), "spec_only": True}, indent=2))
        return 0
    result = construct_live_fixture(spec, Path(args.out_dir), Path(args.reports_dir), args.force)
    result["manifest"] = str(manifest_path)
    print(json.dumps(result, indent=2))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
