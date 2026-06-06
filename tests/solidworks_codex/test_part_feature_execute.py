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


class FakeCreatedFeature:
    _oleobj_ = True

    def __init__(self, name):
        self.Name = name


class FakeFeatureManager:
    _oleobj_ = True

    def __init__(self):
        self.calls = []

    def FeatureFillet3(self, *args):
        self.calls.append(("FeatureFillet3", args))
        return FakeCreatedFeature("Codex_Fillet")

    def FeatureChamfer3(self, *args):
        self.calls.append(("FeatureChamfer3", args))
        return FakeCreatedFeature("Codex_Chamfer")

    def FeatureLinearPattern5(self, *args):
        self.calls.append(("FeatureLinearPattern5", args))
        return FakeCreatedFeature("Codex_LinearPattern")

    def FeatureCircularPattern5(self, *args):
        self.calls.append(("FeatureCircularPattern5", args))
        return FakeCreatedFeature("Codex_CircularPattern")

    def InsertMirrorFeature2(self, *args):
        self.calls.append(("InsertMirrorFeature2", args))
        return FakeCreatedFeature("Codex_Mirror")

    def FeatureCut3(self, *args):
        self.calls.append(("FeatureCut3", args))
        return FakeCreatedFeature("Codex_Cut")

    def FeatureExtrusion3(self, *args):
        self.calls.append(("FeatureExtrusion3", args))
        return FakeCreatedFeature("Codex_BossExtrude")

    def FeatureRevolve2(self, *args):
        self.calls.append(("FeatureRevolve2", args))
        return FakeCreatedFeature("Codex_Revolve")

    def FeatureRevolveCut2(self, *args):
        self.calls.append(("FeatureRevolveCut2", args))
        return FakeCreatedFeature("Codex_RevolvedCut")

    def HoleWizard5(self, *args):
        self.calls.append(("HoleWizard5", args))
        return FakeCreatedFeature("Codex_HoleWizard")


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

    def test_executes_fillet_and_names_reviewed_feature(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "fillet",
            "selectors": [{"kind": "entity", "name": "Edge<1>@Plate", "type": "EDGE", "point": {"x": 0.1}}],
            "parameters": {"radius_mm": 2.5, "feature_name": "ReviewedEdgeRound"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedEdgeRound")
        self.assertEqual(result["operation_result"]["fillet"]["assigned_feature_name"], "ReviewedEdgeRound")
        self.assertEqual(result["operation_result"]["fillet"]["raw"].Name, "ReviewedEdgeRound")

    def test_executes_chamfer_and_names_reviewed_feature(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "chamfer",
            "selectors": [{"kind": "entity", "name": "Edge<2>@Plate", "type": "EDGE", "point": {"x": 0.1}}],
            "parameters": {"distance_mm": 1.2, "angle_deg": 45, "feature_name": "ReviewedEdgeBreak"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedEdgeBreak")
        self.assertEqual(result["operation_result"]["chamfer"]["assigned_feature_name"], "ReviewedEdgeBreak")
        self.assertEqual(result["operation_result"]["chamfer"]["raw"].Name, "ReviewedEdgeBreak")

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
            "parameters": {"count": 3, "spacing_mm": 10, "feature_name": "ReviewedLinearPattern"},
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
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedLinearPattern")
        self.assertEqual(result["operation_result"]["call"]["assigned_feature_name"], "ReviewedLinearPattern")

    def test_circular_pattern_reports_instance_intent_and_axis_selector(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "circular_pattern",
            "selectors": [
                {"kind": "feature", "name": "SeedCut"},
                {"kind": "entity", "name": "Axis1", "type": "AXIS"},
            ],
            "parameters": {"count": 6, "angle_deg": 180, "feature_name": "ReviewedCircularPattern"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_result"]["pattern_evidence"]["pattern_type"], "circular")
        self.assertEqual(result["operation_result"]["pattern_evidence"]["expected_instance_count"], 6)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["angle_deg"], 180.0)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["axis_selector"], "Axis1")
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedCircularPattern")
        self.assertEqual(result["operation_result"]["call"]["assigned_feature_name"], "ReviewedCircularPattern")

    def test_mirror_reports_mirrored_instance_intent_and_plane_selector(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "mirror",
            "selectors": [
                {"kind": "feature", "name": "SeedCut"},
                {"kind": "entity", "name": "Front Plane", "type": "PLANE"},
            ],
            "parameters": {"feature_name": "ReviewedMirror"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_result"]["pattern_evidence"]["pattern_type"], "mirror")
        self.assertEqual(result["operation_result"]["pattern_evidence"]["expected_instance_count"], 2)
        self.assertEqual(result["operation_result"]["pattern_evidence"]["mirror_plane_selector"], "Front Plane")
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedMirror")
        self.assertEqual(result["operation_result"]["call"]["assigned_feature_name"], "ReviewedMirror")

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
            "parameters": {"diameter_mm": 6, "depth_mm": 12, "center": {"x": 0.01, "y": 0.02, "z": 0}, "feature_name": "ReviewedPilotHole"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "cylindrical_hole_cut")
        self.assertIn(("CreateCircleByRadius", (0.01, 0.02, 0.0, 0.003)), model.SketchManager.calls)
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedPilotHole")
        self.assertEqual(result["operation_result"]["cut"]["assigned_feature_name"], "ReviewedPilotHole")

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
                "feature_name": "ReviewedCountersink",
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
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedCountersink")
        self.assertEqual(result["operation_result"]["wizard_call"]["assigned_feature_name"], "ReviewedCountersink")

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
                "feature_name": "ReviewedCounterbore",
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
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedCounterbore")
        self.assertEqual(result["operation_result"]["wizard_call"]["assigned_feature_name"], "ReviewedCounterbore")

    def test_executes_extrude_cut_from_reviewed_sketch(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "extrude_cut",
            "selectors": [{"kind": "entity", "name": "CutSketch", "type": "SKETCH"}],
            "parameters": {"depth_mm": 9, "feature_name": "ReviewedExtrudeCut"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "reviewed_profile_extrude_cut")
        self.assertEqual(model.Extension.calls[0][0], "SelectByID2")
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")
        self.assertEqual(result["operation_result"]["cut"]["method"], "FeatureCut3")
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedExtrudeCut")
        self.assertEqual(result["operation_result"]["cut"]["assigned_feature_name"], "ReviewedExtrudeCut")

    def test_executes_slot_cut_from_reviewed_plane(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "slot_cut",
            "selectors": [{"kind": "entity", "name": "Top Plane", "type": "PLANE"}],
            "parameters": {"length_mm": 40, "width_mm": 8, "depth_mm": 5, "center": {"x": 0, "y": 0, "z": 0}, "feature_name": "ReviewedSlot"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "slot_profile_cut")
        self.assertTrue(any(call[0] == "CreateStraightSlot" for call in model.SketchManager.calls))
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedSlot")
        self.assertEqual(result["operation_result"]["cut"]["assigned_feature_name"], "ReviewedSlot")

    def test_executes_pocket_cut_from_reviewed_plane(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "pocket_cut",
            "selectors": [{"kind": "entity", "name": "Top Plane", "type": "PLANE"}],
            "parameters": {"width_mm": 20, "height_mm": 10, "depth_mm": 4, "center": {"x": 0, "y": 0, "z": 0}, "feature_name": "ReviewedPocket"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "rectangular_pocket_cut")
        self.assertTrue(any(call[0] == "CreateCenterRectangle" for call in model.SketchManager.calls))
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureCut3")
        self.assertEqual(result["operation_result"]["feature_name"], "ReviewedPocket")
        self.assertEqual(result["operation_result"]["cut"]["assigned_feature_name"], "ReviewedPocket")

    def test_executes_extrude_boss_from_reviewed_sketch(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "extrude_boss",
            "selectors": [{"kind": "entity", "name": "BossSketch", "type": "SKETCH"}],
            "parameters": {"depth_mm": 25, "feature_name": "DriveGearBlank"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "reviewed_profile_extrude_boss")
        self.assertEqual(model.Extension.calls[0][0], "SelectByID2")
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureExtrusion3")
        self.assertEqual(result["operation_result"]["boss"]["method"], "FeatureExtrusion3")
        self.assertEqual(result["operation_result"]["feature_name"], "DriveGearBlank")
        self.assertEqual(result["operation_result"]["depth_m"], 0.025)

    def test_executes_revolve_boss_with_reviewed_axis(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "revolve_boss",
            "selectors": [
                {"kind": "entity", "name": "ToothProfile", "type": "SKETCH"},
                {"kind": "entity", "name": "Axis1", "type": "AXIS"},
            ],
            "parameters": {"angle_deg": 360, "feature_name": "GearHub"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "reviewed_profile_revolve_boss")
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureRevolve2")
        self.assertEqual(result["operation_result"]["revolve"]["method"], "FeatureRevolve2")
        self.assertEqual(result["operation_result"]["axis_selector"], "Axis1")
        self.assertAlmostEqual(result["operation_result"]["angle_rad"], 6.283185307179586)

    def test_executes_revolved_cut_with_reviewed_axis_and_cut_direction(self):
        model = FakeModel()
        plan = mod.validate_spec({
            "operation": "revolved_cut",
            "selectors": [
                {"kind": "entity", "name": "ReliefProfile", "type": "SKETCH"},
                {"kind": "entity", "name": "Axis1", "type": "AXIS"},
            ],
            "parameters": {"angle_deg": 180, "reverse_direction": True, "feature_name": "HalfRelief"},
        })

        result = mod.execute(model, plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["operation_role"], "reviewed_profile_revolved_cut")
        self.assertEqual(model.FeatureManager.calls[-1][0], "FeatureRevolveCut2")
        self.assertEqual(result["operation_result"]["revolve_cut"]["method"], "FeatureRevolveCut2")
        self.assertEqual(result["operation_result"]["axis_selector"], "Axis1")
        self.assertTrue(result["operation_result"]["reverse_direction"])


if __name__ == "__main__":
    unittest.main()
