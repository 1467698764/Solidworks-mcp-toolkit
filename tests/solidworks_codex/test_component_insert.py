import json
import tempfile
import unittest
from pathlib import Path

from tools.solidworks_codex.scripts import sw_component_insert as mod


class FakeComponent:
    _oleobj_ = True

    def __init__(self, name):
        self.Name2 = name
        self.selected = []

    def Select4(self, append, data, mark):
        self.selected.append((append, mark))
        return True


class FakeAssembly:
    _oleobj_ = True

    def __init__(self):
        self.insert_calls = []
        self.fixed = False
        self.rebuilt = False
        self.saved = False
        self.component = FakeComponent("bearing-1")

    def GetTitle(self):
        return "fixture.SLDASM"

    def GetPathName(self):
        return "C:/models/fixture.SLDASM"

    def AddComponent5(self, *args):
        self.insert_calls.append(("AddComponent5", args))
        return self.component

    def FixComponent(self):
        self.fixed = True
        return True

    def ForceRebuild3(self, top_only):
        self.rebuilt = True
        return True


class ComponentInsertTests(unittest.TestCase):
    def test_validates_component_insert_spec(self):
        plan = mod.validate_spec({
            "part_path": "C:/parts/bearing.SLDPRT",
            "component_name": "bearing-1",
            "origin_m": [0.1, 0.2, 0.3],
            "fixed": True,
        })

        self.assertEqual(plan["part_path"], "C:/parts/bearing.SLDPRT")
        self.assertEqual(plan["origin_m"], [0.1, 0.2, 0.3])
        self.assertTrue(plan["fixed"])

    def test_executes_component_insert_and_optional_fix(self):
        assembly = FakeAssembly()
        plan = mod.validate_spec({
            "part_path": "C:/parts/bearing.SLDPRT",
            "origin_m": [0.1, 0.2, 0.3],
            "fixed": True,
        })

        result = mod.execute_insert(assembly, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(assembly.insert_calls[0][0], "AddComponent5")
        self.assertEqual(assembly.insert_calls[0][1][-3:], (0.1, 0.2, 0.3))
        self.assertTrue(assembly.fixed)
        self.assertEqual(assembly.component.selected, [(False, 0)])
        self.assertEqual(result["component"]["name"], "bearing-1")

    def test_dry_run_writes_reviewable_insert_plan(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "insert.json"
            out = Path(td) / "out.json"
            spec.write_text(json.dumps({
                "part_path": "C:/parts/bolt.SLDPRT",
                "origin_m": [0, 0.01, 0.02],
                "fixed": False,
            }), encoding="utf-8")

            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = ["sw_component_insert.py", "--spec", str(spec), "--dry-run", "--out", str(out)]
                mod.main()
            finally:
                __import__("sys").argv = old_argv

            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertTrue(data["dry_run"])
            self.assertEqual(data["execution_plan"]["part_path"], "C:/parts/bolt.SLDPRT")


if __name__ == "__main__":
    unittest.main()
