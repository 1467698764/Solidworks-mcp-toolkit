import importlib.util
import inspect
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
import json

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_live_validation_gate.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sw_live_validation_gate", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load live validation gate module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_shaper_builder():
    script = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_create_complete_shaper_fixture.py"
    spec = importlib.util.spec_from_file_location("sw_create_complete_shaper_fixture_for_live_gate_test", script)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load shaper builder module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def with_readbacks(context):
    for part in context.values():
        for op in part["operations"].values():
            op["selection_guard"] = {
                "active_title": part.get("active_title"),
                "cleared_selection_count": 0,
                "selected_sketch": op["sketch"],
                "selection_count_before_feature": 1,
            }
            op["readback"] = {
                "source": "reopened_feature_tree",
                "sketch": op["sketch"],
                "feature_type": op["feature_type"],
                "geometry": dict(op["geometry"]),
            }
    return context


def capability_mates():
    return [
        {
            "name": "Concentric_Mate",
            "ok": True,
            "components": ["revolve_boss_part-1", "revolve_cut_part-1"],
            "selected_entities": 2,
            "selection_guard": {
                "cleared_selection_count": 0,
                "selection_count_before_mate": 2,
                "component_pair": ["revolve_boss_part-1", "revolve_cut_part-1"],
            },
        },
        {
            "name": "Distance_Mate",
            "ok": True,
            "components": ["extrude_cut_plate-1", "editable_dimension_plate-1"],
            "selected_entities": 2,
            "selection_guard": {
                "cleared_selection_count": 0,
                "selection_count_before_mate": 2,
                "component_pair": ["extrude_cut_plate-1", "editable_dimension_plate-1"],
            },
        },
    ]


def capability_assembly_inspect():
    return {
        "active_document": {
            "type": "assembly",
            "component_count_sampled": 4,
            "components": [
                {"name2": "extrude_cut_plate-1", "transform": {"origin_m": [0.00, 0.00, -0.006]}},
                {"name2": "revolve_boss_part-1", "transform": {"origin_m": [0.12, 0.00, 0.00]}},
                {"name2": "revolve_cut_part-1", "transform": {"origin_m": [0.12, 0.075, 0.00]}},
                {"name2": "editable_dimension_plate-1", "transform": {"origin_m": [0.00, 0.10, 0.026]}},
            ],
            "mate_like_features": [
                {"name": "Concentric_Mate", "type": "MateConcentric", "components": ["revolve_boss_part-1", "revolve_cut_part-1"], "suppressed": False},
                {"name": "Distance_Mate", "type": "MateDistanceDim", "components": ["extrude_cut_plate-1", "editable_dimension_plate-1"], "suppressed": False},
            ],
        }
    }


def shaper_mates():
    mates = []
    for name, expected in load_shaper_builder().expected_shaper_mate_contract().items():
        pair = list(expected["semantic_pair"])
        components = [f"{pair[0]}-1", f"{pair[1]}-1"]
        mates.append({
            "name": name,
            "kind": expected["type"],
            "semantic_pair": pair,
            "components": components,
            "selected_entities": 2,
            "selection_guard": {"cleared_selection_count": 0, "selection_count_before_mate": 2, "component_pair": components},
            "ok": True,
        })
    return mates


def shaper_primary_components():
    return [
        {"name2": f"{name}-1", "transform": {"origin_m": list(origin)}, "suppressed": False}
        for name, origin in load_module()._expected_shaper_component_origins().items()
    ]


def shaper_inspect_evidence():
    builder = load_shaper_builder()
    return {"active_document": {"type": "assembly", "component_count_sampled": 58, "components": shaper_primary_components(), "mate_like_features": [
        {"name": name, "type": builder.expected_inspect_mate_type(expected["type"]), "components": [f"{expected['semantic_pair'][0]}-1", f"{expected['semantic_pair'][1]}-1"], "suppressed": False}
        for name, expected in builder.expected_shaper_mate_contract().items()
    ]}}


def shaper_understanding_evidence():
    return {"baseline": {"inventory": {"component_count": 58}}, "cad_evidence_graph": {"spatial_evidence": {"near_or_overlap_pairs": [
        {"a": f"{left}-1", "b": f"{right}-1", "relation": "near", "gap_m": 0.002}
        for left, right in load_shaper_builder().expected_shaper_functional_connection_contract()
    ]}}}


def shaper_part_feature_evidence():
    return {
        part_name: {"ok": True, "features": [{"name": name, "type": "Feature"} for name in feature_names]}
        for part_name, feature_names in load_shaper_builder().expected_live_feature_names().items()
    }


class LiveValidationGateSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()


    def test_gate_contract_runs_minimal_session_smoke_before_heavy_builds(self):
        contract = self.module.build_gate_contract()
        names = [check.name for check in contract.checks]
        self.assertLess(names.index("live_session_smoke"), names.index("live_capability_suite"))
        smoke = next(check for check in contract.checks if check.name == "live_session_smoke")
        self.assertIn("sw_live_session_smoke.py", " ".join(smoke.command))
        self.assertIn("single SolidWorks session", smoke.purpose)

    def test_gate_contract_requires_capability_suite_and_complete_shaper(self):
        contract = self.module.build_gate_contract()
        names = [check.name for check in contract.checks]
        self.assertEqual(names, ["live_session_smoke", "live_capability_suite", "complete_shaper_v5"])
        by_name = {check.name: check for check in contract.checks}
        self.assertIn("sw_live_capability_suite.py", by_name["live_capability_suite"].command[1])
        self.assertIn("sw_create_complete_shaper_fixture.py", by_name["complete_shaper_v5"].command[1])
        for check in contract.checks:
            self.assertIn("--force", check.command)
            self.assertTrue(check.report_json.endswith(".json"))

    def test_shaper_gate_reuses_builder_origin_contract_without_coordinate_copy(self):
        source = inspect.getsource(self.module._expected_shaper_component_origins)
        self.assertIn("expected_shaper_placement_contract", source)
        self.assertNotIn('"cast_bed_with_t_slots": (0.0, 0.0, -0.0275)', source)

    def test_shaper_gate_loads_builder_contract_without_repo_root_on_syspath(self):
        original = list(sys.path)
        try:
            sys.path[:] = [
                entry for entry in sys.path
                if entry and Path(entry).resolve() != ROOT
            ]
            origins = self.module._expected_shaper_component_origins()
        finally:
            sys.path[:] = original

        self.assertIn("cast_bed_with_t_slots", origins)

    def test_shaper_gate_component_origin_contract_matches_builder_placements(self):
        builder_script = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_create_complete_shaper_fixture.py"
        spec = importlib.util.spec_from_file_location("sw_create_complete_shaper_fixture_for_gate_test", builder_script)
        builder = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = builder
        spec.loader.exec_module(builder)
        builder_contract = builder.expected_shaper_placement_contract()
        gate_contract = self.module._expected_shaper_component_origins()

        self.assertEqual(set(builder_contract), set(gate_contract))
        for name, gate_origin in gate_contract.items():
            self.assertEqual(builder_contract[name]["expected_origin_m"], gate_origin)

    def test_validate_gate_rejects_missing_or_failed_reports(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "missing.json"
            failed = root / "failed.json"
            failed.write_text(json.dumps({"ok": False, "validation": {"failed": ["mass_callback"]}}), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("missing_check", missing, ("ok",)),
                self.module.ReportExpectation("failed_check", failed, ("ok",)),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("missing_report:missing_check", result["failed"])
        self.assertIn("report_not_ok:failed_check", result["failed"])


    def test_validate_gate_rejects_weak_shaper_evidence_even_when_report_says_ok(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            weak = root / "complete_shaper_build.json"
            weak.write_text(json.dumps({"ok": True, "validation": {"ok": True, "failed": []}}), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("complete_shaper_v5", weak, ("ok",), self.module.shaper_v5_strict_checks()),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("strict:complete_shaper_v5:part_count", result["failed"])
        self.assertIn("strict:complete_shaper_v5:component_count", result["failed"])
        self.assertIn("strict:complete_shaper_v5:interference_clearance", result["failed"])
        self.assertIn("strict:complete_shaper_v5:post_cleanup_single_session", result["failed"])

    def test_validate_gate_rejects_weak_capability_suite_native_artifacts_and_callbacks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            weak = root / "live_capability_suite.json"
            weak.write_text(json.dumps({
                "ok": True,
                "native_artifacts": {"primary": True},
                "validation": {"ok": True, "failed_capabilities": []},
            }), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("live_capability_suite", weak, ("ok", "native_artifacts.primary"), self.module.capability_suite_strict_checks()),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("strict:live_capability_suite:native_solidworks_artifacts", result["failed"])
        self.assertIn("strict:live_capability_suite:interference_callback", result["failed"])
        self.assertIn("strict:live_capability_suite:assembly_mates_persisted", result["failed"])
        self.assertIn("strict:live_capability_suite:open_existing_modify_reopen", result["failed"])
        self.assertIn("strict:live_capability_suite:operation_context_guards", result["failed"])

    def test_operation_context_strict_check_rejects_null_selection_guard_without_crashing(self):
        report = {
            "operation_context": with_readbacks({
                "extrude": {"document": "extrude_cut_plate.SLDPRT", "active_title": "Part1", "saved_path": "C:/generated/extrude_cut_plate.SLDPRT", "operations": {
                    "Body_Plate": {"sketch": "Sketch1", "profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"},
                    "Round_Through_Hole": {"sketch": "Sketch2", "profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"},
                    "Rectangular_Window_Cut": {"sketch": "Sketch3", "profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"},
                }},
                "revolve": {"document": "revolve_boss_part.SLDPRT", "active_title": "Part2", "saved_path": "C:/generated/revolve_boss_part.SLDPRT", "operations": {
                    "Revolve_Boss_Profile": {"sketch": "Sketch1", "profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"},
                }},
                "revolve_cut": {"document": "revolve_cut_part.SLDPRT", "active_title": "Part3", "saved_path": "C:/generated/revolve_cut_part.SLDPRT", "operations": {
                    "Revolve_Boss_Profile": {"sketch": "Sketch1", "profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"},
                    "Revolve_Cut_Bore": {"sketch": "Sketch2", "profile": "closed_cut_profile_with_centerline", "geometry": {"lines": 4, "circles": 0, "centerlines": 1}, "feature_type": "RevCut", "api": "FeatureRevolveCut2"},
                }},
                "editable": {"document": "editable_dimension_plate.SLDPRT", "active_title": "Part4", "saved_path": "C:/generated/editable_dimension_plate.SLDPRT", "operations": {
                    "Body_Editable_Plate": {"sketch": "Sketch1", "profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"},
                    "Edited_Sketch_Dimension": {"sketch": "Sketch2", "profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3", "dimension": "D1@Edited_Sketch_Dimension"},
                }},
            })
        }
        report["operation_context"]["editable"]["operations"]["Edited_Sketch_Dimension"]["selection_guard"]["selection_count_before_feature"] = None
        self.assertTrue(self.module._strict_check_failed(report, "operation_context_guards"))



    def test_session_smoke_strict_check_rejects_second_session_or_lock_leak(self):
        good = {"ok": True, "started_second_session": False, "part_inspect": {"active_document": {"type": "part"}}, "assembly_inspect": {"active_document": {"type": "assembly", "component_count_sampled": 2, "mate_like_features": [{"name": "Smoke_Distance_Mate", "components": ["session_smoke_left-1", "session_smoke_right-1"]}]}}, "callbacks": {"interference": {"available": True, "count": 0}}, "post_cleanup": {"locked_files": [], "lock_files": []}, "validation": {"ok": True, "failed": []}}
        self.assertFalse(self.module._strict_check_failed(good, "single_session_smoke"))
        bad = dict(good, started_second_session=True)
        self.assertTrue(self.module._strict_check_failed(bad, "single_session_smoke"))
        bad_asm = dict(good, assembly_inspect={"active_document": {"type": "assembly", "component_count_sampled": 0, "mate_like_features": []}})
        self.assertTrue(self.module._strict_check_failed(bad_asm, "single_session_smoke"))
        bad_lock = dict(good, post_cleanup={"locked_files": ["session_smoke.SLDPRT"], "lock_files": []})
        self.assertTrue(self.module._strict_check_failed(bad_lock, "single_session_smoke"))
        bad_mate_details = dict(good, assembly_inspect={"active_document": {"type": "assembly", "component_count_sampled": 2, "mate_like_features": [{"name": "Smoke_Distance_Mate"}]}})
        self.assertTrue(self.module._strict_check_failed(bad_mate_details, "single_session_smoke"))

    def test_default_report_expectations_use_strict_live_checks(self):
        contract = self.module.build_gate_contract()
        expectations = {item.name: item for item in self.module.report_expectations(contract)}
        self.assertIn("native_solidworks_artifacts", expectations["live_capability_suite"].strict_checks)
        self.assertIn("assembly_mates_persisted", expectations["live_capability_suite"].strict_checks)
        self.assertIn("open_existing_modify_reopen", expectations["live_capability_suite"].strict_checks)
        self.assertIn("operation_context_guards", expectations["live_capability_suite"].strict_checks)
        self.assertIn("assembly_component_placements", expectations["live_capability_suite"].strict_checks)
        self.assertIn("part_count", expectations["complete_shaper_v5"].strict_checks)
        self.assertIn("component_count", expectations["complete_shaper_v5"].strict_checks)
        self.assertIn("mate_semantics", expectations["complete_shaper_v5"].strict_checks)
        self.assertIn("part_feature_evidence", expectations["complete_shaper_v5"].strict_checks)

    def test_validate_gate_accepts_strict_live_evidence_and_native_artifacts(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = root / "live_capability_suite.json"
            shaper = root / "complete_shaper_build.json"
            suite.write_text(json.dumps({
                "ok": True,
                "native_artifacts": {"assembly_exists": True, "part_count": 4, "primary": True},
                "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
                "assembly_result": {"component_count": 4, "mates": capability_mates()},
                "assembly_inspect": capability_assembly_inspect(),
                "reopen_modify": {
                    "dimension": "D1@Edited_Sketch_Dimension",
                    "after_reopen_m": 0.028,
                    "persisted": True,
                    "save": {"ok": True, "errors": 0, "warnings": 0},
                },
                "operation_context": with_readbacks({
                    "extrude": {"document": "extrude_cut_plate.SLDPRT", "active_title": "闆朵欢1", "saved_path": "C:/generated/extrude_cut_plate.SLDPRT", "operations": {
                        "Body_Plate": {"sketch": "Sketch1", "profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"},
                        "Round_Through_Hole": {"sketch": "Sketch2", "profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"},
                        "Rectangular_Window_Cut": {"sketch": "Sketch3", "profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3"},
                    }},
                    "revolve": {"document": "revolve_boss_part.SLDPRT", "active_title": "闆朵欢2", "saved_path": "C:/generated/revolve_boss_part.SLDPRT", "operations": {
                        "Revolve_Boss_Profile": {"sketch": "Sketch1", "profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"},
                    }},
                    "revolve_cut": {"document": "revolve_cut_part.SLDPRT", "active_title": "闆朵欢3", "saved_path": "C:/generated/revolve_cut_part.SLDPRT", "operations": {
                        "Revolve_Boss_Profile": {"sketch": "Sketch1", "profile": "closed_revolve_profile_with_centerline", "geometry": {"lines": 5, "circles": 0, "centerlines": 1}, "feature_type": "Revolution", "api": "FeatureRevolve2"},
                        "Revolve_Cut_Bore": {"sketch": "Sketch2", "profile": "closed_cut_profile_with_centerline", "geometry": {"lines": 4, "circles": 0, "centerlines": 1}, "feature_type": "RevCut", "api": "FeatureRevolveCut2"},
                    }},
                    "editable": {"document": "editable_dimension_plate.SLDPRT", "active_title": "闆朵欢4", "saved_path": "C:/generated/editable_dimension_plate.SLDPRT", "operations": {
                        "Body_Editable_Plate": {"sketch": "Sketch1", "profile": "rectangle", "geometry": {"lines": 4, "circles": 0, "centerlines": 0}, "feature_type": "Extrusion", "api": "FeatureExtrusion2"},
                        "Edited_Sketch_Dimension": {"sketch": "Sketch2", "profile": "circle", "geometry": {"lines": 0, "circles": 1, "centerlines": 0}, "feature_type": "ICE", "api": "FeatureCut3", "dimension": "D1@Edited_Sketch_Dimension"},
                    }},
                }),
                "callbacks": {"interference": {"available": True, "count": 0}, "mass": {"available": True, "mass_kg": 0.2}},
                "post_cleanup": {"locked_files": []},
                "validation": {"ok": True, "failed_capabilities": []},
            }), encoding="utf-8")
            shaper.write_text(json.dumps({
                "ok": True,
                "part_count": 24,
                "component_count": 58,
                "mates": shaper_mates(),
                "callbacks": {"interference": {"available": True, "count": 0}, "mass": {"available": True, "mass_kg": 15.125546510666322}},
                "part_feature_evidence": shaper_part_feature_evidence(),
                "inspect": shaper_inspect_evidence(),
                "model_understanding": shaper_understanding_evidence(),
                "post_cleanup": {"locked_files": [], "lock_files": []},
                "validation": {"ok": True, "failed": []},
            }), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("live_capability_suite", suite, ("ok", "native_artifacts.primary"), self.module.capability_suite_strict_checks()),
                self.module.ReportExpectation("complete_shaper_v5", shaper, ("ok",), self.module.shaper_v5_strict_checks()),
            ])
        self.assertTrue(result["ok"], result)

    def test_shaper_gate_rejects_mates_without_selection_and_component_evidence(self):
        report = {
            "mates": shaper_mates(),
        }
        self.assertFalse(self.module._strict_check_failed(report, "mate_semantics"))

        report["mates"][0]["selected_entities"] = 1
        self.assertTrue(self.module._strict_check_failed(report, "mate_semantics"))

        report["mates"] = shaper_mates()
        report["mates"][1]["selection_guard"]["component_pair"] = ["wrong-1", "crank_center_shaft-1"]
        self.assertTrue(self.module._strict_check_failed(report, "mate_semantics"))


    def test_shaper_gate_requires_guidance_toolhead_and_table_mates(self):
        report = {"mates": shaper_mates()}
        self.assertFalse(self.module._strict_check_failed(report, "mate_semantics"))

        report["mates"] = [
            mate for mate in shaper_mates()
            if mate["name"] not in {
                "Ram_LeftWay_Guidance_Distance_Mate",
                "ToolHead_Ram_Distance_Mate",
                "Table_CrossSlide_Distance_Mate",
            }
        ]
        self.assertTrue(self.module._strict_check_failed(report, "mate_semantics"))

    def test_capability_gate_rejects_mates_without_selection_and_component_evidence(self):
        report = {
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
            "assembly_result": {"component_count": 4, "mates": capability_mates()},
            "assembly_inspect": capability_assembly_inspect(),
        }
        self.assertFalse(self.module._strict_check_failed(report, "assembly_mates_persisted"))

        report["assembly_result"]["mates"][0]["selected_entities"] = 1
        self.assertTrue(self.module._strict_check_failed(report, "assembly_mates_persisted"))

        report["assembly_result"]["mates"] = capability_mates()
        report["assembly_result"]["mates"][1]["selection_guard"]["component_pair"] = ["wrong-1", "editable_dimension_plate-1"]
        self.assertTrue(self.module._strict_check_failed(report, "assembly_mates_persisted"))

        report["assembly_result"]["mates"] = capability_mates()
        report["assembly_inspect"]["active_document"]["mate_like_features"][0]["components"] = ["wrong-1", "revolve_cut_part-1"]
        self.assertTrue(self.module._strict_check_failed(report, "assembly_mates_persisted"))


    def test_capability_gate_rejects_missing_or_far_component_placement_readback(self):
        report = {"assembly_inspect": capability_assembly_inspect()}
        self.assertFalse(self.module._strict_check_failed(report, "assembly_component_placements"))

        del report["assembly_inspect"]["active_document"]["components"][0]["transform"]
        self.assertTrue(self.module._strict_check_failed(report, "assembly_component_placements"))

        report = {"assembly_inspect": capability_assembly_inspect()}
        report["assembly_inspect"]["active_document"]["components"][2]["transform"]["origin_m"] = [9.0, 9.0, 9.0]
        self.assertTrue(self.module._strict_check_failed(report, "assembly_component_placements"))

    def test_shaper_strict_inspect_rejects_same_named_mates_without_details(self):
        report = {
            "ok": True,
            "part_count": 24,
            "component_count": 58,
            "mates": [
                {"name": "Bed_Column_Distance_Mate", "kind": "distance", "semantic_pair": ["cast_bed_with_t_slots", "column_frame_with_window"], "ok": True},
                {"name": "BullGear_CrankShaft_Concentric_Mate", "kind": "concentric", "semantic_pair": ["bull_gear_crank_disk", "crank_center_shaft"], "ok": True},
                {"name": "Crank_Link_Concentric_Mate", "kind": "concentric", "semantic_pair": ["eccentric_crank_pin", "ram_drive_link"], "ok": True},
                {"name": "Rocker_Pivot_Concentric_Mate", "kind": "concentric", "semantic_pair": ["slotted_rocker_arm", "rocker_pivot_shaft"], "ok": True},
            ],
            "callbacks": {"interference": {"available": True, "count": 0}, "mass": {"available": True, "mass_kg": 15.0}},
            "inspect": {"active_document": {"type": "assembly", "component_count_sampled": 58, "components": shaper_primary_components(), "mate_like_features": [
                {"name": "Bed_Column_Distance_Mate"},
                {"name": "BullGear_CrankShaft_Concentric_Mate"},
                {"name": "Crank_Link_Concentric_Mate"},
                {"name": "Rocker_Pivot_Concentric_Mate"},
            ]}},
            "model_understanding": shaper_understanding_evidence(),
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "validation": {"ok": True, "failed": []},
        }
        self.assertTrue(self.module._strict_check_failed(report, "inspect_model_understand"))

    def test_shaper_strict_inspect_rejects_missing_or_far_component_placement_readback(self):
        report = {
            "ok": True,
            "part_count": 24,
            "component_count": 58,
            "mates": shaper_mates(),
            "callbacks": {"interference": {"available": True, "count": 0}, "mass": {"available": True, "mass_kg": 15.0}},
            "inspect": shaper_inspect_evidence(),
            "model_understanding": shaper_understanding_evidence(),
            "post_cleanup": {"locked_files": [], "lock_files": []},
            "validation": {"ok": True, "failed": []},
        }
        self.assertFalse(self.module._strict_check_failed(report, "inspect_model_understand"))

        del report["inspect"]["active_document"]["components"][0]["transform"]
        self.assertTrue(self.module._strict_check_failed(report, "inspect_model_understand"))

        report["inspect"] = shaper_inspect_evidence()
        report["inspect"]["active_document"]["components"][4]["transform"]["origin_m"] = [4.0, 4.0, 4.0]
        self.assertTrue(self.module._strict_check_failed(report, "inspect_model_understand"))

    def test_validate_gate_rejects_reopen_persistence_when_save3_failed(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            suite = root / "live_capability_suite.json"
            suite.write_text(json.dumps({
                "ok": True,
                "native_artifacts": {"assembly_exists": True, "part_count": 4, "primary": True},
                "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
                "reopen_modify": {
                    "dimension": "D1@Edited_Sketch_Dimension",
                    "after_reopen_m": 0.028,
                    "persisted": True,
                    "save": {"ok": False, "errors": 8192, "warnings": 0},
                },
                "callbacks": {"interference": {"available": True, "count": 0}, "mass": {"available": True, "mass_kg": 0.2}},
                "post_cleanup": {"locked_files": []},
                "validation": {"ok": True, "failed_capabilities": []},
            }), encoding="utf-8")
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("live_capability_suite", suite, ("ok", "native_artifacts.primary"), self.module.capability_suite_strict_checks()),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("strict:live_capability_suite:open_existing_modify_reopen", result["failed"])


    def test_readme_documents_live_gate_native_outputs_and_stale_cleanup(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        usage = (ROOT / "docs" / "solidworks-codex-usage.md").read_text(encoding="utf-8")
        joined = readme + "\n" + usage
        self.assertIn("live-gate", joined)
        self.assertIn(".SLDASM/.SLDPRT", joined)
        self.assertIn("STEP", joined)
        self.assertIn("--cleanup-stale", joined)
        self.assertIn("shaper_machine_v5", joined)


    def test_gate_script_advertises_downstream_pywin32_requirement_to_swctl(self):
        head = SCRIPT.read_text(encoding="utf-8").splitlines()[:80]
        self.assertTrue(any("win32com" in line or "pythoncom" in line for line in head))

    def test_swctl_exposes_live_gate_command(self):
        swctl = (ROOT / "tools" / "solidworks_codex" / "swctl.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("'live-gate'", swctl)
        self.assertIn("sw_live_validation_gate.py", swctl)

    def test_cleanup_stale_records_permission_errors_without_crashing(self):
        calls = []
        original_dirs = self.module.default_stale_fixture_dirs
        original_rmtree = self.module.shutil.rmtree
        try:
            stale = ROOT / "tools" / "solidworks_codex" / "live_fixture" / "shaper_machine_v4"
            self.module.default_stale_fixture_dirs = lambda: (stale,)
            def fake_rmtree(path):
                calls.append(path)
                raise PermissionError("locked by SolidWorks")
            self.module.shutil.rmtree = fake_rmtree
            result = self.module.cleanup_stale_fixtures(True)
        finally:
            self.module.default_stale_fixture_dirs = original_dirs
            self.module.shutil.rmtree = original_rmtree
        self.assertEqual([stale], calls)
        self.assertFalse(result["entries"][0]["removed"])
        self.assertIn("PermissionError", result["entries"][0]["error"])

    def test_safe_cleanup_scope_only_allows_generated_live_fixture_children(self):
        allowed = ROOT / "tools" / "solidworks_codex" / "live_fixture" / "shaper_machine_v4"
        current = ROOT / "tools" / "solidworks_codex" / "live_fixture" / "shaper_machine_v5"
        unrelated = ROOT / "docs"
        self.assertTrue(self.module.is_safe_stale_fixture_dir(allowed))
        self.assertFalse(self.module.is_safe_stale_fixture_dir(current))
        self.assertFalse(self.module.is_safe_stale_fixture_dir(unrelated))

    def test_run_check_reports_timeout_without_hanging_gate(self):
        def fake_run(*args, **kwargs):
            raise self.module.subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

        original_run = self.module.subprocess.run
        try:
            self.module.subprocess.run = fake_run
            result = self.module.run_check(
                self.module.LiveCheck("heavy", ("python", "heavy.py"), "heavy.json", "slow"),
                timeout_seconds=3,
            )
        finally:
            self.module.subprocess.run = original_run
        self.assertEqual("heavy", result["name"])
        self.assertEqual(124, result["returncode"])
        self.assertIn("timeout_after_3s", result["stderr_tail"])

    def test_run_check_timeout_invokes_cleanup_hook_for_stuck_solidworks(self):
        calls = []

        def fake_run(*args, **kwargs):
            raise self.module.subprocess.TimeoutExpired(cmd=args[0], timeout=kwargs.get("timeout"))

        original_run = self.module.subprocess.run
        try:
            self.module.subprocess.run = fake_run
            result = self.module.run_check(
                self.module.LiveCheck("complete_shaper_v5", ("python", "heavy.py"), "heavy.json", "slow"),
                timeout_seconds=3,
                timeout_cleanup=lambda check: (calls.append(check.name) or {"terminated_pids": [77]}),
            )
        finally:
            self.module.subprocess.run = original_run
        self.assertEqual(["complete_shaper_v5"], calls)
        self.assertTrue(result["timeout_cleanup_requested"])
        self.assertEqual({"terminated_pids": [77]}, result["timeout_cleanup"])

    def test_timeout_cleanup_only_terminates_unhealthy_solidworks_processes(self):
        killed = []
        result = self.module.cleanup_solidworks_after_timeout(
            process_snapshots=[
                {"id": 11, "responding": True, "private_memory_bytes": 500_000_000},
                {"id": 12, "responding": False, "private_memory_bytes": 500_000_000},
                {"id": 13, "responding": True, "private_memory_bytes": 2_500_000_000},
            ],
            terminator=lambda pid: killed.append(pid),
            max_private_memory_bytes=1_900_000_000,
        )
        self.assertEqual([12, 13], killed)
        self.assertEqual([12, 13], result["terminated_pids"])


    def test_gate_preflight_blocks_any_generated_lock_files_before_running_checks(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = root / "tools" / "solidworks_codex" / "live_fixture"
            generated.mkdir(parents=True)
            lock = generated / "~$codex_validation_assembly.SLDASM"
            lock.write_text("stale", encoding="utf-8")
            result = self.module.generated_lockfile_preflight(root)
        self.assertFalse(result["ok"])
        self.assertIn("solidworks_generated_lock_files", result["failed"])
        self.assertEqual([str(lock)], result["lock_files"])


    def test_gate_preflight_failure_skips_stale_report_validation(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            generated = root / "tools" / "solidworks_codex" / "live_fixture"
            generated.mkdir(parents=True)
            (generated / "~$stale.SLDPRT").write_text("stale", encoding="utf-8")
            preflight = self.module.generated_lockfile_preflight(root)
            validation = self.module.validation_for_gate_state(
                preflight,
                validate_only=False,
                expectations=[self.module.ReportExpectation("missing", root / "missing.json", ("ok",))],
            )
        self.assertFalse(validation["ok"])
        self.assertEqual(["skipped_due_to_generated_lock_files"], validation["failed"])
        self.assertEqual({}, validation["reports"])


    def test_gate_stops_between_checks_if_a_check_leaks_generated_lock_files(self):
        root = Path("C:/fake-root")
        checks = (
            self.module.LiveCheck("smoke", ("python", "smoke.py"), "smoke.json", "first"),
            self.module.LiveCheck("heavy", ("python", "heavy.py"), "heavy.json", "second"),
        )
        calls = []
        lock_states = iter([
            {"ok": True, "failed": [], "lock_files": []},
            {"ok": False, "failed": ["solidworks_generated_lock_files"], "lock_files": ["~$leak.SLDPRT"]},
        ])
        executions, preflights = self.module.execute_checks_with_lock_preflight(
            checks,
            root,
            runner=lambda check: (calls.append(check.name) or {"name": check.name, "returncode": 0}),
            lock_probe=lambda probe_root: next(lock_states),
        )
        self.assertEqual(["smoke"], calls)
        self.assertEqual(["smoke"], [item["name"] for item in executions])
        self.assertFalse(preflights[-1]["ok"])


    def test_validate_gate_rejects_reports_older_than_their_live_script(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            script = root / "script.py"
            report.write_text(json.dumps({"ok": True, "validation": {"ok": True, "failed": []}}), encoding="utf-8")
            script.write_text("# newer", encoding="utf-8")
            import os
            os.utime(report, (100, 100))
            os.utime(script, (200, 200))
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("live_check", report, ("ok",), source_paths=(script,)),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("stale_report:live_check", result["failed"])


    def test_validate_gate_rejects_report_not_written_by_current_live_check(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = root / "report.json"
            report.write_text(json.dumps({"ok": True, "validation": {"ok": True, "failed": []}}), encoding="utf-8")
            import os
            os.utime(report, (100, 100))
            result = self.module.validate_gate_reports([
                self.module.ReportExpectation("live_check", report, ("ok",), generated_after=150),
            ])
        self.assertFalse(result["ok"])
        self.assertIn("stale_run_report:live_check", result["failed"])


    def test_execution_freshness_is_bound_to_each_check_start_time(self):
        checks = (self.module.LiveCheck("smoke", ("python", "smoke.py"), "smoke.json", "first"),)
        def fake_runner(check):
            return {"name": check.name, "returncode": 0}
        executions, _preflights = self.module.execute_checks_with_lock_preflight(
            checks,
            Path("C:/fake-root"),
            runner=fake_runner,
            lock_probe=lambda root: {"ok": True, "failed": [], "lock_files": []},
            clock=lambda: 123.5,
        )
        self.assertEqual(123.5, executions[0]["started_at_epoch"])


    def test_default_report_freshness_tracks_shared_inspect_code_for_live_checks(self):
        contract = self.module.build_gate_contract()
        expectations = {item.name: item for item in self.module.report_expectations(contract)}
        inspect_script = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_inspect.py"
        self.assertIn(inspect_script, expectations["live_session_smoke"].source_paths)
        self.assertIn(inspect_script, expectations["live_capability_suite"].source_paths)
        self.assertIn(inspect_script, expectations["complete_shaper_v5"].source_paths)
        shaper_script = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_create_complete_shaper_fixture.py"
        self.assertIn(shaper_script, expectations["live_session_smoke"].source_paths)

    def test_gate_console_summary_omits_full_report_tree_but_keeps_key_status(self):
        payload = {
            "ok": True,
            "failed": [],
            "executions": [{"name": "live_session_smoke", "returncode": 0, "stdout_tail": "x" * 8000}],
            "validation": {
                "ok": True,
                "failed": [],
                "reports": {
                    "complete_shaper_v5": {
                        "ok": True,
                        "inspect": {"active_document": {"features": ["huge"] * 1000}},
                    }
                },
            },
            "generated_lockfile_preflight": {"ok": True, "failed": [], "lock_files": []},
            "stale_fixture_cleanup": {"remove_requested": False, "entries": []},
        }

        text = self.module.console_summary_json(payload)
        summary = json.loads(text)

        self.assertTrue(summary["ok"])
        self.assertEqual([], summary["failed"])
        self.assertEqual([{"name": "live_session_smoke", "returncode": 0}], summary["executions"])
        self.assertNotIn("reports", summary["validation"])
        self.assertLess(len(text), 1200)

    def test_gate_console_summary_includes_report_hint_contract_and_failed_tail(self):
        payload = {
            "ok": False,
            "failed": ["process:live_capability_suite:2"],
            "contract": {"output_json": "tools/solidworks_codex/reports/live_validation_gate.json", "checks": [{"name": "live_capability_suite"}]},
            "executions": [{"name": "live_capability_suite", "returncode": 2, "stderr_tail": "diagnostic" * 200}],
            "validation": {"ok": False, "failed": ["strict:live_capability_suite:mass_callback"], "reports": {}},
            "generated_lockfile_preflight": {"ok": True, "failed": [], "lock_files": []},
            "stale_fixture_cleanup": {"remove_requested": False, "entries": []},
        }

        summary = json.loads(self.module.console_summary_json(payload, full_report="custom.json"))

        self.assertEqual("custom.json", summary["full_report"])
        self.assertIn("Use --full-console-json", summary["hint"])
        self.assertEqual(["live_capability_suite"], summary["contract"]["check_names"])
        failed_execution = summary["executions"][0]
        self.assertIn("stderr_tail", failed_execution)
        self.assertLessEqual(len(failed_execution["stderr_tail"]), 240)

    def test_gate_main_prints_summary_by_default_and_full_json_on_request(self):
        payload = {"ok": True, "contract": {"checks": [{"name": "live_session_smoke"}], "output_json": "x.json"}, "stale_fixture_cleanup": {"entries": []}}
        summary = json.loads(self.module.console_output_json(payload, full_console_json=False, full_report="out.json"))
        full = json.loads(self.module.console_output_json(payload, full_console_json=True, full_report="out.json"))

        self.assertIn("full_report", summary)
        self.assertNotEqual(payload, summary)
        self.assertEqual(payload, full)

    def test_live_gate_supports_explicit_full_console_json_escape_hatch(self):
        args = self.module.parse_args(["--full-console-json"])
        self.assertTrue(args.full_console_json)
        swctl = (ROOT / "tools" / "solidworks_codex" / "swctl.ps1").read_text(encoding="utf-8-sig")
        self.assertIn("FullConsoleJson", swctl)
        self.assertIn("--full-console-json", swctl)

    def test_console_json_is_safe_for_gbk_stdout(self):
        text = self.module.console_json({"relationship": "ram↔way", "ok": False})
        text.encode("gbk")
        self.assertIn("\\u2194", text)


if __name__ == "__main__":
    unittest.main()
