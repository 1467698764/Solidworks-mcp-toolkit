import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGNOSE = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_diagnose.py"
REPAIR_PLAN = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_repair_plan.py"
INTERFACE_INDEX = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_interface_index.py"
MATE_GROUP_PLAN = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_group_plan.py"


def run_py(script: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MateGroupPlanTests(unittest.TestCase):
    def sample_report(self):
        return {
            "active_document": {
                "type": "assembly",
                "title": "mate_group_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "path": "C:/m/cover_plate.SLDPRT", "fixed": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                    {"name2": "bolt_m6-1", "path": "C:/m/bolt_m6.SLDPRT", "fixed": False, "bbox_m": [0.05, 0.05, 0.024, 0.058, 0.058, 0.065]},
                    {"name2": "loose_handle-1", "path": "C:/m/loose_handle.SLDPRT", "fixed": False, "bbox_m": [1.0, 1.0, 1.0, 1.10, 1.10, 1.10]},
                ],
                "mate_like_features": [
                    {"name": "Base_Cover_Coincident", "type": "MateCoincident", "components": ["base_plate-1", "cover_plate-1"], "suppressed": False},
                    {"name": "Broken_Bolt_Mate", "type": "MateConcentric", "components": ["bolt_m6-1", "cover_plate-1"], "suppressed": True, "status": "unsolved", "mate_error": 4},
                ],
                "features": [
                    {"name": "Bolt_Dia6_Z_Shaft", "type": "Boss-Extrude", "components": ["bolt_m6-1"]},
                    {"name": "Cover_Dia6_Z_Hole", "type": "Cut-Extrude", "components": ["cover_plate-1"]},
                ],
                "dimensions": [
                    {"full_name": "D1@Bolt_Dia6_Z_Shaft@bolt_m6.SLDPRT", "feature": "Bolt_Dia6_Z_Shaft", "system_value_m": 0.006},
                    {"full_name": "D1@Cover_Dia6_Z_Hole@cover_plate.SLDPRT", "feature": "Cover_Dia6_Z_Hole", "system_value_m": 0.006},
                ],
            }
        }

    def test_builds_reviewable_groups_from_repair_and_interface_evidence(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            diagnosis = root / "diagnosis.json"
            repair = root / "repair.json"
            interfaces = root / "interfaces.json"
            out = root / "mate_groups.json"
            md = root / "mate_groups.md"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")
            proc = run_py(DIAGNOSE, "--report", str(report), "--out", str(diagnosis), "--standard-part-regex", "bolt|washer|nut|screw")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            proc = run_py(REPAIR_PLAN, "--diagnosis", str(diagnosis), "--out", str(repair))
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            proc = run_py(INTERFACE_INDEX, "--report", str(report), "--out", str(interfaces), "--standard-part-regex", "bolt|washer|nut|screw")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

            proc = run_py(MATE_GROUP_PLAN, "--repair-plan", str(repair), "--interface-index", str(interfaces), "--out", str(out), "--markdown-out", str(md))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["mode"], "read_only_mate_group_plan")
            self.assertEqual(data["document"]["title"], "mate_group_fixture.SLDASM")
            groups = {item["group_id"]: item for item in data["mate_groups"]}
            self.assertIn("repair_Broken_Bolt_Mate", groups)
            self.assertIn("standard_bolt_m6-1", groups)
            self.assertEqual(groups["standard_bolt_m6-1"]["components"], ["bolt_m6-1", "cover_plate-1"])
            self.assertEqual(groups["standard_bolt_m6-1"]["suggested_mates"][0]["type"], "concentric")
            self.assertEqual(groups["standard_bolt_m6-1"]["suggested_mates"][0]["dof_role"], "radial_axis_alignment")
            self.assertEqual(len(groups["standard_bolt_m6-1"]["suggested_mates"][0]["selection_selectors"]), 2)
            self.assertEqual(groups["standard_bolt_m6-1"]["suggested_mates"][1]["type"], "coincident")
            self.assertEqual(groups["standard_bolt_m6-1"]["suggested_mates"][1]["dof_role"], "axial_seating_locator")
            self.assertEqual(len(groups["standard_bolt_m6-1"]["suggested_mates"][1]["selection_selectors"]), 2)
            self.assertEqual(groups["standard_bolt_m6-1"]["dof_expectation"]["intent"], "fully_located_attachment")
            self.assertEqual(groups["standard_bolt_m6-1"]["dof_expectation"]["rotation_about_axis"], "locked")
            self.assertIn("classify_loose_handle-1", groups)
            self.assertEqual(groups["classify_loose_handle-1"]["suggested_mates"], [])
            self.assertIn("requires_live_selection", data["operator_notes"])
            self.assertIn("standard_bolt_m6-1", md.read_text(encoding="utf-8-sig"))

    def test_swctl_routes_mate_group_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            diagnosis = root / "diagnosis.json"
            repair = root / "repair.json"
            interfaces = root / "interfaces.json"
            out = root / "mate_groups.json"
            md = root / "mate_groups.md"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")
            proc = run_py(DIAGNOSE, "--report", str(report), "--out", str(diagnosis), "--standard-part-regex", "bolt|washer|nut|screw")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            proc = run_py(REPAIR_PLAN, "--diagnosis", str(diagnosis), "--out", str(repair))
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            proc = run_py(INTERFACE_INDEX, "--report", str(report), "--out", str(interfaces), "--standard-part-regex", "bolt|washer|nut|screw")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-group-plan",
                    "-Report", str(repair),
                    "-FromReport", str(interfaces),
                    "-Out", str(out),
                    "-JsonOut", str(md),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(any(item["group_id"] == "standard_bolt_m6-1" for item in data["mate_groups"]))


if __name__ == "__main__":
    unittest.main()
