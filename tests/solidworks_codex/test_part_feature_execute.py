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

    def FeatureCircularPattern5(self, *args):
        self.calls.append(("FeatureCircularPattern5", args))
        return {"name": "Codex_CircularPattern"}

    def InsertMirrorFeature2(self, *args):
        self.calls.append(("InsertMirrorFeature2", args))
        return {"name": "Codex_Mirror"}

    def FeatureCut3(self, *args):
        self.calls.append(("FeatureCut3", args))
        return {"name": "Codex_Cut"}

    def HoleWizard5(self, *args):
        self.calls.append(("HoleWizard5", args))
        return {"name": "Codex_HoleWizard"}


class FakeSketchManager:
    _oleobj_ = True

    def __init__(self):
        self.calls = []

    def InsertSketch(self, *args):
        self.calls.append(("InsertSketch", args))
        return True

    def CreateCircleByRadius(self, *args):
        self.calls.append(("CreateCircleByRadius", args))
        return {"name": "Circle"}

    def CreateCenterRectangle(self, *args):
        self.calls.append(("CreateCenterRectangle", args))
        return {"name": "CenterRectangle"}

    def CreateStraightSlot(self, *args):
        self.calls.append(("CreateStraightSlot", args))
        return {"name": "StraightSlot"}


class FakeModel:
    def __init__(self):
        self.Extension = FakeExtension()
        self.FeatureManager = FakeFeatureManager()
        self.SketchManager = FakeSketchManager()
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
        self.assertEqual(plan["operation_role"], "edge_rounding")
        self.assertEqual(plan["selectors"][0]["type"], "EDGE")
        self.assertEqual(plan["parameters"]["radius_mm"], 2.5)

    def test_validates_chamfer_as_edge_break_operation(self):
        plan = mod.validate_spec({
            "operation": "chamfer",
            "selectors": [{"kind": "entity", "name": "Edge<2>@Plate", "type": "EDGE", "point": {"x": 0.1}}],
            "parameters": {"distance_mm": 1.2, "angle_deg": 45},
        })

        self.assertEqual(plan["operation"], "chamfer")
        self.assertEqual(plan["operation_role"], "edge_break")

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
        self.assertEqual(result["operation_role"], "repeat_seed_feature")
        self.assertEqual(result["operation_result"]["pattern_evidence"]["pattern_type"], "linear")
        self.assertEqual(result["operation_result"]["pattern_evidence"]["seed_features"], ["SeedCut"])
        self.assertEqual(result["operation_result"]["pattern_evidence"]["expected_instance_count"], 3)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["spacing_m"], 0.01)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["direction_selector"], "Right Plane")

    def test_circular_pattern_reports_instance_intent_and_axis_selector(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "circular_pattern",
            "selectors": [
                {"kind": "feature", "name": "SeedCut"},
                {"kind": "entity", "name": "Axis1", "type": "AXIS"},
            ],
            "parameters": {"count": 6, "angle_deg": 180},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_result"]["pattern_evidence"]["pattern_type"], "circular")
        self.assertEqual(result["operation_result"]["pattern_evidence"]["expected_instance_count"], 6)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["angle_deg"], 180.0)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["axis_selector"], "Axis1")

    def test_mirror_reports_mirrored_instance_intent_and_plane_selector(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "mirror",
            "selectors": [
                {"kind": "feature", "name": "SeedCut"},
                {"kind": "entity", "name": "Front Plane", "type": "PLANE"},
            ],
            "parameters": {},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_result"]["pattern_evidence"]["pattern_type"], "mirror")
        self.assertEqual(result["operation_result"]["pattern_evidence"]["expected_instance_count"], 2)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["mirror_plane_selector"], "Front Plane")

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
            self.assertEqual(data["operation_role"], "mirror_seed_feature")
            self.assertEqual(data["execution_plan"]["selectors"][1]["type"], "PLANE")

    def test_executes_basic_hole_cut_from_reviewed_plane(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "basic_hole",
            "selectors": [{"kind": "entity", "name": "Front Plane", "type": "PLANE"}],
            "parameters": {"diameter_mm": 6, "depth_mm": 12, "center": {"x": 0.01, "y": 0.02, "z": 0}},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "cylindrical_hole_cut")
        self.assertIn(("CreateCircleByRadius", (0.01, 0.02, 0.0, 0.003)), model.SketchManager.calls)
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")

    def test_executes_countersink_hole_with_reviewed_hole_wizard_metadata(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "countersink_hole",
            "selectors": [{"kind": "entity", "name": "Front Plane", "type": "PLANE"}],
            "parameters": {
                "diameter_mm": 5,
                "depth_mm": 18,
                "countersink_diameter_mm": 10,
                "countersink_angle_deg": 82,
                "center": {"x": 0.01, "y": 0.02, "z": 0},
            },
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(plan["selectors"][0]["point"], {"x": 0.01, "y": 0.02, "z": 0.0})
        self.assertEqual(result["operation_role"], "countersunk_hole_cut")
        self.assertEqual(model.FeatureManager.calls[-1][0], "HoleWizard5")
        self.assertEqual(result["operation_result"]["hole_variant"], "countersink")
        self.assertEqual(result["operation_result"]["hole_metadata"]["diameter_m"], 0.005)
        self.assertEqual(result["operation_result"]["hole_metadata"]["countersink_diameter_m"], 0.01)
        self.assertEqual(result["operation_result"]["hole_metadata"]["countersink_angle_deg"], 82.0)
        self.assertEqual(result["operation_result"]["wizard_call"]["method"], "HoleWizard5")

    def test_executes_counterbore_hole_with_reviewed_hole_wizard_metadata(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "counterbore_hole",
            "selectors": [{"kind": "entity", "name": "Front Plane", "type": "PLANE"}],
            "parameters": {
                "diameter_mm": 6,
                "depth_mm": 20,
                "counterbore_diameter_mm": 12,
                "counterbore_depth_mm": 4,
                "center": {"x": 0.01, "y": 0.02, "z": 0},
            },
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "counterbored_hole_cut")
        self.assertEqual(model.FeatureManager.calls[-1][0], "HoleWizard5")
        self.assertEqual(result["operation_result"]["hole_variant"], "counterbore")
        self.assertEqual(result["operation_result"]["hole_metadata"]["diameter_m"], 0.006)
        self.assertEqual(result["operation_result"]["hole_metadata"]["counterbore_diameter_m"], 0.012)
        self.assertEqual(result["operation_result"]["hole_metadata"]["counterbore_depth_m"], 0.004)
        self.assertEqual(result["operation_result"]["wizard_call"]["method"], "HoleWizard5")

    def test_executes_extrude_cut_from_reviewed_sketch(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "extrude_cut",
            "selectors": [{"kind": "entity", "name": "CutSketch", "type": "SKETCH"}],
            "parameters": {"depth_mm": 9},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "reviewed_profile_extrude_cut")
        self.assertEqual(model.Extension.calls[0][0], "SelectByID2")
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")
        self.assertEqual(result["operation_result"]["cut"]["method"], "FeatureCut3")

    def test_executes_slot_cut_from_reviewed_plane(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "slot_cut",
            "selectors": [{"kind": "entity", "name": "Top Plane", "type": "PLANE"}],
            "parameters": {"length_mm": 40, "width_mm": 8, "depth_mm": 5, "center": {"x": 0, "y": 0, "z": 0}},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "slot_profile_cut")
        self.assertTrue(any(call[0] == "CreateStraightSlot" for call in model.SketchManager.calls))
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")

    def test_executes_pocket_cut_from_reviewed_plane(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "pocket_cut",
            "selectors": [{"kind": "entity", "name": "Top Plane", "type": "PLANE"}],
            "parameters": {"width_mm": 20, "height_mm": 10, "depth_mm": 4, "center": {"x": 0, "y": 0, "z": 0}},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "rectangular_pocket_cut")
        self.assertTrue(any(call[0] == "CreateCenterRectangle" for call in model.SketchManager.calls))
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")


if __name__ == "__main__":
    unittest.main()
