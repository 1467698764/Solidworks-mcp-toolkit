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


class ModelUnderstandGenericMechanicalTests(unittest.TestCase):
    def make_report(self, root: Path) -> Path:
        report = {
            "active_document": {
                "title": "gearbox_fixture.SLDASM",
                "path": "C:/machines/gearbox_fixture.SLDASM",
                "type": "assembly",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/machines/base_plate.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [-0.12, -0.08, -0.01, 0.12, 0.08, 0.0]},
                    {"name2": "gearbox_housing-1", "path": "C:/machines/gearbox_housing.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.05, -0.04, 0.0, 0.05, 0.04, 0.06]},
                    {"name2": "cover_plate-1", "path": "C:/machines/cover_plate.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.052, -0.042, 0.058, 0.052, 0.042, 0.066]},
                    {"name2": "dowel_pin-1", "path": "C:/machines/dowel_pin.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.046, -0.036, -0.005, -0.041, -0.031, 0.064]},
                    {"name2": "bolt_m6-1", "path": "C:/machines/bolt_m6.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0.04, 0.03, -0.006, 0.047, 0.037, 0.068]},
                ],
                "dimensions": [
                    {"full_name": "D1@Sketch1@base_plate.SLDPRT", "system_value_m": 0.24, "feature": "Sketch1"},
                    {"full_name": "HoleDia@Sketch2@cover_plate.SLDPRT", "system_value_m": 0.0066, "feature": "Sketch2"}
                ],
                "features": [{"name": "HolePattern1", "type": "LPattern"}, {"name": "Cut-Extrude1", "type": "Cut"}]
            }
        }
        path = root / "gearbox_fixture.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_understanding_is_generic_mechanical_not_robot_joint_template(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_json = root / "understanding.json"
            out_md = root / "understanding.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(self.make_report(root)),
                "--task", "理解这个齿轮箱夹具的装配、定位销、螺栓孔、盖板加工可行性",
                "--view", "auto",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn(data["scope"]["view"], {"manufacturing-holes", "spatial-assembly"})
            domain_names = {d["domain"] for d in data["task_model"]["domains"]}
            self.assertIn("locating_fastening", domain_names)
            self.assertIn("manufacturing_features", domain_names)
            names = {o["name"] for o in data["task_model"]["relevant_objects"]}
            self.assertIn("dowel_pin-1", names)
            self.assertIn("bolt_m6-1", names)
            forbidden = "robot joint bearing encoder motor output flange".split()
            combined = json.dumps(data, ensure_ascii=False).lower() + text.lower()
            for word in forbidden:
                self.assertNotIn(word, combined)


if __name__ == "__main__":
    unittest.main()
