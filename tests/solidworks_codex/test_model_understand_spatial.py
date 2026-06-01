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


class ModelUnderstandSpatialTests(unittest.TestCase):
    def make_spatial_report(self, root: Path) -> Path:
        report = {
            "timestamp": "spatial",
            "active_document": {
                "title": "spatial_sample_machine.SLDASM",
                "path": "C:/robot/spatial_sample_machine.SLDASM",
                "type": "assembly",
                "components": [
                    {"name2": "housing-1", "path": "C:/robot/housing.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [-0.05, -0.05, -0.02, 0.05, 0.05, 0.02]},
                    {"name2": "support_bushing-1", "path": "C:/cad/projects/sample_machine/support_bushing.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.015, -0.015, -0.01, 0.015, 0.015, 0.01]},
                    {"name2": "reference_sensor-1", "path": "C:/cad/projects/sample_machine/reference_sensor.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.012, -0.012, 0.009, 0.012, 0.012, 0.017]},
                    {"name2": "drive_unit-1", "path": "C:/cad/projects/sample_machine/drive_unit.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.03, -0.03, -0.08, 0.03, 0.03, -0.021]},
                    {"name2": "cover-virtual", "path": "", "suppressed": False, "hidden": False, "fixed": False}
                ],
                "dimensions": [
                    {"full_name": "D1@Sketch1@housing.SLDPRT", "system_value_m": 0.1, "feature": "Sketch1"}
                ],
                "features": [
                    {"name": "MateGroup", "type": "MateGroup"}
                ]
            }
        }
        path = root / "spatial_report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_spatial_understanding_detects_overlap_gap_centers_and_missing_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = self.make_spatial_report(root)
            out_json = root / "understanding.json"
            out_md = root / "understanding.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(report),
                "--task", "理解轴承 编码器 电机 壳体的空间关系和装配可行性",
                "--view", "spatial-assembly",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertEqual(data["scope"]["view"], "spatial-assembly")
            self.assertIn("spatial_model", data)
            by_name = {item["name"]: item for item in data["spatial_model"]["components"]}
            self.assertAlmostEqual(by_name["support_bushing-1"]["center_m"][2], 0.0, places=6)
            pairs = {(p["a"], p["b"]): p for p in data["spatial_model"]["pairwise_relations"]}
            self.assertEqual(pairs[("support_bushing-1", "reference_sensor-1")]["relation"], "overlap")
            self.assertLessEqual(pairs[("support_bushing-1", "reference_sensor-1")]["gap_m"], 0)
            self.assertEqual(pairs[("housing-1", "drive_unit-1")]["relation"], "near")
            self.assertTrue(any(item["object"] == "cover-virtual" for item in data["spatial_model"]["missing_spatial_evidence"]))
            self.assertTrue(any(item["kind"] == "spatial_overlap" for item in data["unknowns_and_risks"]))
            self.assertIn("Spatial relationships", text)
            self.assertIn("support_bushing-1", text)
            self.assertIn("reference_sensor-1", text)


if __name__ == "__main__":
    unittest.main()
