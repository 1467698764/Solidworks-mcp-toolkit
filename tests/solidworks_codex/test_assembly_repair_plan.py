import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DIAGNOSE = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_diagnose.py"
REPAIR_PLAN = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_assembly_repair_plan.py"


def run_py(script: Path, *args: str):
    return subprocess.run(
        [sys.executable, str(script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class AssemblyRepairPlanTests(unittest.TestCase):
    def sample_report(self):
        return {
            "active_document": {
                "type": "assembly",
                "title": "repair_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/machines/base_plate.SLDPRT", "fixed": True, "suppressed": False, "hidden": False, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "path": "C:/machines/cover_plate.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                    {"name2": "bolt_m6-1", "path": "C:/machines/bolt_m6.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [0.05, 0.05, 0.024, 0.058, 0.058, 0.065]},
                    {"name2": "loose_handle-1", "path": "C:/machines/loose_handle.SLDPRT", "fixed": False, "suppressed": False, "hidden": False, "bbox_m": [1.0, 1.0, 1.0, 1.10, 1.10, 1.10]},
                ],
                "mate_like_features": [
                    {"name": "Base_Cover_Coincident", "type": "MateCoincident", "components": ["base_plate-1", "cover_plate-1"], "suppressed": False},
                    {"name": "Broken_Bolt_Mate", "type": "MateConcentric", "components": ["bolt_m6-1", "cover_plate-1"], "suppressed": True, "status": "unsolved", "mate_error": 4},
                ],
            }
        }

    def test_repair_plan_prioritizes_bad_mates_standard_hosts_and_intent_questions(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            diagnosis = root / "diagnosis.json"
            out_json = root / "repair_plan.json"
            out_md = root / "repair_plan.md"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")
            proc = run_py(DIAGNOSE, "--report", str(report), "--out", str(diagnosis), "--standard-part-regex", "bolt|washer|nut|screw")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

            proc = run_py(REPAIR_PLAN, "--diagnosis", str(diagnosis), "--out", str(out_json), "--markdown-out", str(out_md))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["mode"], "read_only_plan")
            self.assertEqual(data["document"]["title"], "repair_fixture.SLDASM")
            actions = data["actions"]
            self.assertLess(
                next(i for i, item in enumerate(actions) if item["kind"] == "resolve_bad_mate"),
                next(i for i, item in enumerate(actions) if item["kind"] == "attach_hostless_standard_part"),
            )
            self.assertTrue(any(item["kind"] == "resolve_bad_mate" and item["target"] == "Broken_Bolt_Mate" for item in actions))
            bad_mate_action = next(item for item in actions if item["kind"] == "resolve_bad_mate")
            self.assertEqual(bad_mate_action["affected_subgraph"]["components"], ["bolt_m6-1", "cover_plate-1"])
            self.assertEqual(bad_mate_action["affected_subgraph"]["mates"], ["Broken_Bolt_Mate"])
            self.assertEqual(
                bad_mate_action["affected_subgraph"]["component_paths"],
                {
                    "bolt_m6-1": "C:/machines/bolt_m6.SLDPRT",
                    "cover_plate-1": "C:/machines/cover_plate.SLDPRT",
                },
            )
            self.assertIn("bad_mate_participants", bad_mate_action["affected_subgraph"]["evidence"])
            host_actions = [item for item in actions if item["kind"] == "attach_hostless_standard_part"]
            self.assertEqual(host_actions[0]["target"], "bolt_m6-1")
            self.assertEqual(host_actions[0]["suggested_host"], "cover_plate-1")
            self.assertEqual(host_actions[0]["affected_subgraph"]["components"], ["bolt_m6-1", "cover_plate-1"])
            self.assertIn("nearest_spatial_host", host_actions[0]["affected_subgraph"]["evidence"])
            self.assertTrue(any(item["kind"] == "classify_isolated_component" and item["target"] == "loose_handle-1" for item in actions))
            rollback = data["rollback_plan"]
            self.assertEqual("rollback_plan", rollback["artifact"])
            self.assertEqual(
                rollback["affected_files"],
                [
                    "C:/machines/bolt_m6.SLDPRT",
                    "C:/machines/cover_plate.SLDPRT",
                    "C:/machines/loose_handle.SLDPRT",
                ],
            )
            self.assertIn("backup -Files", rollback["backup_command"])
            self.assertIn("restore-backup -Report", rollback["restore_command"])
            self.assertTrue(rollback["blocks_mutation_without_backup"])
            self.assertEqual(rollback["guard"]["required_before_action_kinds"], ["attach_hostless_standard_part", "resolve_bad_mate"])
            self.assertEqual(rollback["guard"]["backup_status_required"], "ok")
            self.assertEqual(rollback["backup_execution"]["tool"], "backup")
            self.assertEqual(rollback["backup_execution"]["files"], rollback["affected_files"])
            self.assertEqual(rollback["backup_status_execution"]["tool"], "backup-status")
            self.assertEqual(rollback["restore_execution"]["tool"], "restore-backup")
            self.assertTrue(rollback["restore_execution"]["apply"])
            self.assertEqual(bad_mate_action["mutation_preconditions"]["rollback_backup_report"], rollback["backup_report"])
            self.assertEqual(bad_mate_action["mutation_preconditions"]["backup_status_required"], "ok")
            self.assertIn("rollback_report_paths_are_required_before_mutation", data["operator_notes"])
            self.assertIn("do_not_apply_blindly", data["operator_notes"])
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn("Broken_Bolt_Mate", text)
            self.assertIn("Rollback Plan", text)

    def test_swctl_routes_assembly_repair_plan(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            diagnosis = root / "diagnosis.json"
            out_json = root / "repair_plan.json"
            out_md = root / "repair_plan.md"
            report.write_text(json.dumps(self.sample_report()), encoding="utf-8")
            proc = run_py(DIAGNOSE, "--report", str(report), "--out", str(diagnosis), "--standard-part-regex", "bolt|washer|nut|screw")
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "assembly-repair-plan",
                    "-Report", str(diagnosis),
                    "-Out", str(out_json),
                    "-JsonOut", str(out_md),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(out_json.exists())
            self.assertTrue(out_md.exists())
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertTrue(any(item["kind"] == "resolve_bad_mate" for item in data["actions"]))


if __name__ == "__main__":
    unittest.main()
