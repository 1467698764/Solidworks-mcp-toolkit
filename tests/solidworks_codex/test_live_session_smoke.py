import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_live_session_smoke.py"


def load_module():
    spec = importlib.util.spec_from_file_location("sw_live_session_smoke", SCRIPT)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load live session smoke module spec")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class LiveSessionSmokeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.module = load_module()

    def _base_result(self):
        return {
            "ok": True,
            "started_second_session": False,
            "part_inspect": {"active_document": {"type": "part"}},
            "assembly_inspect": {"active_document": {"type": "assembly", "component_count_sampled": 2, "mate_like_features": [
                {"name": "Smoke_Distance_Mate", "components": ["session_smoke_left-1", "session_smoke_right-1"]}
            ]}},
            "callbacks": {"interference": {"available": True, "count": 0}},
            "post_cleanup": {"locked_files": [], "lock_files": []},
        }

    def test_smoke_validation_requires_mate_reference_components_from_inspect(self):
        self.assertTrue(self.module.validate_session_smoke_result(self._base_result())["ok"])
        bad = self._base_result()
        bad["assembly_inspect"]["active_document"]["mate_like_features"] = [{"name": "Smoke_Distance_Mate"}]
        validation = self.module.validate_session_smoke_result(bad)
        self.assertFalse(validation["ok"])
        self.assertIn("assembly_mate_component_evidence", validation["failed"])


if __name__ == "__main__":
    unittest.main()
