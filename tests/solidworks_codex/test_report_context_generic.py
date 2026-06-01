import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_py(script: str, *args: str):
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class GenericReportContextTests(unittest.TestCase):
    def make_fixture_report(self, root: Path) -> Path:
        report = {
            "active_document": {
                "title": "fixture_table.SLDASM",
                "path": "C:/machines/fixture_table.SLDASM",
                "type": "assembly",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/machines/base_plate.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [-0.15, -0.10, 0.0, 0.15, 0.10, 0.012]},
                    {"name2": "locator_block-1", "path": "C:/machines/locator_block.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.04, -0.03, 0.012, 0.04, 0.03, 0.05]},
                    {"name2": "clamp_arm-1", "path": "C:/machines/clamp_arm.SLDPRT", "suppressed": False, "hidden": True, "fixed": False, "bbox_m": [0.02, -0.02, 0.05, 0.12, 0.02, 0.075]},
                    {"name2": "dowel_pin-1", "path": "C:/machines/dowel_pin.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.045, -0.025, 0.0, -0.039, -0.019, 0.055]},
                ],
                "dimensions": [
                    {"full_name": "HoleDia@Sketch1@base_plate.SLDPRT", "system_value_m": 0.006, "feature": "Sketch1"},
                    {"full_name": "ClampGap@Sketch2@clamp_arm.SLDPRT", "system_value_m": 0.0, "feature": "Sketch2"},
                ],
                "features": [
                    {"name": "MateGroup", "type": "MateGroup"},
                    {"name": "HoleWizard1", "type": "HoleWzd"},
                ],
            }
        }
        path = root / "fixture_context.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_context_pack_is_generic_and_does_not_prescribe_fixed_domain_searches(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_md = root / "context.md"
            out_json = root / "context.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_report_context.py",
                "--report", str(self.make_fixture_report(root)),
                "--focus", "理解夹具定位、夹紧空间、孔系加工证据，不要套固定模板",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            lower_text = text.lower()
            self.assertIn("SolidWorks Codex Context Pack", text)
            self.assertIn("Evidence gaps", text)
            self.assertIn("Flexible next queries", text)
            self.assertIn("model-understand", text)
            self.assertIn("locator_block-1", text)
            self.assertIn("ClampGap@Sketch2@clamp_arm.SLDPRT", text)
            self.assertNotIn("mechanical-assembly", lower_text)
            self.assertNotIn("mechanical assembly", lower_text)
            self.assertNotIn("mounting interface", lower_text)
            self.assertNotIn("sample-machine-baseline", lower_text)
            commands = "\n".join(data["recommended_commands"]).lower()
            self.assertNotIn("mounting interface", commands)
            self.assertIn("evidence_gaps", data)
            self.assertIn("next_queries", data)
            self.assertTrue(any(q["kind"] == "spatial_understanding" for q in data["next_queries"]))
            self.assertTrue(any(g["kind"] == "manufacturing_evidence" for g in data["evidence_gaps"]))


if __name__ == "__main__":
    unittest.main()
