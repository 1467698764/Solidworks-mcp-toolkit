import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_live_capability_suite.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sw_live_capability_suite", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load live capability suite module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def sample_operation_context(module):
    context = module.expected_operation_context()
    for part_key, part in context.items():
        part["active_title"] = f"Temporary title for {part_key}"
        part["saved_path"] = f"C:/generated/{part['document']}"
        for op_name, op in part["operations"].items():
            op["sketch"] = f"Sketch_for_{op_name}"
            op["selection_guard"] = {
                "active_title": f"Temporary title for {part_key}",
                "cleared_selection_count": 0,
                "selected_sketch": f"Sketch_for_{op_name}",
                "selection_count_before_feature": 1,
            }
            op["readback"] = {
                "sketch": f"Sketch_for_{op_name}",
                "geometry": dict(op["geometry"]),
                "feature_type": op["feature_type"],
                "source": "reopened_feature_tree",
            }
    return context


def sample_mates():
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


def sample_assembly_inspect():
    return {
        "active_document": {
            "type": "assembly",
            "component_count_sampled": 4,
            "mate_like_features": [
                {"name": "Concentric_Mate", "type": "MateConcentric", "components": ["revolve_boss_part-1", "revolve_cut_part-1"], "suppressed": False},
                {"name": "Distance_Mate", "type": "MateDistanceDim", "components": ["extrude_cut_plate-1", "editable_dimension_plate-1"], "suppressed": False},
            ],
        }
    }


class FakeSegment:
    def __init__(self, segment_type, construction=False):
        self._segment_type = segment_type
        self.ConstructionGeometry = construction

    def GetType(self):
        return self._segment_type


class FakeSketch:
    def __init__(self, segments):
        self._segments = tuple(segments)

    def GetSketchSegments(self):
        return self._segments


class FakeSubFeature:
    def __init__(self, name, feature_type, sketch=None, next_sub=None):
        self.Name = name
        self._feature_type = feature_type
        self._sketch = sketch
        self._next_sub = next_sub

    def GetTypeName2(self):
        return self._feature_type

    def GetSpecificFeature2(self):
        return self._sketch

    def GetNextSubFeature(self):
        return self._next_sub


class FakeFeature:
    def __init__(self, sub_feature):
        self._sub_feature = sub_feature

    def GetFirstSubFeature(self):
        return self._sub_feature


class LiveCapabilitySuiteSpecTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_capability_matrix_covers_core_live_operations(self):
        matrix = self.module.build_capability_matrix()
        names = {c.name for c in matrix.capabilities}
        required = {
            "extrude_boss",
            "extrude_cut",
            "revolve_boss",
            "revolve_cut",
            "sketch_edit_dimension",
            "read_modify_rebuild",
            "open_existing_modify_reopen",
            "assembly_insert_component",
            "assembly_mate_concentric",
            "assembly_mate_distance",
            "interference_callback",
            "mass_callback",
            "native_solidworks_artifacts",
            "cleanup_single_session",
        }
        self.assertTrue(required.issubset(names), sorted(required - names))

    def test_each_capability_has_live_artifacts_and_acceptance(self):
        matrix = self.module.build_capability_matrix()
        for capability in matrix.capabilities:
            self.assertTrue(capability.live_artifact, capability.name)
            self.assertTrue(capability.acceptance_checks, capability.name)
            self.assertIn(capability.status, {"implemented", "planned"})
        implemented = [c for c in matrix.capabilities if c.status == "implemented"]
        self.assertGreaterEqual(len(implemented), 10)

    def test_expected_feature_contract_includes_revolve_and_mates(self):
        contract = self.module.expected_live_contract()
        self.assertIn("revolve_boss_part", contract["parts"])
        self.assertIn("Revolve_Boss_Profile", contract["parts"]["revolve_boss_part"])
        self.assertIn("Revolve_Cut_Bore", contract["parts"]["revolve_cut_part"])
        self.assertIn("Edited_Sketch_Dimension", contract["dimensions"])
        self.assertIn("Concentric_Mate", contract["mates"])
        self.assertIn("Distance_Mate", contract["mates"])
        self.assertGreaterEqual(contract["minimum_component_count"], 3)


    def test_expected_contract_includes_reopen_persistence_check(self):
        contract = self.module.expected_live_contract()
        self.assertIn("open_existing_modify_reopen", contract)
        self.assertEqual(contract["open_existing_modify_reopen"]["dimension"], "D1@Edited_Sketch_Dimension")
        self.assertEqual(contract["open_existing_modify_reopen"]["expected_after_reopen_m"], 0.028)

    def test_expected_contract_requires_operation_context_guards(self):
        contract = self.module.expected_live_contract()
        guards = contract["operation_context"]
        self.assertEqual(guards["extrude"]["document"], "extrude_cut_plate.SLDPRT")
        self.assertEqual(guards["extrude"]["operations"]["Round_Through_Hole"]["profile"], "circle")
        self.assertEqual(guards["extrude"]["operations"]["Round_Through_Hole"]["geometry"]["circles"], 1)
        self.assertEqual(guards["extrude"]["operations"]["Rectangular_Window_Cut"]["geometry"]["lines"], 4)
        self.assertEqual(guards["extrude"]["operations"]["Rectangular_Window_Cut"]["profile"], "rectangle")
        self.assertEqual(guards["revolve"]["operations"]["Revolve_Boss_Profile"]["geometry"]["centerlines"], 1)
        self.assertEqual(guards["revolve_cut"]["operations"]["Revolve_Cut_Bore"]["feature_type"], "RevCut")
        self.assertEqual(guards["editable"]["operations"]["Edited_Sketch_Dimension"]["dimension"], "D1@Edited_Sketch_Dimension")
        for part in guards.values():
            for op in part["operations"].values():
                self.assertTrue(op["selection_guard"]["active_title"])
                self.assertEqual(op["selection_guard"]["cleared_selection_count"], 0)
                self.assertEqual(op["selection_guard"]["selection_count_before_feature"], 1)

    def test_validate_operation_context_rejects_missing_or_wrong_selection_guard(self):
        context = sample_operation_context(self.module)

        del context["extrude"]["operations"]["Round_Through_Hole"]["selection_guard"]
        validation = self.module.validate_operation_context(context)
        self.assertFalse(validation["ok"])
        self.assertIn("extrude:Round_Through_Hole:selection_guard", validation["failed"])

        context = sample_operation_context(self.module)
        context["extrude"]["operations"]["Round_Through_Hole"]["selection_guard"]["selected_sketch"] = "Sketch_from_previous_operation"
        validation = self.module.validate_operation_context(context)
        self.assertFalse(validation["ok"])
        self.assertIn("extrude:Round_Through_Hole:selection_guard:selected_sketch", validation["failed"])

        context = sample_operation_context(self.module)
        context["revolve_cut"]["operations"]["Revolve_Cut_Bore"]["selection_guard"]["selection_count_before_feature"] = 2
        validation = self.module.validate_operation_context(context)
        self.assertFalse(validation["ok"])
        self.assertIn("revolve_cut:Revolve_Cut_Bore:selection_guard:selection_count_before_feature", validation["failed"])

        context = sample_operation_context(self.module)
        context["editable"]["operations"]["Edited_Sketch_Dimension"]["selection_guard"]["selection_count_before_feature"] = None
        validation = self.module.validate_operation_context(context)
        self.assertFalse(validation["ok"])
        self.assertIn("editable:Edited_Sketch_Dimension:selection_guard:selection_count_before_feature", validation["failed"])

        context = sample_operation_context(self.module)
        context["revolve"]["operations"]["Revolve_Boss_Profile"]["selection_guard"]["cleared_selection_count"] = None
        validation = self.module.validate_operation_context(context)
        self.assertFalse(validation["ok"])
        self.assertIn("revolve:Revolve_Boss_Profile:selection_guard:cleared_selection_count", validation["failed"])

        context = sample_operation_context(self.module)
        context["extrude"]["operations"]["Body_Plate"]["selection_guard"]["active_title"] = ""
        validation = self.module.validate_operation_context(context)
        self.assertFalse(validation["ok"])
        self.assertIn("extrude:Body_Plate:selection_guard:active_title", validation["failed"])


    def test_reopened_feature_readback_reports_actual_consumed_sketch_name_and_geometry(self):
        actual_sketch = FakeSubFeature(
            "ActualConsumedSketch",
            "ProfileFeature",
            FakeSketch([FakeSegment(0), FakeSegment(0), FakeSegment(1), FakeSegment(0, construction=True)]),
        )
        feature = FakeFeature(actual_sketch)

        readback = self.module.sketch_readback_from_feature(feature)

        self.assertEqual(readback["sketch"], "ActualConsumedSketch")
        self.assertEqual(readback["source"], "reopened_feature_tree")
        self.assertEqual(readback["geometry"], {"lines": 2, "circles": 1, "centerlines": 1})

    def test_cleanup_policy_is_explicit_and_keeps_generated_outputs_separate(self):
        matrix = self.module.build_capability_matrix()
        self.assertIn("live_capability_suite", matrix.output_dir)
        self.assertIn("live_capability_suite", matrix.reports_dir)
        policy = self.module.cleanup_policy()
        self.assertTrue(policy["close_documents_before_cleanup"])
        self.assertTrue(policy["delete_unlocked_generated_files"])
        self.assertTrue(policy["never_touch_unrelated_user_files"])

    def test_validate_live_result_rejects_failed_mates_callbacks_and_cleanup(self):
        bad = {
            "features": {
                "extrude": [{"name": "Body_Plate"}, {"name": "Round_Through_Hole"}, {"name": "Rectangular_Window_Cut"}],
                "revolve": [{"name": "Revolve_Boss_Profile"}],
                "revolve_cut": [{"name": "Revolve_Boss_Profile"}, {"name": "Revolve_Cut_Bore"}],
                "editable": [{"name": "Body_Editable_Plate"}, {"name": "Edited_Sketch_Dimension"}],
            },
            "dimension_edit": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.02, "after_m": 0.024},
            "reopen_modify": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.028, "persisted": True, "save": {"ok": True, "errors": 0, "warnings": 0}},
            "assembly_result": {"component_count": 4, "mates": [{"name": "Concentric_Mate", "ok": False}, {"name": "Distance_Mate", "ok": False}]},
            "callbacks": {
                "mass": {"available": True, "mass_kg": 1.0},
                "interference": {"available": False, "error": "bad api"},
                "export": {"success": False, "exists_after": True, "size": 10},
            },
            "cleanup": {"locked_files": ["part.SLDPRT"]},
        }
        validation = self.module.validate_live_result(bad)
        self.assertFalse(validation["ok"])
        self.assertIn("mate:Concentric_Mate", validation["failed_capabilities"])
        self.assertIn("interference_callback", validation["failed_capabilities"])
        self.assertIn("cleanup_single_session", validation["failed_capabilities"])

    def test_validate_live_result_accepts_complete_evidence(self):
        good = {
            "features": {
                "extrude": [{"name": "Body_Plate"}, {"name": "Round_Through_Hole"}, {"name": "Rectangular_Window_Cut"}],
                "revolve": [{"name": "Revolve_Boss_Profile"}],
                "revolve_cut": [{"name": "Revolve_Boss_Profile"}, {"name": "Revolve_Cut_Bore"}],
                "editable": [{"name": "Body_Editable_Plate"}, {"name": "Edited_Sketch_Dimension"}],
            },
            "dimension_edit": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.02, "after_m": 0.024},
            "reopen_modify": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.028, "persisted": True, "save": {"ok": True, "errors": 0, "warnings": 0}},
            "assembly_result": {"component_count": 4, "mates": sample_mates()},
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
            "assembly_inspect": sample_assembly_inspect(),
            "callbacks": {
                "mass": {"available": True, "mass_kg": 1.0},
                "interference": {"available": True, "count": 0},
                "optional_step_export": {"optional": True, "api_success": False},
            },
            "native_artifacts": {"assembly_exists": True, "part_count": 4, "part_files": ["a.SLDPRT", "b.SLDPRT", "c.SLDPRT", "d.SLDPRT"]},
            "cleanup": {"locked_files": []},
            "post_cleanup": {"locked_files": []},
        }
        validation = self.module.validate_live_result(good)
        self.assertFalse(validation["ok"])
        self.assertIn("operation_context_guards", validation["failed_capabilities"])

        good["operation_context"] = sample_operation_context(self.module)
        del good["operation_context"]["extrude"]["active_title"]
        validation = self.module.validate_live_result(good)
        self.assertFalse(validation["ok"])
        self.assertIn("operation_context_guards", validation["failed_capabilities"])

        good["operation_context"] = sample_operation_context(self.module)
        validation = self.module.validate_live_result(good)
        self.assertTrue(validation["ok"], validation)
        self.assertEqual([], validation["failed_capabilities"])

        good["operation_context"]["extrude"]["operations"]["Round_Through_Hole"]["profile"] = "rectangle"
        validation = self.module.validate_live_result(good)
        self.assertFalse(validation["ok"])
        self.assertIn("operation_context_guards", validation["failed_capabilities"])

        good["operation_context"] = sample_operation_context(self.module)
        good["operation_context"]["extrude"]["operations"]["Round_Through_Hole"]["geometry"]["circles"] = 0
        validation = self.module.validate_live_result(good)
        self.assertFalse(validation["ok"])
        self.assertIn("operation_context_guards", validation["failed_capabilities"])

        good["operation_context"] = sample_operation_context(self.module)
        del good["operation_context"]["extrude"]["operations"]["Round_Through_Hole"]["readback"]
        validation = self.module.validate_live_result(good)
        self.assertFalse(validation["ok"])
        self.assertIn("operation_context_guards", validation["failed_capabilities"])

        good["operation_context"] = sample_operation_context(self.module)
        good["operation_context"]["extrude"]["operations"]["Round_Through_Hole"]["readback"]["geometry"]["circles"] = 0
        validation = self.module.validate_live_result(good)
        self.assertFalse(validation["ok"])
        self.assertIn("operation_context_guards", validation["failed_capabilities"])

    def test_cleanup_rejects_unsafe_force_directory(self):
        unsafe = ROOT / "definitely_not_the_live_suite_root"
        self.assertFalse(self.module.is_safe_generated_dir(unsafe))
        with self.assertRaises(ValueError):
            self.module.cleanup_generated(unsafe, True)

    def test_validate_live_result_requires_post_cleanup_and_persisted_mates(self):
        result = {
            "features": {
                "extrude": [{"name": "Body_Plate"}, {"name": "Round_Through_Hole"}, {"name": "Rectangular_Window_Cut"}],
                "revolve": [{"name": "Revolve_Boss_Profile"}],
                "revolve_cut": [{"name": "Revolve_Boss_Profile"}, {"name": "Revolve_Cut_Bore"}],
                "editable": [{"name": "Body_Editable_Plate"}, {"name": "Edited_Sketch_Dimension"}],
            },
            "dimension_edit": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.02, "after_m": 0.024},
            "reopen_modify": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.028, "persisted": True, "save": {"ok": True, "errors": 0, "warnings": 0}},
            "assembly_result": {"component_count": 4, "mates": sample_mates()},
            "assembly_features": [],
            "callbacks": {
                "mass": {"available": True, "mass_kg": 1.0},
                "interference": {"available": True, "count": 0},
                "optional_step_export": {"optional": True, "api_success": False},
            },
            "native_artifacts": {"assembly_exists": True, "part_count": 4, "part_files": ["a.SLDPRT", "b.SLDPRT", "c.SLDPRT", "d.SLDPRT"]},
            "cleanup": {"locked_files": []},
            "post_cleanup": {"locked_files": []},
        }
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("assembly_mates_persisted", validation["failed_capabilities"])

        result["assembly_features"] = [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}]
        result["post_cleanup"] = {"locked_files": ["capability_suite.SLDASM"]}
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("post_cleanup_single_session", validation["failed_capabilities"])

    def test_validate_live_result_requires_mate_selection_and_component_evidence(self):
        result = {
            "features": {
                "extrude": [{"name": "Body_Plate"}, {"name": "Round_Through_Hole"}, {"name": "Rectangular_Window_Cut"}],
                "revolve": [{"name": "Revolve_Boss_Profile"}],
                "revolve_cut": [{"name": "Revolve_Boss_Profile"}, {"name": "Revolve_Cut_Bore"}],
                "editable": [{"name": "Body_Editable_Plate"}, {"name": "Edited_Sketch_Dimension"}],
            },
            "dimension_edit": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.02, "after_m": 0.024},
            "reopen_modify": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.028, "persisted": True, "save": {"ok": True, "errors": 0, "warnings": 0}},
            "assembly_result": {"component_count": 4, "mates": sample_mates()},
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
            "assembly_inspect": sample_assembly_inspect(),
            "callbacks": {"mass": {"available": True, "mass_kg": 1.0}, "interference": {"available": True, "count": 0}},
            "native_artifacts": {"assembly_exists": True, "part_count": 4, "part_files": ["a.SLDPRT", "b.SLDPRT", "c.SLDPRT", "d.SLDPRT"]},
            "cleanup": {"locked_files": []},
            "post_cleanup": {"locked_files": []},
            "operation_context": sample_operation_context(self.module),
        }
        validation = self.module.validate_live_result(result)
        self.assertTrue(validation["ok"], validation)

        result["assembly_result"]["mates"][0]["selected_entities"] = 1
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("mate_selection:Concentric_Mate", validation["failed_capabilities"])

        result["assembly_result"]["mates"] = sample_mates()
        result["assembly_result"]["mates"][1]["selection_guard"]["component_pair"] = ["wrong_part-1", "editable_dimension_plate-1"]
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("mate_components:Distance_Mate", validation["failed_capabilities"])

        result["assembly_result"]["mates"] = sample_mates()
        result["assembly_result"]["mates"][1]["selection_guard"]["selection_count_before_mate"] = None
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("mate_selection:Distance_Mate", validation["failed_capabilities"])

    def test_validate_live_result_requires_assembly_inspect_mate_component_readback(self):
        result = {
            "features": {
                "extrude": [{"name": "Body_Plate"}, {"name": "Round_Through_Hole"}, {"name": "Rectangular_Window_Cut"}],
                "revolve": [{"name": "Revolve_Boss_Profile"}],
                "revolve_cut": [{"name": "Revolve_Boss_Profile"}, {"name": "Revolve_Cut_Bore"}],
                "editable": [{"name": "Body_Editable_Plate"}, {"name": "Edited_Sketch_Dimension"}],
            },
            "dimension_edit": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.02, "after_m": 0.024},
            "reopen_modify": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.028, "persisted": True, "save": {"ok": True, "errors": 0, "warnings": 0}},
            "assembly_result": {"component_count": 4, "mates": sample_mates()},
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
            "callbacks": {"mass": {"available": True, "mass_kg": 1.0}, "interference": {"available": True, "count": 0}},
            "native_artifacts": {"assembly_exists": True, "part_count": 4, "part_files": ["a.SLDPRT", "b.SLDPRT", "c.SLDPRT", "d.SLDPRT"]},
            "cleanup": {"locked_files": []},
            "post_cleanup": {"locked_files": []},
            "operation_context": sample_operation_context(self.module),
        }
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("assembly_inspect_mates", validation["failed_capabilities"])

        result["assembly_inspect"] = sample_assembly_inspect()
        validation = self.module.validate_live_result(result)
        self.assertTrue(validation["ok"], validation)

        result["assembly_inspect"]["active_document"]["mate_like_features"][0]["components"] = ["wrong-1", "revolve_cut_part-1"]
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("assembly_inspect_mates", validation["failed_capabilities"])


    def test_validate_live_result_rejects_missing_reopen_persistence(self):
        result = {
            "features": {
                "extrude": [{"name": "Body_Plate"}, {"name": "Round_Through_Hole"}, {"name": "Rectangular_Window_Cut"}],
                "revolve": [{"name": "Revolve_Boss_Profile"}],
                "revolve_cut": [{"name": "Revolve_Boss_Profile"}, {"name": "Revolve_Cut_Bore"}],
                "editable": [{"name": "Body_Editable_Plate"}, {"name": "Edited_Sketch_Dimension"}],
            },
            "dimension_edit": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.02, "after_m": 0.024},
            "assembly_result": {"component_count": 4, "mates": sample_mates()},
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
            "callbacks": {"mass": {"available": True, "mass_kg": 1.0}, "interference": {"available": True, "count": 0}},
            "native_artifacts": {"assembly_exists": True, "part_count": 4, "part_files": ["a.SLDPRT", "b.SLDPRT", "c.SLDPRT", "d.SLDPRT"]},
            "cleanup": {"locked_files": []},
            "post_cleanup": {"locked_files": []},
        }
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("open_existing_modify_reopen", validation["failed_capabilities"])

        result["reopen_modify"] = {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.027, "persisted": False}
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("open_existing_modify_reopen", validation["failed_capabilities"])

        result["reopen_modify"] = {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.028, "persisted": True, "save": {"ok": False, "errors": 8192, "warnings": 0}}
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("open_existing_modify_reopen", validation["failed_capabilities"])

    def test_native_solidworks_artifacts_are_primary_not_step(self):
        matrix = self.module.build_capability_matrix()
        by_name = {capability.name: capability for capability in matrix.capabilities}
        self.assertIn("native_solidworks_artifacts", by_name)
        self.assertNotIn("mass_export_callback", by_name)
        native = by_name["native_solidworks_artifacts"]
        self.assertIn("capability_suite.SLDASM", native.live_artifact)
        self.assertIn("sldasm_exists", native.acceptance_checks)
        self.assertIn("sldprt_count>=4", native.acceptance_checks)
        self.assertNotIn("step_exists", native.acceptance_checks)

    def test_validate_live_result_requires_native_solidworks_files_not_step_export(self):
        result = {
            "features": {
                "extrude": [{"name": "Body_Plate"}, {"name": "Round_Through_Hole"}, {"name": "Rectangular_Window_Cut"}],
                "revolve": [{"name": "Revolve_Boss_Profile"}],
                "revolve_cut": [{"name": "Revolve_Boss_Profile"}, {"name": "Revolve_Cut_Bore"}],
                "editable": [{"name": "Body_Editable_Plate"}, {"name": "Edited_Sketch_Dimension"}],
            },
            "dimension_edit": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.02, "after_m": 0.024},
            "reopen_modify": {"dimension": "D1@Edited_Sketch_Dimension", "before_m": 0.024, "target_m": 0.028, "after_reopen_m": 0.028, "persisted": True, "save": {"ok": True, "errors": 0, "warnings": 0}},
            "assembly_result": {"component_count": 4, "mates": sample_mates()},
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
            "assembly_inspect": sample_assembly_inspect(),
            "native_artifacts": {"assembly_exists": False, "part_count": 4, "part_files": ["a.SLDPRT", "b.SLDPRT", "c.SLDPRT", "d.SLDPRT"]},
            "callbacks": {
                "mass": {"available": True, "mass_kg": 1.0},
                "interference": {"available": True, "count": 0},
                "export": {"api_success": True, "exists_after": True, "size": 10},
            },
            "cleanup": {"locked_files": []},
            "post_cleanup": {"locked_files": []},
        }
        validation = self.module.validate_live_result(result)
        self.assertFalse(validation["ok"])
        self.assertIn("native_solidworks_artifacts", validation["failed_capabilities"])

        result["native_artifacts"]["assembly_exists"] = True
        result["operation_context"] = sample_operation_context(self.module)
        validation = self.module.validate_live_result(result)
        self.assertTrue(validation["ok"], validation)


if __name__ == "__main__":
    unittest.main()
