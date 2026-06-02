import importlib.util
import sys
import unittest
from pathlib import Path

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
        self.assertIn("eccentric_pin_hole", features_by_part["bull_gear_crank_disk"])
        self.assertIn("lightening_hole_pattern", features_by_part["bull_gear_crank_disk"])
        self.assertIn("bolt_hole_pattern", features_by_part["clapper_tool_head"])
        self.assertIn("t_slot_cut", features_by_part["work_table_with_t_slots"])
        self.assertIn("hex_bolt", features_by_part["fastener_set_m6"])
        self.assertIn("washer", features_by_part["washer_set"])

    def test_validation_manifest_rejects_plain_block_stack(self):
        model = self.module.build_complete_shaper_spec()
        manifest = self.module.spec_to_manifest(model)
        self.assertEqual(manifest["quality_target"], "display_grade_mechanical_model")
        self.assertGreaterEqual(manifest["feature_counts"]["cut"], 18)
        self.assertGreaterEqual(manifest["feature_counts"]["hole"], 20)
        self.assertGreaterEqual(manifest["feature_counts"]["slot"], 6)
        self.assertGreaterEqual(manifest["feature_counts"]["fastener"], 12)
        self.assertIn("no_plain_block_stack", manifest["acceptance_rules"])
        self.assertIn("visible_holes_slots_and_fasteners", manifest["acceptance_rules"])
        self.assertIn("recognizable_bullhead_shaper_silhouette", manifest["acceptance_rules"])

    def test_live_builder_fails_fast_for_missing_cut_features(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("FeatureCut3 returned None", source)
        self.assertIn("CreateCornerRectangle returned None", source)
        self.assertIn("FeatureExtrusion2 returned None", source)
        self.assertIn("select_new_cut_sketch", source)

    def test_live_builder_places_visible_detail_instances(self):
        detail_placements = self.module.detail_instance_placements()
        self.assertGreaterEqual(len(detail_placements["fastener_set_m6"]), 18)
        self.assertGreaterEqual(len(detail_placements["washer_set"]), 12)
        self.assertGreaterEqual(len(detail_placements["oil_cups"]), 4)
        self.assertGreaterEqual(self.module.expected_assembly_component_minimum(), 58)

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

    def test_live_outputs_are_separate_from_old_failed_fixture(self):
        model = self.module.build_complete_shaper_spec()
        self.assertIn("shaper_machine_v4", model.output_dir)
        self.assertTrue(model.assembly_file.endswith("bullhead_shaper_complete.SLDASM"))
        self.assertNotIn("shaper_quick_return_validation", model.assembly_file)


if __name__ == "__main__":
    unittest.main()
