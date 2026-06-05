import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "tools" / "solidworks_codex" / "mcp" / "smoke-test.cjs"


class McpSmokeCoverageTests(unittest.TestCase):
    def test_smoke_routes_mate_selection_and_live_protocol_tools(self):
        text = SMOKE.read_text(encoding="utf-8-sig")
        self.assertIn("solidworks_component_insert", text)
        self.assertIn("solidworks_part_feature_execute", text)
        self.assertIn("solidworks_metadata_execute", text)
        self.assertIn("solidworks_mate_selection_check", text)
        self.assertIn("solidworks_mate_group_execute", text)
        self.assertIn("solidworks_mate_group_live_protocol", text)
        self.assertIn("solidworks_motion_sweep_lite", text)
        self.assertIn("componentInsert_is_error", text)
        self.assertIn("partFeatureExecute_is_error", text)
        self.assertIn("metadataExecute_is_error", text)
        self.assertIn("mateSelectionCheck_is_error", text)
        self.assertIn("mateGroupExecute_is_error", text)
        self.assertIn("mateGroupLiveProtocol_is_error", text)
        self.assertIn("motionSweepLite_is_error", text)


if __name__ == "__main__":
    unittest.main()
