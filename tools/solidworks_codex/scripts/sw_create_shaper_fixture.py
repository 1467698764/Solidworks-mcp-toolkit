#!/usr/bin/env python3
"""Create a legacy SolidWorks simple-mechanism validation fixture.

The module intentionally exposes a pure, import-safe mechanism specification so
unit tests and release gates can validate the fixture intent without requiring
SolidWorks or pywin32. Live model construction is performed only from the CLI.
"""
from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PartSpec:
    name: str
    kind: str
    size_mm: tuple[float, float, float]
    role: str
    material: str = "Plain Carbon Steel"


@dataclass(frozen=True)
class JointSpec:
    name: str
    kind: str
    components: tuple[str, str]
    purpose: str


@dataclass(frozen=True)
class DimensionSpec:
    name: str
    default_m: float
    validation_value_m: float
    purpose: str


@dataclass(frozen=True)
class ValidationTargets:
    safe_set_dimension: str
    safe_set_value_m: float
    hide_show_components: tuple[str, ...]
    fix_float_components: tuple[str, ...]
    export_step: str


@dataclass(frozen=True)
class ShaperSpec:
    name: str
    mechanism: str
    parts: tuple[PartSpec, ...]
    joints: tuple[JointSpec, ...]
    adjustable_dimensions: tuple[DimensionSpec, ...]
    validation_targets: ValidationTargets
    functional_requirements: tuple[str, ...]


def build_shaper_spec() -> ShaperSpec:
    parts = (
        PartSpec("base_casting", "block", (520, 220, 35), "rigid machine base and datum"),
        PartSpec("vertical_column", "block", (95, 70, 260), "supports ram ways and rocker pivot"),
        PartSpec("left_ram_way", "rail", (360, 18, 24), "left prismatic guide rail"),
        PartSpec("right_ram_way", "rail", (360, 18, 24), "right prismatic guide rail"),
        PartSpec("ram_slide", "block", (255, 58, 46), "reciprocating ram constrained by ways"),
        PartSpec("tool_head", "block", (48, 46, 72), "tool clapper/head on ram nose"),
        PartSpec("crank_disk", "cylinder", (120, 120, 18), "rotating drive disk with adjustable eccentric"),
        PartSpec("eccentric_crank_pin", "pin", (18, 18, 42), "offset crank pin driving die block"),
        PartSpec("sliding_die_block", "block", (42, 28, 28), "block sliding inside rocker slot"),
        PartSpec("slotted_rocker", "slot_link", (54, 18, 250), "oscillating slotted arm for quick return"),
        PartSpec("rocker_pivot_bracket", "bracket", (80, 42, 92), "fixed bracket carrying rocker pivot"),
        PartSpec("connecting_link", "link", (170, 18, 16), "link between rocker head and ram"),
        PartSpec("stroke_adjuster", "block", (36, 24, 30), "ram attachment with adjustable stroke window"),
        PartSpec("front_limit_stop", "block", (18, 66, 32), "front travel stop and interference sentinel"),
        PartSpec("rear_limit_stop", "block", (18, 66, 32), "rear travel stop and clearance sentinel"),
        PartSpec("pivot_pin_set", "pin", (16, 16, 70), "visible pivot pins and spacer washers"),
    )
    joints = (
        JointSpec("base_column_fixed", "coincident", ("base_casting-1", "vertical_column-1"), "column fixed to base"),
        JointSpec("left_way_fixed", "coincident", ("vertical_column-1", "left_ram_way-1"), "left way fixed to column"),
        JointSpec("right_way_fixed", "coincident", ("vertical_column-1", "right_ram_way-1"), "right way fixed to column"),
        JointSpec("ram_prismatic", "sliding", ("ram_slide-1", "left_ram_way-1"), "ram translates along guide rails"),
        JointSpec("tool_head_to_ram", "coincident", ("tool_head-1", "ram_slide-1"), "tool head mounted to ram"),
        JointSpec("crank_to_base", "revolute", ("crank_disk-1", "base_casting-1"), "drive disk rotates on base shaft"),
        JointSpec("pin_to_crank", "revolute", ("eccentric_crank_pin-1", "crank_disk-1"), "pin follows eccentric radius"),
        JointSpec("die_to_pin", "revolute", ("sliding_die_block-1", "eccentric_crank_pin-1"), "die block rotates around pin"),
        JointSpec("die_in_rocker_slot", "slot", ("sliding_die_block-1", "slotted_rocker-1"), "die block slides in rocker slot"),
        JointSpec("rocker_to_bracket", "revolute", ("slotted_rocker-1", "rocker_pivot_bracket-1"), "rocker oscillates about fixed pivot"),
        JointSpec("link_to_rocker", "revolute", ("connecting_link-1", "slotted_rocker-1"), "link driven by rocker head"),
        JointSpec("link_to_ram", "revolute", ("connecting_link-1", "stroke_adjuster-1"), "link drives ram adjuster"),
        JointSpec("adjuster_to_ram", "sliding", ("stroke_adjuster-1", "ram_slide-1"), "stroke window permits adjusted pin position"),
    )
    dims = (
        DimensionSpec("D1@Sketch_Eccentric@crank_disk.Part", 0.018, 0.022, "crank drive feature thickness is a guarded editable live dimension"),
        DimensionSpec("D1@Sketch_StrokeWindow@ram_slide.Part", 0.145, 0.158, "ram slot/window length"),
        DimensionSpec("D1@Sketch_RockerSlot@slotted_rocker.Part", 0.175, 0.185, "slotted rocker slot length"),
        DimensionSpec("D1@Sketch_RamTravel@base_casting.Part", 0.092, 0.105, "nominal ram travel envelope"),
    )
    targets = ValidationTargets(
        safe_set_dimension="D1@Sketch_Eccentric@crank_disk.Part",
        safe_set_value_m=0.022,
        hide_show_components=("tool_head-1", "front_limit_stop-1"),
        fix_float_components=("connecting_link-1", "slotted_rocker-1"),
        export_step="tools/solidworks_codex/exports/shaper_quick_return_validation.step",
    )
    return ShaperSpec(
        name="shaper_quick_return_validation",
        mechanism="legacy quick-return mechanism fixture",
        parts=parts,
        joints=joints,
        adjustable_dimensions=dims,
        validation_targets=targets,
        functional_requirements=(
            "quick_return",
            "ram_guided_prismatic_motion",
            "eccentric_radius_change_observable",
            "component_state_on_nontrivial_parts",
            "interference_and_clearance_targets",
            "mass_export_selection_report_targets",
        ),
    )


