import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.solidworks_codex.scripts import sw_mate_group_execute as mod

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_group_execute.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class FakeExtension:
    def __init__(self):
        self.calls = []

    def SelectByID2(self, name, entity_type, x, y, z, append, mark, callout, option):
        self.calls.append(
            {
                "name": name,
                "type": entity_type,
                "xyz": [x, y, z],
                "append": append,
                "mark": mark,
                "option": option,
            }
        )
        return True


class FakeSelectionManager:
    def __init__(self, extension):
        self.extension = extension

    def GetSelectedObjectCount2(self, mark):
        return len(self.extension.calls)


class FakeFeature:
    def __init__(self):
        self.Name = ""


class FakeAssembly:
    def __init__(self):
        self.Extension = FakeExtension()
        self.SelectionManager = FakeSelectionManager(self.Extension)
        self.cleared = []
        self.mates = []
        self.rebuilds = []

    def ClearSelection2(self, value):
        self.cleared.append(value)
        self.Extension.calls.clear()

    def AddMate5(self, *args):
        self.mates.append(args)
        return FakeFeature()

    def ForceRebuild3(self, value):
        self.rebuilds.append(value)
        return True


class MateGroupExecuteTests(unittest.TestCase):
    def manifest(self):
        return {
            "mode": "reviewable_mate_group_macros",
            "macros": [
                {
                    "group_id": "standard_bolt_m6-1",
                    "mate_type": "coincident",
                    "expected_mate_name": "MG_standard_bolt_m6_1_02_coincident",
                    "components": ["bolt_m6-1", "cover_plate-1"],
                    "selection_selectors": [
                        {
                            "stable_id": "bolt_m6-1:plane:z_min",
                            "component": "bolt_m6-1",
                            "fallback": {
                                "type": "bbox_planar_face",
                                "origin_m": [0.054, 0.054, 0.024],
                            },
                        },
                        {
                            "stable_id": "cover_plate-1:plane:z_max",
                            "component": "cover_plate-1",
                            "fallback": {
                                "type": "bbox_planar_face",
                                "origin_m": [0.1, 0.05, 0.024],
                            },
                        },
                    ],
                }
            ],
        }

    def test_executes_reviewed_selectors_with_addmate5_and_rebuild(self):
        asm = FakeAssembly()

        result = mod.execute_manifest(self.manifest(), asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["counts"]["executed_mates"], 1)
        mate = result["executed_mates"][0]
        self.assertEqual(mate["expected_mate_name"], "MG_standard_bolt_m6_1_02_coincident")
        self.assertEqual(mate["selected_entities"], 2)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["coincident"])
        self.assertEqual(asm.rebuilds, [False])
        self.assertEqual([call["type"] for call in mate["selection_guard"]["select_by_id_calls"]], ["FACE", "FACE"])

    def test_dry_run_reports_selector_actions_without_solidworks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            out = root / "execute.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest), "--out", str(out), "--dry-run")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["mode"], "mate_group_live_execute")
            self.assertEqual(data["counts"]["planned_mates"], 1)
            self.assertEqual(data["planned_mates"][0]["selection_actions"][0]["type"], "FACE")

    def test_swctl_routes_mate_group_execute_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "manifest.json"
            out = root / "execute.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-group-execute",
                    "-Report",
                    str(manifest),
                    "-Out",
                    str(out),
                    "-ValidateOnly",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["counts"]["planned_mates"], 1)


if __name__ == "__main__":
    unittest.main()
