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
                "selection_count_before_mate": 2,
                "component_pair": [f"{expected['semantic_pair'][0]}-1", f"{expected['semantic_pair'][1]}-1"],
            },
        })
    return mates


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

    def test_live_builder_places_visible_exploded_detail_instances(self):
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
                "selection_guard": {"cleared_selection_count": 0, "selection_count_before_mate": 2, "component_pair": ["base_plate-1", "cover_plate-1"]},
            },
            {
                "name": "Shaft_Bearing_Concentric",
                "ok": True,
                "kind": "concentric",
                "semantic_pair": ["drive_shaft", "bearing_block"],
                "components": ["drive_shaft-1", "bearing_block-1"],
                "selected_entities": 2,
                "selection_guard": {"cleared_selection_count": 0, "selection_count_before_mate": 2, "component_pair": ["drive_shaft-1", "bearing_block-1"]},
            },
        ]
        self.assertEqual([], self.module.validate_semantic_mate_network(mates, contract))

        broken = list(mates)
        broken[1] = dict(broken[1], components=["wrong-1", "bearing_block-1"])
        self.assertIn("mate_components:Shaft_Bearing_Concentric", self.module.validate_semantic_mate_network(broken, contract))

    def test_complete_shaper_requires_semantic_mate_network_not_single_distance_mate(self):
        expected = self.module.expected_shaper_mate_contract()
        self.assertGreaterEqual(len(expected), 4)
        self.assertIn("Bed_Column_Distance_Mate", expected)
        self.assertIn("Ram_LeftWay_Guidance_Distance_Mate", expected)
        self.assertIn("ToolHead_Ram_Distance_Mate", expected)
        self.assertIn("Table_CrossSlide_Distance_Mate", expected)
        self.assertIn("BullGear_CrankShaft_Concentric_Mate", expected)
        self.assertIn("Crank_Link_Concentric_Mate", expected)
        self.assertIn("Rocker_Pivot_Concentric_Mate", expected)
        self.assertGreaterEqual(len(expected), 7)

        spatial = self.module.expected_shaper_spatial_contract()
        self.assertIn("structural_stack", spatial)
        self.assertIn("ram_guidance", spatial)
        self.assertIn("tool_head", spatial)
        self.assertIn("quick_return_drive", spatial)
        self.assertIn("ram_with_dovetail_and_tool_mount", spatial["ram_guidance"])
        self.assertIn("single_point_cutting_tool", spatial["tool_head"])

        self.assertEqual(expected["Ram_LeftWay_Guidance_Distance_Mate"]["semantic_pair"], ["ram_with_dovetail_and_tool_mount", "left_dovetail_way"])
        self.assertEqual(expected["ToolHead_Ram_Distance_Mate"]["semantic_pair"], ["clapper_tool_head", "ram_with_dovetail_and_tool_mount"])
        self.assertEqual(expected["Table_CrossSlide_Distance_Mate"]["semantic_pair"], ["work_table_with_t_slots", "table_cross_slide"])

        only_one = {
            "ok": True,
            "part_count": 24,
            "component_count": self.module.expected_assembly_component_minimum(),
            "layout": {"ok": True},
            "mates": [{"name": "Shaper_Distance_Mate", "ok": True, "mate_error": 1, "semantic_pair": ["cast_bed_with_t_slots", "column_frame_with_window"]}],
            "callbacks": {"mass": {"available": True, "mass_kg": 14.81}, "interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
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
        }
        self.assertTrue(self.module.validate_live_result(base)["ok"])

        missing = dict(base)
        missing["mates"] = [
            mate for mate in sample_shaper_mates(self.module)
            if mate["name"] not in {
                "Ram_LeftWay_Guidance_Distance_Mate",
                "ToolHead_Ram_Distance_Mate",
                "Table_CrossSlide_Distance_Mate",
            }
        ]
        validation = self.module.validate_live_result(missing)
        self.assertFalse(validation["ok"])
        self.assertIn("mate_network", validation["failed"])

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
        self.assertTrue(self.module.validate_live_result(inspected)["ok"])

        bad = dict(inspected)
        bad["model_understanding"] = {"ok": True, "baseline": {"inventory": {"component_count": 58, "floating_components": []}}, "cad_evidence_graph": {"spatial_evidence": {"near_or_overlap_pairs": []}}}
        validation = self.module.validate_live_result(bad)
        self.assertFalse(validation["ok"])
        self.assertIn("model_understanding:spatial_contract", validation["failed"])

    def test_model_understanding_accepts_contract_member_inventory_when_near_pairs_are_sparse(self):
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
        self.assertEqual([], self.module.validate_model_understanding_evidence(understanding))

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
            self.assertEqual(contract[name]["expected_origin_m"], self.module.placements_for(self.module.build_complete_shaper_spec())[name])
            self.assertLessEqual(contract[name]["tolerance_m"], 0.003)


    def test_builder_runs_hidden_and_has_mate_and_interference_callbacks(self):
        source = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("sw.Visible = False", source)
        self.assertIn("AddMate5", source)
        self.assertIn("add_bed_column_distance_mate", source)
        self.assertIn("run_assembly_callbacks", source)
        self.assertIn("InterferenceDetectionManager", source)
        self.assertIn("validate_live_result", source)

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
