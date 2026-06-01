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


class GenericDesignToolsTests(unittest.TestCase):
    def make_fixture_report(self, root: Path) -> Path:
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
                    {"full_name": "HoleDia@Sketch2@cover_plate.SLDPRT", "system_value_m": 0.0066, "feature": "Sketch2"}
                ],
                "features": [{"name": "HolePattern1", "type": "LPattern"}, {"name": "Cut-Extrude1", "type": "Cut"}]
            }
        }
        path = root / "fixture.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_design_review_outputs_generic_evidence_and_open_questions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_md = root / "review.md"
            out_json = root / "review.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_design_review.py",
                "--report", str(self.make_fixture_report(root)),
                "--intent", "评审齿轮箱夹具的定位销、螺栓孔、盖板装配和加工可行性",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("Mechanical CAD Evidence Review", text)
            self.assertNotIn("Robot Joint", text)
            self.assertNotIn("修改队列", text)
            self.assertIn("open_questions", data)
            self.assertIn("candidate_actions", data)
            categories = {item["category"] for item in data["findings"]}
            self.assertIn("assembly_state", categories)
            self.assertIn("manufacturing_features", categories)
            self.assertTrue(any("dowel_pin-1" in e for f in data["findings"] for e in f.get("evidence", [])))

    def test_change_plan_is_flexible_generic_and_not_fixed_robot_workflow(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_md = root / "plan.md"
            out_json = root / "plan.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_change_plan.py",
                "--report", str(self.make_fixture_report(root)),
                "--goal", "调整盖板螺栓孔并检查定位销装配可行性",
                "--session-name", "fixture-hole-update",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("Mechanical CAD Change Plan", text)
            self.assertNotIn("Robot Joint", text)
            self.assertIn("decision_points", data)
            self.assertIn("optional_branches", data)
            self.assertIn("candidate_actions", data)
            self.assertTrue(any(item["tool"] == "model-understand" for item in data["candidate_actions"]))
            self.assertTrue(any(item["tool"] == "backup" for item in data["candidate_actions"]))
            self.assertTrue(data["requires_backup"])
            self.assertLessEqual(len(data["steps"]), 8)


if __name__ == "__main__":
    unittest.main()
