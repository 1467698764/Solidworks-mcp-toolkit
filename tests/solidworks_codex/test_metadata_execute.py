import json
import tempfile
import unittest
from pathlib import Path

from tools.solidworks_codex.scripts import sw_metadata_execute as mod


class FakePropertyManager:
    _oleobj_ = True

    def __init__(self):
        self.calls = []

    def Add3(self, name, property_type, value, option):
        self.calls.append(("Add3", name, property_type, value, option))
        return 0

    def Set2(self, name, value):
        self.calls.append(("Set2", name, value))
        return 0


class FakeExtension:
    _oleobj_ = True

    def __init__(self):
        self.manager = FakePropertyManager()

    def CustomPropertyManager(self, configuration):
        return self.manager


class FakeModel:
    _oleobj_ = True

    def __init__(self):
        self.Extension = FakeExtension()
        self.material_calls = []
        self.rebuilt = False

    def GetTitle(self):
        return "plate.SLDPRT"

    def GetPathName(self):
        return "C:/models/plate.SLDPRT"

    def ConfigurationManager(self):
        return None

    def SetMaterialPropertyName2(self, config, database, material):
        self.material_calls.append((config, database, material))
        return True

    def ForceRebuild3(self, top_only):
        self.rebuilt = True
        return True


class MetadataExecuteTests(unittest.TestCase):
    def test_validates_material_and_properties_spec(self):
        plan = mod.validate_spec({
            "material": "Plain Carbon Steel",
            "properties": {"PartNo": "A-100", "Finish": "Black oxide"},
            "configuration": "Default",
        })

        self.assertEqual(plan["material"], "Plain Carbon Steel")
        self.assertEqual(plan["properties"]["PartNo"], "A-100")
        self.assertEqual(plan["configuration"], "Default")

    def test_executes_material_and_custom_property_writes(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "material": "Plain Carbon Steel",
            "properties": {"PartNo": "A-100", "Finish": "Black oxide"},
            "configuration": "Default",
        })

        result = mod.execute_metadata(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(model.material_calls, [("Default", "", "Plain Carbon Steel")])
        calls = model.Extension.manager.calls
        self.assertIn(("Add3", "PartNo", 30, "A-100", 1), calls)
        self.assertIn(("Set2", "Finish", "Black oxide"), calls)

    def test_dry_run_writes_reviewable_metadata_plan(self):
        with tempfile.TemporaryDirectory() as td:
            spec = Path(td) / "metadata.json"
            out = Path(td) / "out.json"
            spec.write_text(json.dumps({
                "material": "6061 Aluminum",
                "properties": {"Vendor": "local"},
            }), encoding="utf-8")

            old_argv = __import__("sys").argv
            try:
                __import__("sys").argv = ["sw_metadata_execute.py", "--spec", str(spec), "--dry-run", "--out", str(out)]
                mod.main()
            finally:
                __import__("sys").argv = old_argv

            data = json.loads(out.read_text(encoding="utf-8"))
            self.assertTrue(data["ok"])
            self.assertTrue(data["dry_run"])
            self.assertEqual(data["execution_plan"]["material"], "6061 Aluminum")


if __name__ == "__main__":
    unittest.main()
