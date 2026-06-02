import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_validation_profiles.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sw_validation_profiles", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load validation profile module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ValidationProfileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def test_default_draft_profile_is_lightweight_and_non_blocking_for_heavy_engineering(self):
        profile = self.module.validation_profile_for_intent("draft_part")
        blocking = self.module.blocking_check_names(profile)
        warnings = self.module.warning_check_names(profile)

        self.assertIn("native_artifacts", blocking)
        self.assertIn("rebuild_health", blocking)
        self.assertIn("part_shape_semantics", blocking)
        self.assertNotIn("motion_sweep_collision", blocking)
        self.assertIn("dfm_screen", warnings)
        self.assertIn("dfa_screen", warnings)

    def test_mechanism_profile_blocks_constraint_motion_clearance_and_interference(self):
        profile = self.module.validation_profile_for_intent("mechanism_assembly")
        blocking = self.module.blocking_check_names(profile)

        for check in (
            "native_artifacts",
            "rebuild_health",
            "part_shape_semantics",
            "assembly_mate_semantics",
            "component_placements",
            "static_interference",
            "functional_adjacency",
            "constraint_dof_intent",
            "motion_sweep_collision",
            "clearance_tolerance_screen",
        ):
            self.assertIn(check, blocking)
        self.assertNotIn("full_fea", blocking)

    def test_profile_can_be_extended_by_reasoning_model_without_making_everything_required(self):
        profile = self.module.validation_profile_for_intent(
            "draft_part",
            extra_checks=[{"name": "tool_access", "severity": "warning", "layer": "engineering"}],
        )
        self.assertIn("tool_access", self.module.warning_check_names(profile))
        self.assertNotIn("tool_access", self.module.blocking_check_names(profile))

    def test_not_applicable_checks_are_reported_not_failed(self):
        profile = self.module.validation_profile_for_intent("single_part")
        names = self.module.not_applicable_check_names(profile)
        self.assertIn("assembly_mate_semantics", names)
        self.assertIn("motion_sweep_collision", names)


if __name__ == "__main__":
    unittest.main()
