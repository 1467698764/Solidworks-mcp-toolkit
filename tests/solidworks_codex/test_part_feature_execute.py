import json
import tempfile
import unittest
from pathlib import Path

from tools.solidworks_codex.scripts import sw_part_feature_execute as mod


class FakeExtension:
    _oleobj_ = True

    def __init__(self):
        self.calls = []

    def SelectByID2(self, *args):
        self.calls.append(("SelectByID2", args))
        return True


class FakeFeature:
    _oleobj_ = True

    def __init__(self, name):
        self.Name = name
        self.selected = []
        self.next = None

    def GetNameForSelection(self):
        return self.Name

    def GetNextFeature(self):
        return self.next

    def Select2(self, append, mark):
        self.selected.append((append, mark))
        return True


class FakeFeatureManager:
    _oleobj_ = True

    def __init__(self):
        self.calls = []

    def FeatureFillet3(self, *args):
        self.calls.append(("FeatureFillet3", args))
        return {"name": "Codex_Fillet"}

    def FeatureLinearPattern5(self, *args):
        self.calls.append(("FeatureLinearPattern5", args))
        return {"name": "Codex_LinearPattern"}

    def InsertMirrorFeature2(self, *args):
        self.calls.append(("InsertMirrorFeature2", args))
        return {"name": "Codex_Mirror"}


class FakeModel:
    def __init__(self):
        self.Extension = FakeExtension()
        self.FeatureManager = FakeFeatureManager()
        self.seed = FakeFeature("SeedCut")

    def FirstFeature(self):
        return self.seed

    def ClearSelection2(self, clear):
        return True


class PartFeatureExecuteTests(unittest.TestCase):
    def test_validates_fillet_edge_selectors_and_radius(self):
        plan = mod.validate_spec({
            "operation": "fillet",
            "selectors": [{"kind": "entity", "name": "Edge<1>@Plate", "type": "EDGE", "point": {"x": 0.1}}],
            "parameters": {"radius_mm": 2.5},
        })

        self.assertEqual(plan["operation"], "fillet")
        self.assertEqual(plan["selectors"][0]["type"], "EDGE")
        self.assertEqual(plan["parameters"]["radius_mm"], 2.5)

    def test_rejects_pattern_without_seed_feature(self):
        with self.assertRaisesRegex(ValueError, "seed feature"):
            mod.validate_spec({
                "operation": "linear_pattern",
                "selectors": [{"kind": "entity", "name": "Right Plane", "type": "PLANE"}],
                "parameters": {"count": 4, "spacing_mm": 12},
            })

    def test_executes_feature_and_entity_selection_before_feature_call(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "linear_pattern",
            "selectors": [
                {"kind": "feature", "name": "SeedCut"},
                {"kind": "entity", "name": "Right Plane", "type": "PLANE"},
            ],
            "parameters": {"count": 3, "spacing_mm": 10},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(model.seed.selected, [(False, 0)])
        self.assertEqual(model.Extension.calls[0][0], "SelectByID2")
        self.assertEqual(model.FeatureManager.calls[0][0], "FeatureLinearPattern5")
        self.assertEqual(model.FeatureManager.calls[0][1][0], 3)
        self.assertAlmostEqual(model.FeatureManager.calls[0][1][2], 0.01)

    def test_dry_run_writes_reviewable_execution_plan(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "mirror.json"
            out = Path(td) / "out.json"
            spec.write_text(json.dumps({
                "operation": "mirror",
                "selectors": [
                    {"kind": "feature", "name": "SeedCut"},
                    {"kind": "entity", "name": "Front Plane", "type": "PLANE"},
                ],
                "parameters": {},
            }), encoding="utf-8")

            proc_args = ["--spec", str(spec), "--dry-run", "--out", str(out)]
            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = ["sw_part_feature_execute.py", *proc_args]
                mod.main()
            finally:
                __import__("sys").argv = old_argv

            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertTrue(data["dry_run"])
            self.assertEqual(data["operation"], "mirror")
            self.assertEqual(data["execution_plan"]["selectors"][1]["type"], "PLANE")


if __name__ == "__main__":
    unittest.main()
