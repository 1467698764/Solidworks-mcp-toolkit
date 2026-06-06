import importlib.util
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_create_complete_shaper_fixture.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sw_create_complete_shaper_fixture", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load complete shaper module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_shaper_mates(module):
    mates = []
    for name, expected in module.expected_shaper_mate_contract().items():
        mates.append({
            "name": name,
            "ok": True,
            "kind": expected["type"],
            "mate_error": 1,
            "semantic_pair": list(expected["semantic_pair"]),
            "components": [f"{expected['semantic_pair'][0]}-1", f"{expected['semantic_pair'][1]}-1"],
            "selected_entities": 2,
            "selection_guard": {
                "cleared_selection_count": 0,
                "left_selected": True,
                "right_selected": True,
                "selection_count_before_mate": 2,
                "component_pair": [f"{expected['semantic_pair'][0]}-1", f"{expected['semantic_pair'][1]}-1"],
            },
        })
    return mates


def sample_part_feature_evidence(module):
    return {
        part_name: {"ok": True, "features": [{"name": name, "type": "Feature"} for name in feature_names]}
        for part_name, feature_names in module.expected_live_feature_names().items()
    }


def sample_design_layout_fixed_components(module):
    return [
        {"component": f"{name}-1", "ok": True, "api_result": None}
        for name in module.structural_reference_parts_for_shaper()
    ]


class CompleteShaperSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_complete_shaper_has_display_grade_part_catalog(self):
        model = self.module.build_complete_shaper_spec()
        self.assertEqual(model.name, "bullhead_shaper_complete")
        self.assertGreaterEqual(len(model.parts), 24)
        names = {p.name for p in model.parts}
        required = {
            "cast_bed_with_t_slots",
            "column_frame_with_window",
            "ram_with_dovetail_and_tool_mount",
            "clapper_tool_head",
            "single_point_cutting_tool",
            "bull_gear_crank_disk",
            "eccentric_crank_pin",
            "slotted_rocker_arm",
            "bronze_sliding_die_block",
            "rocker_pivot_bracket",
            "ram_drive_link",
            "left_dovetail_way",
            "right_dovetail_way",
            "front_gib_plate",
            "rear_gib_plate",
            "table_cross_slide",
            "work_table_with_t_slots",
            "vise_jaw_fixed",
            "vise_jaw_movable",
            "rocker_pivot_shaft",
            "crank_center_shaft",
            "fastener_set_m6",
            "washer_set",
            "oil_cups",
        }
        self.assertTrue(required.issubset(names), sorted(required - names))

    def test_parts_require_real_holes_slots_ribs_and_fasteners(self):
        model = self.module.build_complete_shaper_spec()
        features_by_part = {p.name: {f.kind for f in p.features} for p in model.parts}
        self.assertIn("mounting_hole_pattern", features_by_part["cast_bed_with_t_slots"])
        self.assertIn("t_slot_cut", features_by_part["cast_bed_with_t_slots"])
        self.assertIn("rib", features_by_part["cast_bed_with_t_slots"])
        self.assertIn("frame_window_cut", features_by_part["column_frame_with_window"])
        self.assertIn("bearing_bore", features_by_part["column_frame_with_window"])
        self.assertIn("dovetail_rail", features_by_part["left_dovetail_way"])
        self.assertIn("dovetail_rail", features_by_part["right_dovetail_way"])
        self.assertIn("long_slot_cut", features_by_part["slotted_rocker_arm"])
        self.assertIn("pin_bore", features_by_part["slotted_rocker_arm"])
        self.assertIn("gear_tooth_profile", features_by_part["bull_gear_crank_disk"])
        self.assertIn("eccentric_pin_hole", features_by_part["bull_gear_crank_disk"])
        self.assertIn("lightening_hole_pattern", features_by_part["bull_gear_crank_disk"])
        self.assertIn("bolt_hole_pattern", features_by_part["clapper_tool_head"])
        self.assertIn("t_slot_cut", features_by_part["work_table_with_t_slots"])
        self.assertIn("hex_bolt", features_by_part["fastener_set_m6"])
        self.assertIn("washer", features_by_part["washer_set"])

    def test_validation_manifest_rejects_plain_block_stack(self):
        model = self.module.build_complete_shaper_spec()
        manifest = self.module.spec_to_manifest(model)
        self.assertEqual(manifest["quality_target"], "mechanism_assembly_validation")
        self.assertGreaterEqual(manifest["feature_counts"]["cut"], 18)
        self.assertGreaterEqual(manifest["feature_counts"]["hole"], 20)
        self.assertGreaterEqual(manifest["feature_counts"]["slot"], 6)
        self.assertGreaterEqual(manifest["feature_counts"]["fastener"], 12)
        self.assertIn("no_plain_block_stack", manifest["acceptance_rules"])
        self.assertIn("visible_holes_slots_and_fasteners", manifest["acceptance_rules"])
        self.assertIn("named_gear_has_tooth_profile", manifest["acceptance_rules"])
        self.assertIn("recognizable_bullhead_shaper_silhouette", manifest["acceptance_rules"])
        self.assertIn("mechanism_profile_blocking_checks", manifest["acceptance_rules"])

    def test_live_builder_fails_fast_for_missing_cut_features(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("require_com_created", source)
        self.assertIn("FeatureCut3 for", source)
        self.assertIn("CreateCornerRectangle for", source)
        self.assertIn("FeatureExtrusion2 for", source)
        self.assertIn("select_new_cut_sketch", source)

    def test_live_builder_treats_false_feature_returns_as_failures(self):
        class SketchManager:
            def InsertSketch(self, value):
                return True

            def CreateCornerRectangle(self, *args):
                return True

            def CreateCircleByRadius(self, *args):
                return True

        class FeatureManager:
            def FeatureExtrusion2(self, *args):
                return False

            def FeatureCut3(self, *args):
                return False

        class Extension:
            def SelectByID2(self, *args):
                return True

        class Model:
            def __init__(self):
                self.SketchManager = SketchManager()
                self.FeatureManager = FeatureManager()
                self.Extension = Extension()

        original = self.module.select_front_plane
        self.module.select_front_plane = lambda model: None
        try:
            with self.assertRaisesRegex(RuntimeError, "FeatureExtrusion2.*returned False"):
                self.module.boss_box(Model(), 0.1, 0.1, 0.01, "FalseExtrude")

            with self.assertRaisesRegex(RuntimeError, "FeatureCut3.*returned False"):
                self.module.create_cut_from_selected_sketch(Model(), 0.01, "FalseCut")
        finally:
            self.module.select_front_plane = original

    def test_live_builder_treats_false_new_document_as_failure(self):
        class Sw:
            def __init__(self, result):
                self.result = result

            def GetUserPreferenceStringValue(self, value):
                return "template"

            def NewDocument(self, *args):
                return self.result

        with self.assertRaisesRegex(RuntimeError, "NewDocument\\(part\\).*False"):
            self.module.new_part(Sw(False))

        with self.assertRaisesRegex(RuntimeError, "NewDocument\\(assembly\\).*0"):
            self.module.new_assembly(Sw(0))

    def test_select_front_plane_rejects_false_fallback_selection(self):
        class Feature:
            def GetTypeName2(self):
                return "RefPlane"

            def Select2(self, append, mark):
                return False

            def GetNextFeature(self):
                return None

        class Extension:
            def SelectByID2(self, *args):
                return False

        class Model:
            def __init__(self):
                self.Extension = Extension()
                self.FirstFeature = Feature()

        original = self.module.empty_dispatch_variant
        self.module.empty_dispatch_variant = lambda: object()
        try:
            with self.assertRaisesRegex(RuntimeError, "Could not select front/ref plane"):
                self.module.select_front_plane(Model())
        finally:
            self.module.empty_dispatch_variant = original

    def test_save_as_requires_created_file_even_when_extension_reports_success(self):
        class VariantFactory:
            def VARIANT(self, *args):
                return type("Variant", (), {"value": 0})()

        class PythonCom:
            VT_BYREF = 0
            VT_I4 = 0
            VT_DISPATCH = 0

        class Extension:
            def SaveAs(self, *args):
                return True

        class Model:
            def __init__(self):
                self.Extension = Extension()

            def SaveAs3(self, *args):
                return True

        original_require = self.module.require_pywin32
        original_empty = self.module.empty_dispatch_variant
        self.module.require_pywin32 = lambda: (PythonCom(), VariantFactory())
        self.module.empty_dispatch_variant = lambda: object()
        try:
            with TemporaryDirectory() as tmp:
                with self.assertRaisesRegex(RuntimeError, "SaveAs failed"):
                    self.module.save_as(Model(), Path(tmp) / "missing.SLDPRT")
        finally:
            self.module.require_pywin32 = original_require
            self.module.empty_dispatch_variant = original_empty

    def test_live_builder_places_visible_attached_detail_instances(self):
        detail_placements = self.module.detail_instance_placements()
        self.assertGreaterEqual(len(detail_placements["fastener_set_m6"]), 18)
        self.assertGreaterEqual(len(detail_placements["washer_set"]), 12)
        self.assertGreaterEqual(len(detail_placements["oil_cups"]), 4)
        self.assertEqual(self.module.expected_assembly_component_minimum(), 55)

    def test_eccentric_pin_contract_matches_solved_readback_origin(self):
        expected = self.module.expected_shaper_placement_contract()
        self.assertEqual(expected["eccentric_crank_pin"]["expected_origin_m"], (-0.2093, 0.115, 0.190))

    def test_shaft_washers_clear_eccentric_crank_pin_envelope(self):
        washers = self.module.detail_instance_placements()["washer_set"]
        eccentric_washer = washers[1]
        pin_origin = self.module.placements_for(self.module.build_complete_shaper_spec())["eccentric_crank_pin"]
        pin_half_depth_m = 0.070 / 2.0
        washer_half_depth_m = 0.003 / 2.0
        center_gap = abs(eccentric_washer[2] - pin_origin[2])
        self.assertGreater(center_gap, pin_half_depth_m + washer_half_depth_m)

    def test_component_face_enumeration_does_not_truncate_tooth_rich_gear_before_bores(self):
        class Face:
            def __init__(self, index):
                self.index = index
                self.next_face = None

            def GetNextFace(self):
                return self.next_face

        class Body:
            def __init__(self, faces):
                self.faces = faces

            def GetFirstFace(self):
                return self.faces[0]

        class Component:
            def __init__(self, faces):
                self.faces = faces

            def GetBodies2(self, body_type):
                return [Body(self.faces)]

        faces = [Face(index) for index in range(96)]
        for left, right in zip(faces, faces[1:]):
            left.next_face = right

        enumerated = self.module.component_faces(Component(faces))

        self.assertEqual(len(enumerated), 96)
        self.assertEqual(enumerated[-1].index, 95)

    def test_live_feature_contract_covers_non_block_details(self):
        expected = self.module.expected_live_feature_names()
        for part_name in (
            "cast_bed_with_t_slots",
            "column_frame_with_window",
            "ram_with_dovetail_and_tool_mount",
            "single_point_cutting_tool",
            "bull_gear_crank_disk",
            "slotted_rocker_arm",
            "work_table_with_t_slots",
            "left_dovetail_way",
            "right_dovetail_way",
            "fastener_set_m6",
        ):
            self.assertIn(part_name, expected)
            self.assertGreaterEqual(len(expected[part_name]), 1)
        self.assertIn("Beveled_Cutting_Tip", expected["single_point_cutting_tool"])
        self.assertIn("Hex_Body_fastener_set_m6", expected["fastener_set_m6"])
        self.assertIn("Hex_Socket_Drive", expected["fastener_set_m6"])
        self.assertIn("Angled_Dovetail_Underside_Cut", expected["ram_with_dovetail_and_tool_mount"])
        self.assertIn("Left_Angled_Dovetail_Flank", expected["left_dovetail_way"])
        self.assertIn("Gear_Tooth_Profile", expected["bull_gear_crank_disk"])

    def test_validate_live_result_requires_part_shape_feature_readback(self):
        base = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": sample_shaper_mates(self.module),
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "inspect": self.module.sample_expected_shaper_inspect_evidence(),
            "model_understanding": self.module.sample_expected_shaper_understanding_evidence(),
        }
        validation = self.module.validate_live_result(base)
        self.assertFalse(validation["ok"])
        self.assertIn("part_feature_evidence", validation["failed"])

        base["part_feature_evidence"] = sample_part_feature_evidence(self.module)
        base["design_layout_fixed_components"] = sample_design_layout_fixed_components(self.module)
        self.assertTrue(self.module.validate_live_result(base)["ok"])

        bad = dict(base)
        bad_features = sample_part_feature_evidence(self.module)
        bad_features["bull_gear_crank_disk"] = {"ok": True, "features": [{"name": "Plain_Disk_Body_Only"}]}
        bad["part_feature_evidence"] = bad_features
        failed = self.module.validate_live_result(bad)["failed"]
        self.assertIn("part_feature_evidence:bull_gear_crank_disk", failed)

        bad_gear = dict(base)
        bad_gear_features = sample_part_feature_evidence(self.module)
        bad_gear_features["bull_gear_crank_disk"] = {
            "ok": True,
            "features": [{"name": "Center_Eccentric_And_Lightening_Holes", "type": "Feature"}],
        }
        bad_gear["part_feature_evidence"] = bad_gear_features
        failed = self.module.validate_live_result(bad_gear)["failed"]
        self.assertIn("part_feature_evidence:bull_gear_crank_disk", failed)

    def test_live_outputs_are_separate_from_old_failed_fixture(self):
        model = self.module.build_complete_shaper_spec()
        self.assertIn("shaper_machine_v5", model.output_dir)
        self.assertTrue(model.assembly_file.endswith("bullhead_shaper_complete.SLDASM"))
        self.assertNotIn("shaper_quick_return_validation", model.assembly_file)

    def test_primary_parts_use_side_elevation_axes_not_depth_as_height(self):
        model = self.module.build_complete_shaper_spec()
        parts = {p.name: p for p in model.parts}
        # size_mm is interpreted by the builder as (side-view X, side-view Y, thickness Z).
        self.assertGreater(parts["column_frame_with_window"].size_mm[1], parts["column_frame_with_window"].size_mm[2])
        self.assertGreater(parts["slotted_rocker_arm"].size_mm[1], parts["slotted_rocker_arm"].size_mm[2] * 6)
        self.assertGreater(parts["ram_with_dovetail_and_tool_mount"].size_mm[0], parts["ram_with_dovetail_and_tool_mount"].size_mm[1] * 4)
        self.assertGreater(parts["work_table_with_t_slots"].size_mm[0], parts["work_table_with_t_slots"].size_mm[1] * 6)

    def test_nominal_placement_has_no_unapproved_bounding_box_intersections(self):
        model = self.module.build_complete_shaper_spec()
        validation = self.module.validate_nominal_layout(model)
        self.assertTrue(validation["ok"], validation)
        self.assertEqual([], validation["intersections"])
        self.assertGreaterEqual(validation["component_count"], self.module.expected_assembly_component_minimum())



    def test_semantic_mate_network_validator_is_generic_not_shaper_name_bound(self):
        contract = {
            "Base_Cover_Distance": {"type": "distance", "semantic_pair": ["base_plate", "cover_plate"]},
            "Shaft_Bearing_Concentric": {"type": "concentric", "semantic_pair": ["drive_shaft", "bearing_block"]},
        }
        mates = [
            {
                "name": "Base_Cover_Distance",
                "ok": True,
                "kind": "distance",
                "semantic_pair": ["base_plate", "cover_plate"],
                "components": ["base_plate-1", "cover_plate-1"],
                "selected_entities": 2,
                "selection_guard": {"cleared_selection_count": 0, "left_selected": True, "right_selected": True, "selection_count_before_mate": 2, "component_pair": ["base_plate-1", "cover_plate-1"]},
            },
            {
                "name": "Shaft_Bearing_Concentric",
                "ok": True,
                "kind": "concentric",
                "semantic_pair": ["drive_shaft", "bearing_block"],
                "components": ["drive_shaft-1", "bearing_block-1"],
                "selected_entities": 2,
                "selection_guard": {"cleared_selection_count": 0, "left_selected": True, "right_selected": True, "selection_count_before_mate": 2, "component_pair": ["drive_shaft-1", "bearing_block-1"]},
            },
        ]
        self.assertEqual([], self.module.validate_semantic_mate_network(mates, contract))

        broken = list(mates)
        broken[1] = dict(broken[1], components=["wrong-1", "bearing_block-1"])
        self.assertIn("mate_components:Shaft_Bearing_Concentric", self.module.validate_semantic_mate_network(broken, contract))

    def test_semantic_mate_network_rejects_unsolved_mate_error(self):
        contract = {
            "Base_Cover_Distance": {"type": "distance", "semantic_pair": ["base_plate", "cover_plate"]},
        }
        mate = {
            "name": "Base_Cover_Distance",
            "ok": True,
            "kind": "distance",
            "mate_error": 4,
            "semantic_pair": ["base_plate", "cover_plate"],
            "components": ["base_plate-1", "cover_plate-1"],
            "selected_entities": 2,
            "selection_guard": {"cleared_selection_count": 0, "left_selected": True, "right_selected": True, "selection_count_before_mate": 2, "component_pair": ["base_plate-1", "cover_plate-1"]},
        }

        failed = self.module.validate_semantic_mate_network([mate], contract)

        self.assertIn("mate_error:Base_Cover_Distance", failed)

    def test_live_builder_treats_false_addmate_return_as_failure(self):
        class Asm:
            def AddMate5(self, *args):
                return False

        original = self.module.byref_i4
        self.module.byref_i4 = lambda value=0: type("ByRef", (), {"value": value})()
        try:
            result = self.module.add_selected_mate(Asm(), "FalseMate", 3)
        finally:
            self.module.byref_i4 = original

        self.assertFalse(result["ok"])
        self.assertEqual("AddMate5 returned False", result["error"])

    def test_face_selection_guard_records_each_select4_result(self):
        class SelectionManager:
            def GetSelectedObjectCount2(self, mark):
                return 2

        class Asm:
            def ClearSelection2(self, value):
                return True

            def __init__(self):
                self.SelectionManager = SelectionManager()

        class Face:
            def __init__(self, selected):
                self.selected = selected

            def Select4(self, *args):
                return self.selected

        original = self.module.empty_dispatch_variant
        self.module.empty_dispatch_variant = lambda: object()
        try:
            guard = self.module.select_faces(Asm(), Face(False), Face(True), ["left-1", "right-1"])
        finally:
            self.module.empty_dispatch_variant = original

        self.assertFalse(guard["left_selected"])
        self.assertTrue(guard["right_selected"])

    def test_live_validation_rejects_false_face_selection_results(self):
        base = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": sample_shaper_mates(self.module),
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "inspect": self.module.sample_expected_shaper_inspect_evidence(),
            "model_understanding": self.module.sample_expected_shaper_understanding_evidence(),
            "part_feature_evidence": sample_part_feature_evidence(self.module),
            "design_layout_fixed_components": sample_design_layout_fixed_components(self.module),
        }
        bad_mates = sample_shaper_mates(self.module)
        bad_mates[0]["selection_guard"] = dict(bad_mates[0]["selection_guard"], left_selected=False)
        base["mates"] = bad_mates

        self.assertIn(f"mate_selection:{bad_mates[0]['name']}", self.module.validate_live_result(base)["failed"])


    def test_complete_shaper_uses_real_interface_mates_without_fixing_motion_parts(self):
        expected = self.module.expected_shaper_mate_contract()
        real_mates = {name: mate for name, mate in expected.items() if mate.get("type") in {"parallel", "concentric"}}

        self.assertGreaterEqual(len(real_mates), 14)
        self.assertIn("Ram_Left_Way_Parallel", real_mates)
        self.assertIn("Bull_Gear_Crank_Shaft_Concentric", real_mates)
        self.assertEqual("MateParallel", self.module.expected_inspect_mate_type("parallel"))
        self.assertEqual("MateConcentric", self.module.expected_inspect_mate_type("concentric"))
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("GetSelectedObjectCount2(-1)", source)
        self.assertNotIn("selection_count(asm)", source)
        construct = source[source.index("def construct_live_fixture"):]
        self.assertLess(
            construct.index("design_layout_restored_components = restore_primary_design_layout_components(sw, component_objs)"),
            construct.index("mates = add_shaper_mate_network(asm, component_objs)"),
        )
        self.assertLess(
            construct.index("mates = add_shaper_mate_network(asm, component_objs)"),
            construct.index("design_layout_fixed_components = fix_primary_design_layout_components(sw, asm, component_objs)"),
        )

    def test_shaper_exports_generic_assembly_contract_for_reusable_validation(self):
        contract = self.module.build_shaper_assembly_contract()

        self.assertEqual("assembly", contract["document_type"])
        self.assertEqual(self.module.expected_assembly_component_minimum(), contract["minimum_component_count"])
        self.assertIn("cast_bed_with_t_slots", contract["components"])
        self.assertIn("origin_m", contract["components"]["cast_bed_with_t_slots"])
        self.assertIn("Ram_Left_Way_Parallel", contract["mates"])
        self.assertEqual("MateParallel", contract["mates"]["Ram_Left_Way_Parallel"]["type"])
        self.assertEqual(["ram_with_dovetail_and_tool_mount", "left_dovetail_way"], contract["mates"]["Ram_Left_Way_Parallel"]["semantic_pair"])
        self.assertIn("Bull_Gear_Crank_Shaft_Concentric", contract["mates"])
        self.assertEqual("MateConcentric", contract["mates"]["Bull_Gear_Crank_Shaft_Concentric"]["type"])
        self.assertEqual(set(self.module.expected_shaper_mate_contract()), set(contract["mates"]))

    def test_complete_shaper_requires_semantic_mate_network_not_single_distance_mate(self):
        expected = self.module.expected_shaper_mate_contract()
        self.assertGreaterEqual(len(expected), 18)
        mate_types = {mate["type"] for mate in expected.values()}
        self.assertIn("parallel", mate_types)
        self.assertIn("concentric", mate_types)
        self.assertNotIn("distance", mate_types)
        self.assertFalse(all(mate["type"] == "lock" for mate in expected.values()))
        for required_mate in (
            "Bed_Column_Parallel",
            "Left_Way_Column_Parallel",
            "Right_Way_Column_Parallel",
            "Ram_Left_Way_Parallel",
            "Tool_Head_Ram_Parallel",
            "Tool_Tool_Head_Parallel",
            "Table_Slide_Parallel",
            "Fixed_Jaw_Table_Parallel",
            "Bull_Gear_Crank_Shaft_Concentric",
            "Eccentric_Pin_Bull_Gear_Concentric",
            "Rocker_Pivot_Shaft_Bracket_Concentric",
            "Rocker_Arm_Pivot_Shaft_Concentric",
            "Sliding_Die_Rocker_Concentric",
            "Ram_Link_Ram_Concentric",
        ):
            self.assertIn(required_mate, expected)

        spatial = self.module.expected_shaper_spatial_contract()
        self.assertIn("structural_stack", spatial)
        self.assertIn("ram_guidance", spatial)
        self.assertIn("tool_head", spatial)
        self.assertIn("quick_return_drive", spatial)
        self.assertIn("ram_with_dovetail_and_tool_mount", spatial["ram_guidance"])
        self.assertIn("single_point_cutting_tool", spatial["tool_head"])

        only_one = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": [{"name": "Shaper_Distance_Mate", "ok": True, "mate_error": 1, "semantic_pair": ["cast_bed_with_t_slots", "column_frame_with_window"]}],
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "inspect": self.module.sample_expected_shaper_inspect_evidence(),
            "model_understanding": self.module.sample_expected_shaper_understanding_evidence(),
            "part_feature_evidence": sample_part_feature_evidence(self.module),
            "design_layout_fixed_components": sample_design_layout_fixed_components(self.module),
        }

        validation = self.module.validate_live_result(only_one)

        self.assertFalse(validation["ok"])
        self.assertIn("mate_network", validation["failed"])

    def test_complete_shaper_rejects_missing_guidance_toolhead_and_table_mates(self):
        base = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": sample_shaper_mates(self.module),
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "inspect": self.module.sample_expected_shaper_inspect_evidence(),
            "model_understanding": self.module.sample_expected_shaper_understanding_evidence(),
            "part_feature_evidence": sample_part_feature_evidence(self.module),
            "design_layout_fixed_components": sample_design_layout_fixed_components(self.module),
        }
        self.assertTrue(self.module.validate_live_result(base)["ok"])

        missing = dict(base)
        missing["mates"] = [
            mate for mate in sample_shaper_mates(self.module)
            if mate["name"] not in {
                "Ram_Left_Way_Parallel",
                "Tool_Head_Ram_Parallel",
                "Table_Slide_Parallel",
            }
        ]
        validation = self.module.validate_live_result(missing)
        self.assertFalse(validation["ok"])
        self.assertIn("mate_network", validation["failed"])


    def test_complete_shaper_rejects_fixed_functional_parts_as_mechanism_solution(self):
        base = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": sample_shaper_mates(self.module),
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "inspect": self.module.sample_expected_shaper_inspect_evidence(),
            "model_understanding": self.module.sample_expected_shaper_understanding_evidence(),
            "part_feature_evidence": sample_part_feature_evidence(self.module),
            "design_layout_fixed_components": [
                {"component": f"{name}-1", "ok": True, "api_result": None}
                for name in self.module.solved_primary_origins_for_shaper()
            ],
        }

        validation = self.module.validate_live_result(base)

        self.assertFalse(validation["ok"])
        self.assertIn("functional_components_fixed", validation["failed"])

    def test_detail_instances_must_be_attached_to_machine_not_exploded_display_strip(self):
        validation = self.module.validate_detail_instance_layout(self.module.build_complete_shaper_spec())

        self.assertTrue(validation["ok"], validation)
        self.assertEqual([], validation["detached_instances"])

    def test_live_inspect_reuses_current_assembly_and_cleanup_after_exit(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("inspect_live_assembly_model(asm", source)
        self.assertNotIn("inspect_saved_assembly(asm_path", source)
        self.assertIn("already_closed", source)
        self.assertIn("wait_for_generated_files_unlocked", source)
        self.assertLess(source.index("close_or_exit_solidworks(sw, spec, out_dir, started_by_fixture)"), source.rindex('result["post_cleanup"] = wait_for_generated_files_unlocked(out_dir)'))

    def test_live_build_failure_report_includes_stage_and_traceback(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("traceback.format_exc()", source)
        self.assertIn('"stage"', source)


    def test_runtime_preflight_refuses_stale_lock_files_before_live(self):
        result = self.module.preflight_solidworks_runtime(process_snapshots=[], lock_files=["~$part.SLDPRT"])
        self.assertFalse(result["ok"])
        self.assertIn("solidworks_stale_lock_files", result["failed"])

    def test_runtime_preflight_refuses_high_memory_or_com_dead_session(self):
        high = [{"name": "SLDWORKS", "id": 123, "private_memory_bytes": 2_500_000_000, "responding": True}]
        result = self.module.preflight_solidworks_runtime(process_snapshots=high, max_private_memory_bytes=1_500_000_000)
        self.assertFalse(result["ok"])
        self.assertIn("solidworks_memory_high", result["failed"])

        low = [{"name": "SLDWORKS", "id": 124, "private_memory_bytes": 500_000_000, "responding": True}]
        result = self.module.preflight_solidworks_runtime(process_snapshots=low, com_attach_probe=lambda: (_ for _ in ()).throw(RuntimeError("COM unavailable")))
        self.assertFalse(result["ok"])
        self.assertIn("solidworks_com_unreachable", result["failed"])
        self.assertEqual("responsive_process_without_com", result["diagnosis"])
        self.assertIn("restart SolidWorks", result["recommended_action"])

        result = self.module.preflight_solidworks_runtime(process_snapshots=high, max_private_memory_bytes=1_500_000_000, com_attach_probe=lambda: (_ for _ in ()).throw(RuntimeError("COM unavailable")))
        self.assertFalse(result["ok"])
        self.assertIn("solidworks_memory_high", result["failed"])
        self.assertIn("solidworks_com_unreachable", result["failed"])
        self.assertEqual("unhealthy_process_without_com", result["diagnosis"])

    def test_inspect_and_model_understanding_are_hard_shaper_gates(self):
        base = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": sample_shaper_mates(self.module),
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
        }
        no_inspect = self.module.validate_live_result(dict(base))
        self.assertFalse(no_inspect["ok"])
        self.assertIn("inspect_report", no_inspect["failed"])
        self.assertIn("model_understanding", no_inspect["failed"])

        inspected = dict(base)
        inspected["inspect"] = self.module.sample_expected_shaper_inspect_evidence()
        inspected["model_understanding"] = self.module.sample_expected_shaper_understanding_evidence()
        inspected["part_feature_evidence"] = sample_part_feature_evidence(self.module)
        inspected["design_layout_fixed_components"] = sample_design_layout_fixed_components(self.module)
        self.assertTrue(self.module.validate_live_result(inspected)["ok"])

        bad = dict(inspected)
        bad["model_understanding"] = {"ok": True, "baseline": {"inventory": {"component_count": self.module.expected_assembly_component_minimum(), "floating_components": []}}, "cad_evidence_graph": {"spatial_evidence": {"near_or_overlap_pairs": []}}}
        validation = self.module.validate_live_result(bad)
        self.assertFalse(validation["ok"])
        self.assertIn("model_understanding:spatial_contract", validation["failed"])

    def test_model_understanding_accepts_verified_mate_network_as_functional_connection_evidence(self):
        sparse = {
            "ok": True,
            "baseline": {"inventory": {"component_count": self.module.expected_assembly_component_minimum()}},
            "cad_evidence_graph": {"spatial_evidence": {"near_or_overlap_pairs": []}},
            "spatial_model": {"components": [{"name": part.name} for part in self.module.build_complete_shaper_spec().parts], "pairwise_relations": []},
        }
        failed_without_mates = self.module.validate_model_understanding_evidence(sparse)
        self.assertIn("model_understanding:functional_connections", failed_without_mates)

        failed_with_mates = self.module.validate_model_understanding_evidence(sparse, sample_shaper_mates(self.module))
        self.assertNotIn("model_understanding:functional_connections", failed_with_mates)
        self.assertNotIn("model_understanding:spatial_contract", failed_with_mates)

    def test_model_understanding_rejects_contract_member_inventory_when_near_pairs_are_sparse(self):
        components_index = []
        for group_members in self.module.expected_shaper_spatial_contract().values():
            for name in group_members:
                components_index.append({"name": f"{name}-1", "bbox_m": [0, 0, 0, 0.01, 0.01, 0.01]})
        understanding = {
            "ok": True,
            "baseline": {"inventory": {"component_count": self.module.expected_assembly_component_minimum(), "floating_components": []}},
            "cad_evidence_graph": {
                "components_index": components_index,
                "spatial_evidence": {"near_or_overlap_pairs": [], "missing_spatial_evidence": []},
            },
            "spatial_model": {"components": components_index, "pairwise_relations": [], "missing_spatial_evidence": []},
        }
        failed = self.module.validate_model_understanding_evidence(understanding)
        self.assertIn("model_understanding:spatial_contract", failed)

    def test_model_understanding_requires_functional_adjacency_pairs(self):
        required_pairs = self.module.expected_shaper_functional_connection_contract()
        self.assertGreaterEqual(len(required_pairs), 18)
        understanding = self.module.sample_expected_shaper_understanding_evidence()
        self.assertEqual([], self.module.validate_model_understanding_evidence(understanding))

        sparse = dict(understanding)
        sparse["cad_evidence_graph"] = {"spatial_evidence": {"near_or_overlap_pairs": [
            {"a": "cast_bed_with_t_slots-1", "b": "column_frame_with_window-1", "relation": "near", "gap_m": 0.002}
        ], "missing_spatial_evidence": []}}
        sparse["spatial_model"] = {"pairwise_relations": []}
        failed = self.module.validate_model_understanding_evidence(sparse)
        self.assertIn("model_understanding:functional_connections", failed)

    def test_inspect_evidence_rejects_same_named_mates_without_type_and_component_pair(self):
        evidence = self.module.sample_expected_shaper_inspect_evidence()
        doc = evidence["active_document"]
        doc["mate_like_features"] = [{"name": name} for name in self.module.expected_shaper_mate_contract()]
        failed = self.module.validate_inspect_evidence(evidence)
        self.assertIn("inspect_report:mate_details", failed)

    def test_inspect_evidence_rejects_mate_bound_to_wrong_component_pair(self):
        evidence = self.module.sample_expected_shaper_inspect_evidence()
        doc = evidence["active_document"]
        doc["mate_like_features"][0] = dict(doc["mate_like_features"][0], components=["ram_with_dovetail_and_tool_mount-1", "single_point_cutting_tool-1"])
        failed = self.module.validate_inspect_evidence(evidence)
        self.assertIn("inspect_report:mate_details", failed)

    def test_inspect_evidence_requires_primary_component_transform_placement_readback(self):
        evidence = self.module.sample_expected_shaper_inspect_evidence()
        self.assertEqual([], self.module.validate_inspect_evidence(evidence))

        doc = evidence["active_document"]
        by_name = {item["name2"]: item for item in doc["components"]}
        del by_name["ram_with_dovetail_and_tool_mount-1"]["transform"]
        failed = self.module.validate_inspect_evidence(evidence)
        self.assertIn("inspect_report:component_placements", failed)

        evidence = self.module.sample_expected_shaper_inspect_evidence()
        doc = evidence["active_document"]
        by_name = {item["name2"]: item for item in doc["components"]}
        by_name["bull_gear_crank_disk-1"]["transform"]["origin_m"] = [9.0, 9.0, 9.0]
        failed = self.module.validate_inspect_evidence(evidence)
        self.assertIn("inspect_report:component_placements", failed)

    def test_placement_contract_covers_functional_shaper_subassemblies(self):
        contract = self.module.expected_shaper_placement_contract()
        for name in (
            "cast_bed_with_t_slots",
            "column_frame_with_window",
            "ram_with_dovetail_and_tool_mount",
            "bull_gear_crank_disk",
            "slotted_rocker_arm",
            "work_table_with_t_slots",
            "single_point_cutting_tool",
        ):
            self.assertIn(name, contract)
            self.assertLessEqual(contract[name]["tolerance_m"], 0.003)

    def test_placement_contract_uses_restored_design_transform_origins_after_mates(self):
        contract = self.module.expected_shaper_placement_contract()

        self.assertEqual((0.0, 0.0, -0.0275), contract["cast_bed_with_t_slots"]["expected_origin_m"])
        self.assertEqual((-0.22, 0.095, 0.035), contract["column_frame_with_window"]["expected_origin_m"])
        self.assertEqual((-0.245, 0.115, 0.0675), contract["crank_center_shaft"]["expected_origin_m"])
        self.assertEqual((0.1, 0.125, 0.1195), contract["work_table_with_t_slots"]["expected_origin_m"])



    def test_primary_layout_fix_restores_design_transform_before_fixing_components(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("restore_component_origin", source)
        self.assertIn("desired_primary_origins_for_shaper", source)
        self.assertIn("Transform2", source)
        self.assertIn("CreateTransform", source)
        self.assertIn("restored_origin_m", source)

    def test_live_builder_restores_all_primary_layout_after_mates_without_fixing_motion_parts(self):
        source = SCRIPT.read_text(encoding="utf-8")
        construct = source[source.index("def construct_live_fixture"):]
        self.assertIn("restore_primary_design_layout_components", source)
        self.assertIn("design_layout_restored_components", source)
        self.assertLess(
            construct.index("asm.ForceRebuild3(False)"),
            construct.index("design_layout_restored_components = restore_primary_design_layout_components(sw, component_objs)"),
        )
        self.assertLess(
            construct.index("design_layout_restored_components = restore_primary_design_layout_components(sw, component_objs)"),
            construct.index("mates = add_shaper_mate_network(asm, component_objs)"),
        )
        self.assertLess(
            construct.index("mates = add_shaper_mate_network(asm, component_objs)"),
            construct.index("inspect_live_assembly_model(asm, sw, reports_dir)"),
        )

    def test_placement_contract_targets_restored_design_layout_not_bad_solver_positions(self):
        origins = self.module.solved_primary_origins_for_shaper()
        self.assertEqual((-0.22, 0.095, 0.035), origins["column_frame_with_window"])
        self.assertEqual((0.03, 0.245, 0.089), origins["left_dovetail_way"])
        self.assertEqual((0.10, 0.125, 0.1195), origins["work_table_with_t_slots"])

    def test_distance_mate_uses_closest_parallel_face_pair_not_first_arbitrary_faces(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("best_parallel_planar_face_pair", source)
        self.assertIn("face_plane_offset", source)
        self.assertIn("abs(actual_distance - distance)", source)
        self.assertNotIn('if result["ok"]:\n                            return result', source)

    def test_plane_params_use_point_then_normal_for_parallel_face_selection(self):
        class Surface:
            def __init__(self, params):
                self.params = params

            def IsPlane(self):
                return True

            def PlaneParams(self):
                return self.params

        class Face:
            def __init__(self, params):
                self.surface = Surface(params)

            def GetSurface(self):
                return self.surface

        left_face = Face([0.0, 0.0, 0.010, 0.0, 0.0, 1.0])
        right_face = Face([0.0, 0.0, 0.035, 0.0, 0.0, -1.0])

        self.assertEqual((0.0, 0.0, 1.0), self.module.face_plane_normal(left_face))
        self.assertEqual((0.0, 0.0, -1.0), self.module.face_plane_normal(right_face))
        self.assertAlmostEqual(self.module.face_plane_offset(left_face, (0.0, 0.0, 1.0)), 0.010)
        self.assertAlmostEqual(self.module.face_plane_offset(right_face, (0.0, 0.0, 1.0)), 0.035)

    def test_best_parallel_planar_face_pair_uses_actual_plane_distance(self):
        class Surface:
            def __init__(self, params):
                self.params = params

            def IsPlane(self):
                return True

            def PlaneParams(self):
                return self.params

        class Face:
            def __init__(self, name, params):
                self.name = name
                self.surface = Surface(params)
                self.next_face = None

            def GetSurface(self):
                return self.surface

            def GetNextFace(self):
                return self.next_face

        class Body:
            def __init__(self, faces):
                self.faces = faces

            def GetFirstFace(self):
                for left, right in zip(self.faces, self.faces[1:]):
                    left.next_face = right
                return self.faces[0]

        class Component:
            def __init__(self, faces):
                self.faces = faces

            def GetBodies2(self, body_type):
                return [Body(self.faces)]

        left = Component([Face("left_reference", [0.0, 0.0, 0.010, 0.0, 0.0, 1.0])])
        near = Face("right_025", [0.0, 0.0, 0.035, 0.0, 0.0, -1.0])
        far = Face("right_080", [0.0, 0.0, 0.090, 0.0, 0.0, -1.0])
        right = Component([far, near])

        selected_left, selected_right, actual_distance = self.module.best_parallel_planar_face_pair(left, right, 0.025)

        self.assertEqual("left_reference", selected_left.name)
        self.assertEqual("right_025", selected_right.name)
        self.assertAlmostEqual(actual_distance, 0.025)



    def test_concentric_mate_uses_best_cylindrical_axis_pair_not_first_cylinder(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("best_cylindrical_face_pair", source)
        self.assertIn("face_cylinder_axis", source)
        self.assertIn("axis_distance", source)
        self.assertIn("face_pair_axis_distance_m", source)
        self.assertNotIn('left_face = first_face(left, "IsCylinder")', source)
        self.assertNotIn('right_face = first_face(right, "IsCylinder")', source)

    def test_distance_mate_preserves_current_layout_distance_instead_of_forcing_display_clearance(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("mate_distance = actual_distance", source)
        self.assertIn("requested_selector_distance_m", source)
        self.assertIn("preserved_layout_distance_m", source)
        self.assertNotIn("add_selected_mate(asm, name, 5, distance)", source)


    def test_primary_layout_fix_is_not_used_to_mask_unsolved_mates(self):
        source = SCRIPT.read_text(encoding="utf-8")
        construct = source[source.index("def construct_live_fixture"):]
        self.assertIn("fix_primary_design_layout_components", source)
        self.assertLess(construct.index("add_shaper_mate_network(asm, component_objs)"), construct.index("design_layout_fixed_components = fix_primary_design_layout_components(sw, asm, component_objs)"))
        self.assertIn("validate_design_layout_fixed_components", source)

    def test_live_script_writes_shaper_assembly_contract_artifact(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("complete_shaper_assembly_contract.json", source)
        self.assertIn("build_shaper_assembly_contract()", source)
        self.assertIn('result["assembly_contract"]', source)

    def test_builder_runs_hidden_and_has_mate_and_interference_callbacks(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("sw.Visible = False", source)
        self.assertIn("AddMate5", source)
        self.assertIn("add_bed_column_distance_mate", source)
        self.assertIn("run_assembly_callbacks", source)
        self.assertIn("InterferenceDetectionManager", source)
        self.assertIn("validate_live_result", source)

    def test_interference_callback_records_component_pair_evidence(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn('"pairs"', source)
        self.assertIn("GetComponents", source)
        self.assertIn("Components", source)

    def test_validate_live_result_rejects_bad_callbacks_mates_and_interference(self):
        base = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": sample_shaper_mates(self.module),
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "inspect": self.module.sample_expected_shaper_inspect_evidence(),
            "model_understanding": self.module.sample_expected_shaper_understanding_evidence(),
            "part_feature_evidence": sample_part_feature_evidence(self.module),
            "design_layout_fixed_components": sample_design_layout_fixed_components(self.module),
        }
        self.assertTrue(self.module.validate_live_result(base)["ok"])

        bad_mate = dict(base)
        bad_mates = sample_shaper_mates(self.module)
        bad_mates[0] = dict(bad_mates[0], semantic_pair=["ram", "tool"])
        bad_mate["mates"] = bad_mates
        self.assertIn(f"mate_semantics:{bad_mates[0]['name']}", self.module.validate_live_result(bad_mate)["failed"])

        bad_mate_error = dict(base)
        bad_error_mates = sample_shaper_mates(self.module)
        bad_error_mates[0] = dict(bad_error_mates[0], mate_error=4)
        bad_mate_error["mates"] = bad_error_mates
        self.assertIn(f"mate_error:{bad_error_mates[0]['name']}", self.module.validate_live_result(bad_mate_error)["failed"])

        bad_mate_selection = dict(base)
        bad_selection_mates = sample_shaper_mates(self.module)
        bad_selection_mates[0] = dict(bad_selection_mates[0], selected_entities=1)
        bad_mate_selection["mates"] = bad_selection_mates
        self.assertIn(f"mate_selection:{bad_selection_mates[0]['name']}", self.module.validate_live_result(bad_mate_selection)["failed"])

        bad_mate_components = dict(base)
        bad_component_mates = sample_shaper_mates(self.module)
        bad_component_mates[0]["selection_guard"] = dict(bad_component_mates[0]["selection_guard"], component_pair=["wrong-1", "column_frame_with_window-1"])
        bad_mate_components["mates"] = bad_component_mates
        self.assertIn(f"mate_components:{bad_component_mates[0]['name']}", self.module.validate_live_result(bad_mate_components)["failed"])

        bad_interference = dict(base)
        bad_interference["callbacks"] = {"mass": {"available": True, "mass_kg": 1.0}, "interference": {"available": True, "count": 1}}
        self.assertIn("interference_clearance", self.module.validate_live_result(bad_interference)["failed"])

        bad_mass = dict(base)
        bad_mass["callbacks"] = {"mass": {"available": False}, "interference": {"available": True, "count": 0}}
        self.assertIn("mass_callback", self.module.validate_live_result(bad_mass)["failed"])

        bad_lock = dict(base)
        bad_lock["post_cleanup"] = {"locked_files": [], "lock_files": ["~$bullhead_shaper_complete.SLDASM"]}
        self.assertIn("post_cleanup_single_session", self.module.validate_live_result(bad_lock)["failed"])


    def test_live_builder_preflight_checks_requested_output_dir_locks(self):
        calls = []
        original = self.module.preflight_solidworks_runtime
        try:
            self.module.preflight_solidworks_runtime = lambda **kwargs: (calls.append(kwargs) or {"ok": False, "failed": ["solidworks_stale_lock_files"]})
            result = self.module.construct_live_fixture(
                self.module.build_complete_shaper_spec(),
                Path("tools/solidworks_codex/live_fixture/custom_shaper"),
                Path("tools/solidworks_codex/reports/custom_shaper"),
                force=False,
            )
        finally:
            self.module.preflight_solidworks_runtime = original
        self.assertFalse(result["ok"])
        self.assertEqual(Path("tools/solidworks_codex/live_fixture/custom_shaper"), calls[0]["out_dir"])

    def test_runtime_health_guard_raises_before_next_heavy_step_when_solidworks_is_unhealthy(self):
        high = [{"name": "SLDWORKS", "id": 77, "private_memory_bytes": 2_600_000_000, "responding": False}]
        with self.assertRaisesRegex(RuntimeError, "SolidWorks unhealthy before insert_component"):
            self.module.assert_solidworks_runtime_healthy(
                "insert_component",
                process_snapshots=high,
                max_private_memory_bytes=1_900_000_000,
            )


    def test_runtime_health_guard_allows_responsive_heavy_fixture_session_by_default(self):
        snapshots = [{"name": "SLDWORKS", "id": 78, "private_memory_bytes": 4_500_000_000, "responding": True}]

        self.module.assert_solidworks_runtime_healthy("insert_component", process_snapshots=snapshots)


    def test_live_builder_records_attach_failure_report_and_cleanup_state(self):
        spec = self.module.build_complete_shaper_spec()
        with TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "fixture"
            reports_dir = Path(tmp) / "reports"
            original_preflight = self.module.preflight_solidworks_runtime
            original_attach = self.module.attach_solidworks
            try:
                self.module.preflight_solidworks_runtime = lambda **kwargs: {"ok": True, "failed": []}
                self.module.attach_solidworks = lambda: (_ for _ in ()).throw(RuntimeError("COM dispatch failed"))
                result = self.module.construct_live_fixture(spec, out_dir, reports_dir, force=True)
            finally:
                self.module.preflight_solidworks_runtime = original_preflight
                self.module.attach_solidworks = original_attach
            saved = json.loads((reports_dir / "complete_shaper_build.json").read_text(encoding="utf-8"))
        self.assertFalse(result["ok"])
        self.assertEqual("attach_solidworks", result["stage"])
        self.assertIn("RuntimeError: COM dispatch failed", result["error"])
        self.assertIn("traceback", result)
        self.assertIn("post_cleanup", result)
        self.assertEqual(result["stage"], saved["stage"])


    def test_post_cleanup_waits_for_solidworks_to_release_generated_files(self):
        calls = []
        snapshots = iter([{"locked_files": ["part.SLDPRT"], "lock_files": [], "checked_files": ["part.SLDPRT"]}, {"locked_files": [], "lock_files": [], "checked_files": ["part.SLDPRT"]}])
        result = self.module.wait_for_generated_files_unlocked(
            Path("tools/solidworks_codex/live_fixture/shaper_machine_v5"),
            probe=lambda path: (calls.append(path) or next(snapshots)),
            sleep=lambda seconds: None,
            attempts=2,
        )
        self.assertEqual([], result["locked_files"])
        self.assertEqual(2, result["attempts"])
        self.assertEqual(2, len(calls))


    def test_live_inspect_resolves_and_rebuilds_assembly_before_sampling(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("prepare_assembly_for_inspect(asm)", source)
        self.assertIn("ResolveAllLightWeightComponents", source)
        self.assertLess(source.index("prepare_assembly_for_inspect(asm)"), source.index("inspect_mod.inspect_model_object("))


if __name__ == "__main__":
    unittest.main()