def spec_to_manifest(spec: ShaperSpec) -> dict[str, Any]:
    data = asdict(spec)
    data["part_count"] = len(spec.parts)
    data["joint_count"] = len(spec.joints)
    return data


def write_manifest(spec: ShaperSpec, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(spec_to_manifest(spec), indent=2), encoding="utf-8")
    return path




# --- Live SolidWorks construction -------------------------------------------------

def require_pywin32() -> tuple[Any, Any]:
    try:
        import pythoncom  # type: ignore[import-not-found]
        import win32com.client  # type: ignore[import-not-found]
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on host SolidWorks Python
        raise RuntimeError(
            "Live shaper fixture generation requires pywin32. "
            "Set SWCODEX_PYTHON to a Python that can import pythoncom and win32com.client."
        ) from exc
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
        sw.Visible = True
    except Exception:
        pass
    return sw


def save_model(model: Any, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    result = read_member(model, "SaveAs3", str(path.resolve()), 0, 2)
    if result is False:
        raise RuntimeError(f"SaveAs3 returned False for {path}")


def default_template(sw: Any, preference_index: int, label: str) -> str:
    template = sw.GetUserPreferenceStringValue(preference_index)
    if not template:
        raise RuntimeError(f"SolidWorks default {label} template preference {preference_index} is empty")
    return template


def new_part(sw: Any) -> Any:
    template = default_template(sw, 8, "part")
    model = sw.NewDocument(template, 0, 0, 0)
    if model is None:
        raise RuntimeError(f"NewDocument returned None for part template {template}")
    return model


def empty_dispatch_variant() -> Any:
    pythoncom, win32_client = require_pywin32()
    return win32_client.VARIANT(pythoncom.VT_DISPATCH, None)


def select_front_plane(model: Any) -> None:
    empty = empty_dispatch_variant()
    ok = model.Extension.SelectByID2("Front Plane", "PLANE", 0, 0, 0, False, 0, empty, 0)
    if not ok:
        feat = read_member(model, "FirstFeature")
        while feat is not None:
            if read_member(feat, "GetTypeName2") == "RefPlane":
                feat.Select2(False, 0)
                return
            feat = read_member(feat, "GetNextFeature")
        raise RuntimeError("Could not select a sketch plane for new part")


def close_document(sw: Any, model: Any) -> None:
    try:
        title = read_member(model, "GetTitle")
        if title:
            sw.CloseDoc(title)
    except Exception:
        pass


def create_box_part(sw: Any, path: Path, size_mm: tuple[float, float, float], feature_name: str, note: str) -> None:
    model = new_part(sw)
    w, h, d = (v / 1000.0 for v in size_mm)
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCornerRectangle(-w / 2, -h / 2, 0, w / 2, h / 2, 0)
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, d, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is not None:
        feat.Name = feature_name
    model.ForceRebuild3(False)
    save_model(model, path)
    close_document(sw, model)


def create_cylinder_part(sw: Any, path: Path, diameter_mm: float, depth_mm: float, feature_name: str, note: str) -> None:
    model = new_part(sw)
    r = diameter_mm / 2000.0
    depth = depth_mm / 1000.0
    select_front_plane(model)
    model.SketchManager.InsertSketch(True)
    model.SketchManager.CreateCircleByRadius(0, 0, 0, r)
    model.SketchManager.InsertSketch(True)
    feat = model.FeatureManager.FeatureExtrusion2(True, False, False, 0, 0, depth, 0, False, False, False, False, 0, 0, False, False, False, False, True, True, True, 0, 0, False)
    if feat is not None:
        feat.Name = feature_name
    model.ForceRebuild3(False)
    save_model(model, path)
    close_document(sw, model)


def create_part_for_spec(sw: Any, out_dir: Path, part: PartSpec) -> Path:
    path = out_dir / f"{part.name}.SLDPRT"
    feature_name = {
        "crank_disk": "Sketch_Eccentric",
        "ram_slide": "Sketch_StrokeWindow",
        "slotted_rocker": "Sketch_RockerSlot",
        "base_casting": "Sketch_RamTravel",
    }.get(part.name, f"Body_{part.name}")
    if part.kind in {"cylinder", "pin"}:
        create_cylinder_part(sw, path, max(part.size_mm[0], part.size_mm[1]), part.size_mm[2], feature_name, part.role)
    else:
        create_box_part(sw, path, part.size_mm, feature_name, part.role)
    return path


def new_assembly(sw: Any) -> Any:
    template = default_template(sw, 9, "assembly")
    asm = sw.NewDocument(template, 0, 0, 0)
    if asm is None:
        raise RuntimeError(f"NewDocument returned None for assembly template {template}")
    return asm


def open_part_for_insert(sw: Any, part_path: Path) -> Any:
    pythoncom, win32_client = require_pywin32()
    errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    warnings = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
    model = sw.OpenDoc6(str(part_path.resolve()), 1, 1, "", errors, warnings)
    if model is None:
        raise RuntimeError(f"OpenDoc6 failed before AddComponent for {part_path}; errors={getattr(errors, 'value', errors)}, warnings={getattr(warnings, 'value', warnings)}")
    return model


def add_component(sw: Any, asm: Any, part_path: Path, xyz_m: tuple[float, float, float], verbose: bool = False) -> Any:
    if verbose:
        print(f"[shaper]   opening {part_path.name}", flush=True)
    opened_model = open_part_for_insert(sw, part_path)
    try:
        title = read_member(asm, "GetTitle")
        if title:
            pythoncom, win32_client = require_pywin32()
            errors = win32_client.VARIANT(pythoncom.VT_BYREF | pythoncom.VT_I4, 0)
            sw.ActivateDoc3(title, False, 0, errors)
    except Exception:
        pass
    if verbose:
        print(f"[shaper]   inserting {part_path.name}", flush=True)
    comp = asm.AddComponent5(str(part_path.resolve()), 0, "", False, "", xyz_m[0], xyz_m[1], xyz_m[2])
    if comp is None:
        close_document(sw, opened_model)
        raise RuntimeError(f"AddComponent5 failed for {part_path}")
    close_document(sw, opened_model)
    return comp


def cleanup_output_dir(out_dir: Any, force: bool) -> list[str]:
    skipped: list[str] = []
    if not force or not out_dir.exists():
        return skipped
    for child in out_dir.glob("*"):
        if child.is_file():
            try:
                child.unlink()
            except PermissionError:
                skipped.append(getattr(child, "name", str(child)))
    return skipped


def construct_live_fixture(spec: ShaperSpec, out_dir: Path, reports_dir: Path, force: bool) -> dict[str, Any]:
    locked_files = cleanup_output_dir(out_dir, force)
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    sw = attach_solidworks()
    part_paths: dict[str, Path] = {}
    for part in spec.parts:
        print(f"[shaper] creating part {part.name}", flush=True)
        part_paths[part.name] = create_part_for_spec(sw, out_dir, part)
    asm = new_assembly(sw)
    placements = {
        "base_casting": (0.0, 0.0, 0.0),
        "vertical_column": (-0.17, 0.0, 0.09),
        "left_ram_way": (0.03, -0.036, 0.19),
        "right_ram_way": (0.03, 0.036, 0.19),
        "ram_slide": (0.075, 0.0, 0.205),
        "tool_head": (0.235, 0.0, 0.185),
        "crank_disk": (-0.145, 0.09, 0.075),
        "eccentric_crank_pin": (-0.110, 0.09, 0.082),
        "sliding_die_block": (-0.095, 0.055, 0.125),
        "slotted_rocker": (-0.075, 0.045, 0.16),
        "rocker_pivot_bracket": (-0.125, 0.045, 0.115),
        "connecting_link": (0.045, 0.045, 0.165),
        "stroke_adjuster": (0.120, 0.0, 0.205),
        "front_limit_stop": (0.245, 0.0, 0.095),
        "rear_limit_stop": (-0.020, 0.0, 0.095),
        "pivot_pin_set": (-0.105, 0.045, 0.155),
    }
    components: list[str] = []
    for part in spec.parts:
        print(f"[shaper] adding component {part.name}", flush=True)
        comp = add_component(sw, asm, part_paths[part.name], placements.get(part.name, (0, 0, 0)), verbose=True)
        components.append(comp.Name2)
    asm_path = out_dir / f"{spec.name}.SLDASM"
    asm.ForceRebuild3(False)
    print(f"[shaper] saving assembly {asm_path}", flush=True)
    save_model(asm, asm_path)
    result = {
        "ok": True,
        "assembly": str(asm_path.resolve()),
        "parts": {name: str(path.resolve()) for name, path in part_paths.items()},
        "components": components,
        "reports_dir": str(reports_dir.resolve()),
        "locked_files_skipped_during_cleanup": locked_files,
        "note": "Geometry is intentionally simple but mechanically named and placed to exercise assembly inspection, state changes, mass/interference/export, and guarded dimension edits.",
    }
    (reports_dir / "shaper_fixture_build.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out-dir", default="tools/solidworks_codex/live_fixture/shaper_machine")
    parser.add_argument("--reports-dir", default="tools/solidworks_codex/reports/shaper_machine")
    parser.add_argument("--manifest", default=None)
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--spec-only", action="store_true", help="write manifest without launching SolidWorks")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    spec = build_shaper_spec()
    manifest_path = Path(args.manifest) if args.manifest else Path(args.reports_dir) / "shaper_fixture_manifest.json"
    write_manifest(spec, manifest_path)
    if args.spec_only:
        print(json.dumps({"ok": True, "manifest": str(manifest_path), "spec_only": True}, indent=2))
        return 0
    result = construct_live_fixture(spec, Path(args.out_dir), Path(args.reports_dir), args.force)
    result["manifest"] = str(manifest_path)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
