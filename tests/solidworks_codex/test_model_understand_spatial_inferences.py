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


class ModelUnderstandSpatialInferencesTests(unittest.TestCase):
    def make_report(self, root: Path) -> Path:
        comps = [
            {"name2": "housing-1", "path": "C:/robot/housing.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [-0.05, -0.05, -0.03, 0.05, 0.05, 0.03]},
            {"name2": "drive_unit-1", "path": "C:/cad/projects/sample_machine/drive_unit.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.025, -0.025, -0.09, 0.025, 0.025, -0.031]},
            {"name2": "support_bushing-1", "path": "C:/cad/projects/sample_machine/support_bushing.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.015, -0.015, -0.012, 0.015, 0.015, 0.012]},
            {"name2": "shaft-1", "path": "C:/robot/shaft.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.006, -0.006, -0.11, 0.006, 0.006, 0.06]},
            {"name2": "reference_sensor-1", "path": "C:/cad/projects/sample_machine/reference_sensor.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.012, -0.012, 0.034, 0.012, 0.012, 0.05]},
            {"name2": "off_axis_sensor-1", "path": "C:/robot/sensor.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0.035, 0.035, 0.0, 0.045, 0.045, 0.01]},
        ]
        report = {"active_document": {"title": "axis_stack.SLDASM", "path": "C:/robot/axis_stack.SLDASM", "type": "assembly", "components": comps, "dimensions": [], "features": [{"name": "MateGroup", "type": "MateGroup"}]}}
        path = root / "axis_stack.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_spatial_model_infers_z_stack_coaxial_candidates_and_containment(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_json = root / "understanding.json"
            out_md = root / "understanding.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(self.make_report(root)),
                "--task", "理解电机 轴承 轴 编码器 壳体的同轴和轴向堆叠关系",
                "--view", "spatial-assembly",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            sm = data["spatial_model"]
            self.assertEqual(sm["dominant_axis"], "z")
            stack_names = [item["name"] for item in sm["axis_stack"]]
            self.assertLess(stack_names.index("drive_unit-1"), stack_names.index("support_bushing-1"))
            self.assertLess(stack_names.index("support_bushing-1"), stack_names.index("reference_sensor-1"))
            coax_pairs = {(item["a"], item["b"]) for item in sm["coaxial_candidates"]}
            self.assertTrue(("support_bushing-1", "shaft-1") in coax_pairs or ("shaft-1", "support_bushing-1") in coax_pairs)
            self.assertTrue(("reference_sensor-1", "shaft-1") in coax_pairs or ("shaft-1", "reference_sensor-1") in coax_pairs)
            self.assertNotIn(("off_axis_sensor-1", "shaft-1"), coax_pairs)
            contain_pairs = {(item["container"], item["inside"]) for item in sm["containment_relations"]}
            self.assertIn(("housing-1", "support_bushing-1"), contain_pairs)
            self.assertIn(("shaft-1", "support_bushing-1"), contain_pairs)
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn("Axis stack", text)
            self.assertIn("Coaxial candidates", text)
            self.assertIn("Containment relations", text)


if __name__ == "__main__":
    unittest.main()
