import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_diagnose.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class AssemblyDiagnosisTests(unittest.TestCase):
    def sample_report(self):
        return {
            "active_document": {
                "type": "assembly",
                "title": "sample_machine.SLDASM",
                "component_count_sampled": 7,
                "components": [
                    {"name2": "base_plate-1", "path": "C:/machines/base_plate.SLDPRT", "configuration": "Default", "fixed": True, "suppressed": False, "hidden": False, "bbox_m": [-0.15, -0.10, 0.0, 0.15, 0.10, 0.012], "transform_array": [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.01, 0.02, 0.03, 1.0, 0.0, 0.0, 0.0]},
                    {"name2": "cover_plate-1", "path": "C:/machines/cover_plate.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [-0.14, -0.09, 0.012, 0.14, 0.09, 0.026]},
                    {"name2": "dowel_pin-1", "path": "C:/machines/dowel_pin.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [-0.04, -0.03, -0.004, -0.034, -0.024, 0.05]},
                    {"name2": "shaft-1", "path": "C:/machines/shaft.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [0.02, -0.01, 0.026, 0.12, 0.01, 0.046]},
                    {"name2": "bearing_block-1", "path": "C:/machines/bearing_block.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [0.015, -0.03, 0.020, 0.125, 0.03, 0.062]},
                    {"name2": "bolt_m6-1", "path": "C:/machines/bolt_m6.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [0.05, 0.05, 0.026, 0.058, 0.058, 0.07]},
                    {"name2": "loose_handle-1", "path": "C:/machines/loose_handle.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [1.0, 1.0, 1.0, 1.1, 1.1, 1.1]},
                ],
                "mate_like_features": [
                    {"name": "Base_Cover_Coincident", "type": "MateCoincident", "components": ["base_plate-1", "cover_plate-1"], "suppressed": False},
                    {"name": "Pin_Base_Concentric", "type": "MateConcentric", "components": ["dowel_pin-1", "base_plate-1"], "suppressed": False},
                    {"name": "Shaft_Bearing_Concentric", "type": "MateConcentric", "components": ["shaft-1", "bearing_block-1"], "suppressed": False},
                    {"name": "Broken_Mate", "type": "MateDistanceDim", "components": ["cover_plate-1", "loose_handle-1"], "suppressed": True, "status": "unsolved", "mate_error": 4},
                ],
            }
        }

    def test_diagnosis_identifies_mate_graph_isolated_and_hostless_components(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            out = root / "assembly_diagnosis.json"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")

            proc = run_py("--report", str(report), "--out", str(out), "--standard-part-regex", "bolt|washer|nut|screw|pin")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            self.assertEqual(data["document"]["type"], "assembly")
            self.assertEqual(data["inventory"]["component_count"], 7)
            self.assertEqual(data["inventory"]["fixed_components"], ["base_plate-1"])
            components = {item["name"]: item for item in data["inventory"]["components"]}
            base = components["base_plate-1"]
            self.assertEqual(base["path"], "C:/machines/base_plate.SLDPRT")
            self.assertEqual(base["configuration"], "Default")
            self.assertEqual(base["bbox_m"], [-0.15, -0.10, 0.0, 0.15, 0.10, 0.012])
            self.assertEqual(base["size_m"], [0.3, 0.2, 0.012])
            self.assertTrue(base["fixed"])
            self.assertFalse(base["suppressed"])
            self.assertFalse(base["hidden"])
            self.assertEqual(base["origin_m"], [0.01, 0.02, 0.03])
            self.assertEqual(base["local_axes"]["x"], [1.0, 0.0, 0.0])
            self.assertIn("loose_handle-1", data["mate_graph"]["isolated_components"])
            self.assertIn("bolt_m6-1", data["mate_graph"]["no_mate_components"])
            self.assertIn("bolt_m6-1", data["standard_parts"]["hostless"])
            self.assertEqual(data["mate_graph"]["mate_type_distribution"]["MateConcentric"], 2)
            mate_details = {item["name"]: item for item in data["mates"]["details"]}
            broken = mate_details["Broken_Mate"]
            self.assertEqual(broken["mate_type"], "MateDistanceDim")
            self.assertEqual(broken["participants"], ["cover_plate-1", "loose_handle-1"])
            self.assertTrue(broken["suppressed"])
            self.assertEqual(broken["status"], "unsolved")
            self.assertEqual(broken["mate_error"], 4)
            self.assertTrue(broken["bad"])
            graph_edges = {(item["mate"], tuple(item["components"]), item["bad"]) for item in data["mate_graph"]["edges"]}
            self.assertIn(("Base_Cover_Coincident", ("base_plate-1", "cover_plate-1"), False), graph_edges)
            self.assertIn("Broken_Mate", data["mates"]["bad_mates"])
            self.assertTrue(any(pair["a"] == "base_plate-1" and pair["b"] == "cover_plate-1" for pair in data["spatial"]["near_or_touching_pairs"]))
            self.assertFalse(any(item["kind"] == "isolated_functional_component" for item in data["findings"]["blocking"]))
            self.assertTrue(any(item["kind"] == "isolated_component" for item in data["findings"]["warning"]))
            self.assertTrue(any(item["kind"] == "hostless_standard_part" for item in data["findings"]["blocking"]))

    def test_diagnosis_cli_can_scan_lock_files_without_solidworks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            locks = root / "generated"
            locks.mkdir()
            (locks / "~$sample_machine.SLDASM").write_text("", encoding="utf-8")
            out = root / "assembly_diagnosis.json"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")

            proc = run_py("--report", str(report), "--out", str(out), "--lock-root", str(locks))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(data["runtime"]["lock_files"]), 1)
            self.assertTrue(data["runtime"]["lock_files"][0].endswith("~$sample_machine.SLDASM"))

    def test_swctl_routes_assembly_diagnose(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            out = root / "assembly_diagnosis.json"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "assembly-diagnose",
                    "-Report",
                    str(report),
                    "-Out",
                    str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(out.exists())
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertIn("mate_graph", data)


if __name__ == "__main__":
    unittest.main()
