import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_group_macro.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MateGroupMacroTests(unittest.TestCase):
    def sample_plan(self):
        return {
            "mode": "read_only_mate_group_plan",
            "document": {"title": "macro_fixture.SLDASM"},
            "mate_groups": [
                {
                    "group_id": "standard_bolt_m6-1",
                    "source_action": "attach_hostless_standard_part",
                    "priority": "P1",
                    "components": ["bolt_m6-1", "cover_plate-1"],
                    "suggested_mates": [
                        {"type": "concentric", "selection_intent": "bolt axis to cover hole axis", "lock_rotation": True},
                        {"type": "coincident", "selection_intent": "bolt head underside to cover top face"},
                    ],
                    "verification": ["rebuild", "mate_errors"],
                },
                {
                    "group_id": "classify_handle-1",
                    "source_action": "classify_isolated_component",
                    "priority": "P2",
                    "components": ["handle-1"],
                    "suggested_mates": [],
                    "verification": ["design_intent_confirmed_before_mating"],
                },
            ],
        }

    def test_generates_reviewable_preselect_macros_per_actionable_mate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out_dir = root / "macros"
            manifest = root / "macro_manifest.json"
            plan.write_text(json.dumps(self.sample_plan()), encoding="utf-8")

            proc = run_py("--mate-group-plan", str(plan), "--out-dir", str(out_dir), "--manifest", str(manifest))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["mode"], "reviewable_mate_group_macros")
            self.assertEqual(data["document"]["title"], "macro_fixture.SLDASM")
            self.assertEqual(len(data["macros"]), 2)
            self.assertEqual(data["skipped"][0]["group_id"], "classify_handle-1")
            first_macro = Path(data["macros"][0]["macro"])
            self.assertTrue(first_macro.exists())
            text = first_macro.read_text(encoding="utf-8")
            self.assertIn("Preselect exactly two mate entities", text)
            self.assertIn("Group: standard_bolt_m6-1", text)
            self.assertIn("Mate type: concentric", text)
            self.assertTrue(data["preselect_required"])

    def test_swctl_routes_mate_group_macro(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            plan = root / "mate_group_plan.json"
            out_dir = root / "macros"
            manifest = root / "macro_manifest.json"
            plan.write_text(json.dumps(self.sample_plan()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-group-macro",
                    "-Report", str(plan),
                    "-OutDir", str(out_dir),
                    "-Out", str(manifest),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(data["macros"]), 2)


if __name__ == "__main__":
    unittest.main()
