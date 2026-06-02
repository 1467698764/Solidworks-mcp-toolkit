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
            "assembly_result": {"component_count": 4, "mates": [{"name": "Concentric_Mate", "ok": True}, {"name": "Distance_Mate", "ok": True}]},
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
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
        self.assertTrue(validation["ok"], validation)
        self.assertEqual([], validation["failed_capabilities"])

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
            "assembly_result": {"component_count": 4, "mates": [{"name": "Concentric_Mate", "ok": True}, {"name": "Distance_Mate", "ok": True}]},
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
            "assembly_result": {"component_count": 4, "mates": [{"name": "Concentric_Mate", "ok": True}, {"name": "Distance_Mate", "ok": True}]},
            "assembly_features": [{"name": "Concentric_Mate"}, {"name": "Distance_Mate"}],
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
        validation = self.module.validate_live_result(result)
        self.assertTrue(validation["ok"], validation)


if __name__ == "__main__":
    unittest.main()
