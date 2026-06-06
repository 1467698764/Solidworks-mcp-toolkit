import json
import math
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


class FakeThrowingExtension(FakeExtension):
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
        raise TypeError("COM type mismatch")


class FakeSurface:
    def __init__(self, kind, params):
        self.kind = kind
        self.params = params

    def IsPlane(self):
        return self.kind == "plane"

    def PlaneParams(self):
        return self.params

    def IsCylinder(self):
        return self.kind == "cylinder"

    def CylinderParams(self):
        return self.params


class FakeFace:
    def __init__(self, surface, box, tracking_id=None):
        self.surface = surface
        self.box = box
        self.tracking_id = tracking_id
        self.select_calls = []

    def GetSurface(self):
        return self.surface

    def GetBox(self):
        return self.box

    def Select4(self, append, select_data):
        self.select_calls.append((append, select_data))
        return True

    def GetTrackingID(self):
        return self.tracking_id


class FakeCurve:
    def __init__(self, params):
        self.params = params

    def IsLine(self):
        return True

    def LineParams(self):
        return self.params


class FakeEdge:
    def __init__(self, curve, box):
        self.curve = curve
        self.box = box
        self.select_calls = []

    def GetCurve(self):
        return self.curve

    def GetBox(self):
        return self.box

    def Select4(self, append, select_data):
        self.select_calls.append((append, select_data))
        return True


class FakeVertex:
    def __init__(self, point):
        self.point = point
        self.select_calls = []

    def GetPoint(self):
        return self.point

    def Select4(self, append, select_data):
        self.select_calls.append((append, select_data))
        return True


class FakeBody:
    def __init__(self, faces, edges=None, vertices=None):
        self.faces = faces
        self.edges = edges or []
        self.vertices = vertices or []

    def GetFaces(self):
        return self.faces

    def GetEdges(self):
        return self.edges

    def GetVertices(self):
        return self.vertices


class FakeComponent:
    def __init__(self, name, faces, edges=None, vertices=None):
        self.Name2 = name
        self.faces = faces
        self.edges = edges or []
        self.vertices = vertices or []

    def GetBodies3(self, body_type, visible_only):
        return [FakeBody(self.faces, self.edges, self.vertices)]


class FakeSelectionManager:
    def __init__(self, assembly, extension):
        self.assembly = assembly
        self.extension = extension
        self.created_select_data = []

    def GetSelectedObjectCount2(self, mark):
        return len(self.extension.calls) + self.assembly._native_selected_count

    def CreateSelectData(self):
        data = {"mark": 0}
        self.created_select_data.append(data)
        return data


class FakeFeature:
    def __init__(self, name=""):
        self.Name = name
        self.select_calls = []
        self.suppression_calls = []
        self.suppressed = False

    def Select2(self, append, mark):
        self.select_calls.append((append, mark))
        return True

    def SetSuppression2(self, state, option=None, components=None):
        self.suppression_calls.append((state, option, components))
        self.suppressed = True
        return True


class FakeMateData:
    def __init__(self, mate_type):
        self.Type = mate_type
        self.EntitiesToMate = []
        self.WidthSelection = []
        self.TabSelection = []
        self.Constraint = None
        self.ConstraintType = None
        self.Distance = None
        self.Percent = None


class FakeAssembly:
    def __init__(self, components=None, features=None):
        self._native_selected_count = 0
        self.Extension = FakeExtension()
        self.SelectionManager = FakeSelectionManager(self, self.Extension)
        self.components = components or []
        self.features = {feature.Name: feature for feature in (features or [])}
        self.cleared = []
        self.mates = []
        self.mate_data = []
        self.rebuilds = []

    def ClearSelection2(self, value):
        self.cleared.append(value)
        self.Extension.calls.clear()
        self._native_selected_count = 0

    def AddMate5(self, *args):
        self.mates.append(args)
        return FakeFeature()

    def CreateMateData(self, mate_type):
        data = FakeMateData(mate_type)
        self.mate_data.append(data)
        return data

    def CreateMate(self, mate_data):
        self.mates.append(("CreateMate", mate_data))
        return FakeFeature()

    def ForceRebuild3(self, value):
        self.rebuilds.append(value)
        return True

    def GetComponents(self, top_level_only):
        return self.components

    def FeatureByName(self, name):
        return self.features.get(name)


class FakeSelectByIdTypeMismatchAssembly(FakeAssembly):
    def __init__(self, components=None, features=None):
        super().__init__(components, features)
        self.Extension = FakeThrowingExtension()
        self.SelectionManager = FakeSelectionManager(self, self.Extension)


class FakeFalseAddMateAssembly(FakeAssembly):
    def AddMate5(self, *args):
        self.mates.append(args)
        return False


class FakeFalseCreateMateAssembly(FakeAssembly):
    def CreateMate(self, mate_data):
        self.mates.append(("CreateMate", mate_data))
        return False


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

    def test_addmate_false_return_blocks_acceptance(self):
        asm = FakeFalseAddMateAssembly()

        result = mod.execute_manifest(self.manifest(), asm)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["counts"]["executed_mates"], 0)
        self.assertEqual(result["findings"]["blocking"][0]["kind"], "addmate_failed")
        self.assertEqual(result["executed_mates"][0]["ok"], False)
        self.assertEqual(result["executed_mates"][0]["api"], "AddMate5")

    def test_selects_native_component_faces_before_addmate5(self):
        bottom_face = FakeFace(
            FakeSurface("plane", [0.0, 0.0, 0.024, 0.0, 0.0, -1.0]),
            [0.0, 0.0, 0.023, 0.1, 0.1, 0.025],
        )
        top_face = FakeFace(
            FakeSurface("plane", [0.0, 0.0, 0.024, 0.0, 0.0, 1.0]),
            [0.0, 0.0, 0.023, 0.2, 0.1, 0.025],
        )
        asm = FakeAssembly([
            FakeComponent("bolt_m6-1", [bottom_face]),
            FakeComponent("cover_plate-1", [top_face]),
        ])

        result = mod.execute_manifest(self.manifest(), asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(bottom_face.select_calls, [(False, {"mark": 0})])
        self.assertEqual(top_face.select_calls, [(True, {"mark": 0})])
        self.assertEqual(asm.Extension.calls, [])
        guard = result["executed_mates"][0]["selection_guard"]
        self.assertEqual([call["method"] for call in guard["select_by_id_calls"]], ["Face.Select4", "Face.Select4"])

    def test_selectbyid_com_type_mismatch_is_reported_not_raised(self):
        asm = FakeSelectByIdTypeMismatchAssembly()

        result = mod.execute_manifest(self.manifest(), asm)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["counts"]["executed_mates"], 0)
        blocking = result["findings"]["blocking"][0]
        self.assertEqual("selection_failed", blocking["kind"])
        reports = blocking["detail"]["selection_reports"]
        self.assertEqual("SelectByID2", reports[0]["method"])
        self.assertIn("COM type mismatch", reports[0]["error"])
        self.assertEqual(asm.mates, [])

    def test_native_identity_tracking_id_takes_priority_over_bbox_fallback(self):
        manifest = self.manifest()
        manifest["macros"][0]["selection_selectors"][0]["native_identity"] = {"tracking_id": "face:bolt:bottom"}
        manifest["macros"][0]["selection_selectors"][1]["native_identity"] = {"tracking_id": "face:cover:top"}
        wrong_but_close = FakeFace(
            FakeSurface("plane", [0.0, 0.0, 0.024, 0.0, 0.0, -1.0]),
            [0.052, 0.052, 0.023, 0.056, 0.056, 0.025],
            tracking_id="face:bolt:wrong",
        )
        selected_bottom = FakeFace(
            FakeSurface("plane", [0.0, 0.0, 0.024, 0.0, 0.0, -1.0]),
            [0.0, 0.0, 0.023, 0.1, 0.1, 0.025],
            tracking_id="face:bolt:bottom",
        )
        selected_top = FakeFace(
            FakeSurface("plane", [0.0, 0.0, 0.024, 0.0, 0.0, 1.0]),
            [0.0, 0.0, 0.023, 0.2, 0.1, 0.025],
            tracking_id="face:cover:top",
        )
        asm = FakeAssembly([
            FakeComponent("bolt_m6-1", [wrong_but_close, selected_bottom]),
            FakeComponent("cover_plate-1", [selected_top]),
        ])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(wrong_but_close.select_calls, [])
        self.assertEqual(selected_bottom.select_calls, [(False, {"mark": 0})])
        self.assertEqual(selected_top.select_calls, [(True, {"mark": 0})])
        guard = result["executed_mates"][0]["selection_guard"]
        self.assertEqual([call["method"] for call in guard["select_by_id_calls"]], ["native_identity.Select4", "native_identity.Select4"])

    def test_selects_native_cylindrical_faces_for_concentric_mate(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "concentric"
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "shaft-1:cylinder:shaft_axis",
                "component": "shaft-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [0.0, 0.0, 1.0],
                    "origin_m": [0.0, 0.0, 0.0],
                    "radius_m": 0.01,
                },
            },
            {
                "stable_id": "plate-1:cylinder:hole_axis",
                "component": "plate-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [0.0, 0.0, 1.0],
                    "origin_m": [0.0, 0.0, 0.0],
                    "radius_m": 0.01,
                },
            },
        ]
        shaft_face = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.01]),
            [-0.01, -0.01, -0.05, 0.01, 0.01, 0.05],
        )
        hole_face = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.01]),
            [-0.01, -0.01, -0.01, 0.01, 0.01, 0.01],
        )
        asm = FakeAssembly([FakeComponent("shaft-1", [shaft_face]), FakeComponent("plate-1", [hole_face])])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["concentric"])
        self.assertEqual(shaft_face.select_calls, [(False, {"mark": 0})])
        self.assertEqual(hole_face.select_calls, [(True, {"mark": 0})])

    def test_selects_native_slot_centerline_edges_before_addmate5(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "parallel"
        manifest["macros"][0]["expected_mate_name"] = "MG_slot_guides_01_parallel"
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "slot_carrier-1:slot:centerline",
                "component": "slot_carrier-1",
                "fallback": {
                    "type": "slot_centerline",
                    "axis": [1.0, 0.0, 0.0],
                    "centerline_m": {"start": [-0.03, 0.0, 0.0], "end": [0.03, 0.0, 0.0]},
                },
            },
            {
                "stable_id": "rail-1:slot:centerline",
                "component": "rail-1",
                "fallback": {
                    "type": "slot_centerline",
                    "axis": [1.0, 0.0, 0.0],
                    "centerline_m": {"start": [-0.03, 0.02, 0.0], "end": [0.03, 0.02, 0.0]},
                },
            },
        ]
        slot_edge = FakeEdge(FakeCurve([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]), [-0.03, -0.001, -0.001, 0.03, 0.001, 0.001])
        rail_edge = FakeEdge(FakeCurve([0.0, 0.02, 0.0, 1.0, 0.0, 0.0]), [-0.03, 0.019, -0.001, 0.03, 0.021, 0.001])
        asm = FakeAssembly([
            FakeComponent("slot_carrier-1", [], [slot_edge]),
            FakeComponent("rail-1", [], [rail_edge]),
        ])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["parallel"])
        self.assertEqual(slot_edge.select_calls, [(False, {"mark": 0})])
        self.assertEqual(rail_edge.select_calls, [(True, {"mark": 0})])
        guard = result["executed_mates"][0]["selection_guard"]
        self.assertEqual([call["method"] for call in guard["select_by_id_calls"]], ["Edge.Select4", "Edge.Select4"])
        self.assertEqual(asm.Extension.calls, [])

    def test_executes_slot_mate_with_native_slot_centerline_edges(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "slot"
        manifest["macros"][0]["expected_mate_name"] = "MG_slot_slider_01_slot"
        manifest["macros"][0]["slot_constraint_type"] = 1
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "slot_carrier-1:slot:centerline",
                "component": "slot_carrier-1",
                "fallback": {
                    "type": "slot_centerline",
                    "axis": [1.0, 0.0, 0.0],
                    "centerline_m": {"start": [-0.03, 0.0, 0.0], "end": [0.03, 0.0, 0.0]},
                },
            },
            {
                "stable_id": "slider_pin-1:cylinder:pin_axis",
                "component": "slider_pin-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [1.0, 0.0, 0.0],
                    "origin_m": [0.0, 0.0, 0.0],
                    "radius_m": 0.006,
                },
            },
        ]
        slot_edge = FakeEdge(FakeCurve([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]), [-0.03, -0.001, -0.001, 0.03, 0.001, 0.001])
        pin_face = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.006]),
            [-0.006, -0.006, -0.006, 0.006, 0.006, 0.006],
        )
        asm = FakeAssembly([
            FakeComponent("slot_carrier-1", [], [slot_edge]),
            FakeComponent("slider_pin-1", [pin_face]),
        ])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["executed_mates"][0]["api"], "CreateMateData/CreateMate")
        self.assertEqual(result["executed_mates"][0]["mate_type"], "slot")
        self.assertEqual(result["executed_mates"][0]["constraint_role"], "slot_guided_motion")
        self.assertEqual(result["executed_mates"][0]["slot_constraint_type"], 1)
        self.assertEqual(asm.mate_data[0].Type, mod.MATE_TYPES["slot"])
        self.assertEqual(asm.mate_data[0].EntitiesToMate, [slot_edge, pin_face])
        self.assertEqual(asm.mate_data[0].Constraint, 1)
        self.assertEqual(slot_edge.select_calls, [(False, {"mark": 0})])
        self.assertEqual(pin_face.select_calls, [(True, {"mark": 0})])
        guard = result["executed_mates"][0]["selection_guard"]
        self.assertEqual([call["method"] for call in guard["select_by_id_calls"]], ["Edge.Select4", "Face.Select4"])
        self.assertNotIn("entity", guard["selection_reports"][0])

    def test_executes_slot_distance_and_percent_constraints(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "slot"
        manifest["macros"][0]["slot_constraint_type"] = 2
        manifest["macros"][0]["slot_distance_m"] = 0.018
        edge_one = FakeEdge(FakeCurve([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]), [-0.03, -0.001, -0.001, 0.03, 0.001, 0.001])
        edge_two = FakeEdge(FakeCurve([0.0, 0.02, 0.0, 1.0, 0.0, 0.0]), [-0.03, 0.019, -0.001, 0.03, 0.021, 0.001])
        manifest["macros"][0]["selection_selectors"] = [
            {"stable_id": "slot-1:centerline", "component": "slot-1", "fallback": {"type": "slot_centerline", "axis": [1, 0, 0], "origin_m": [0, 0, 0]}},
            {"stable_id": "pin-1:centerline", "component": "pin-1", "fallback": {"type": "slot_centerline", "axis": [1, 0, 0], "origin_m": [0, 0.02, 0]}},
        ]
        distance_asm = FakeAssembly([FakeComponent("slot-1", [], [edge_one]), FakeComponent("pin-1", [], [edge_two])])

        distance_result = mod.execute_manifest(manifest, distance_asm)

        self.assertTrue(distance_result["ok"], distance_result)
        self.assertEqual(distance_asm.mate_data[0].Constraint, 2)
        self.assertEqual(distance_asm.mate_data[0].Distance, 0.018)
        self.assertEqual(distance_result["executed_mates"][0]["slot_distance_m"], 0.018)
        self.assertEqual(distance_result["executed_mates"][0]["constraint_role"], "slot_guided_motion")

        percent_manifest = self.manifest()
        percent_manifest["macros"][0]["mate_type"] = "slot"
        percent_manifest["macros"][0]["slot_constraint_type"] = 3
        percent_manifest["macros"][0]["slot_percent"] = 42.5
        percent_manifest["macros"][0]["selection_selectors"] = manifest["macros"][0]["selection_selectors"]
        percent_asm = FakeAssembly([FakeComponent("slot-1", [], [edge_one]), FakeComponent("pin-1", [], [edge_two])])

        percent_result = mod.execute_manifest(percent_manifest, percent_asm)

        self.assertTrue(percent_result["ok"], percent_result)
        self.assertEqual(percent_asm.mate_data[0].Constraint, 3)
        self.assertEqual(percent_asm.mate_data[0].Percent, 42.5)
        self.assertEqual(percent_result["executed_mates"][0]["slot_percent"], 42.5)
        self.assertEqual(percent_result["executed_mates"][0]["constraint_role"], "slot_guided_motion")

    def test_executes_path_mate_with_native_vertex_and_path_edge(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "path"
        manifest["macros"][0]["expected_mate_name"] = "MG_follower_slot_01_path"
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "follower-1:vertex:path_point",
                "component": "follower-1",
                "fallback": {
                    "type": "bbox_vertex",
                    "origin_m": [0.0, 0.0, 0.0],
                },
            },
            {
                "stable_id": "guide-1:slot:centerline",
                "component": "guide-1",
                "fallback": {
                    "type": "slot_centerline",
                    "axis": [1.0, 0.0, 0.0],
                    "centerline_m": {"start": [-0.03, 0.0, 0.0], "end": [0.03, 0.0, 0.0]},
                },
            },
        ]
        path_vertex = FakeVertex([0.0, 0.0, 0.0])
        path_edge = FakeEdge(FakeCurve([0.0, 0.0, 0.0, 1.0, 0.0, 0.0]), [-0.03, -0.001, -0.001, 0.03, 0.001, 0.001])
        asm = FakeAssembly([
            FakeComponent("follower-1", [], vertices=[path_vertex]),
            FakeComponent("guide-1", [], [path_edge]),
        ])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["path"])
        self.assertEqual(result["executed_mates"][0]["mate_type"], "path")
        self.assertEqual(result["executed_mates"][0]["constraint_role"], "path_following_motion")
        self.assertEqual(path_vertex.select_calls, [(False, {"mark": 0})])
        self.assertEqual(path_edge.select_calls, [(True, {"mark": 0})])
        guard = result["executed_mates"][0]["selection_guard"]
        self.assertEqual([call["method"] for call in guard["select_by_id_calls"]], ["Vertex.Select4", "Edge.Select4"])

    def test_executes_tangent_mate_with_native_cylinder_and_plane_faces(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "tangent"
        manifest["macros"][0]["expected_mate_name"] = "MG_cam_roller_01_tangent"
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "roller-1:cylinder:outer",
                "component": "roller-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [0.0, 0.0, 1.0],
                    "origin_m": [0.0, 0.0, 0.0],
                    "radius_m": 0.015,
                },
            },
            {
                "stable_id": "cam_plate-1:plane:x_max",
                "component": "cam_plate-1",
                "fallback": {
                    "type": "bbox_planar_face",
                    "normal": [1.0, 0.0, 0.0],
                    "origin_m": [0.015, 0.0, 0.0],
                },
            },
        ]
        roller_face = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.015]),
            [-0.015, -0.015, -0.02, 0.015, 0.015, 0.02],
        )
        cam_face = FakeFace(
            FakeSurface("plane", [0.015, 0.0, 0.0, 1.0, 0.0, 0.0]),
            [0.014, -0.04, -0.02, 0.016, 0.04, 0.02],
        )
        asm = FakeAssembly([FakeComponent("roller-1", [roller_face]), FakeComponent("cam_plate-1", [cam_face])])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["tangent"])
        self.assertEqual(result["executed_mates"][0]["mate_type"], "tangent")
        self.assertEqual(result["executed_mates"][0]["constraint_role"], "surface_contact")
        self.assertEqual(roller_face.select_calls, [(False, {"mark": 0})])
        self.assertEqual(cam_face.select_calls, [(True, {"mark": 0})])

    def test_executes_bad_mate_suppression_actions_before_addmate5(self):
        manifest = self.manifest()
        manifest["execution_actions"] = [
            {
                "action": "suppress_mate",
                "target_mate": "Broken_Bolt_Mate",
                "reason": "remove stale mate before adding replacement",
            }
        ]
        bad_mate = FakeFeature("Broken_Bolt_Mate")
        asm = FakeAssembly(features=[bad_mate])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["counts"]["executed_actions"], 1)
        self.assertEqual(result["executed_actions"][0]["action"], "suppress_mate")
        self.assertEqual(result["executed_actions"][0]["target_mate"], "Broken_Bolt_Mate")
        self.assertEqual(bad_mate.select_calls, [(False, 0)])
        self.assertEqual(bad_mate.suppression_calls[0][0], 0)
        self.assertEqual(asm.rebuilds[0], False)

    def test_executes_distance_and_angle_parameters_from_manifest(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "distance"
        manifest["macros"][0]["distance_m"] = 0.0125
        asm = FakeAssembly()

        distance_result = mod.execute_manifest(manifest, asm)

        self.assertTrue(distance_result["ok"], distance_result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["distance"])
        self.assertEqual(asm.mates[0][3], 0.0125)
        self.assertEqual(distance_result["executed_mates"][0]["distance_m"], 0.0125)
        self.assertEqual(distance_result["executed_mates"][0]["constraint_role"], "offset_clearance")

        angle_manifest = self.manifest()
        angle_manifest["macros"][0]["mate_type"] = "angle"
        angle_manifest["macros"][0]["angle_deg"] = 30.0
        angle_manifest["macros"][0]["flip"] = True
        angle_asm = FakeAssembly()

        angle_result = mod.execute_manifest(angle_manifest, angle_asm)

        self.assertTrue(angle_result["ok"], angle_result)
        self.assertEqual(angle_asm.mates[0][0], mod.MATE_TYPES["angle"])
        self.assertTrue(angle_asm.mates[0][2])
        self.assertEqual(angle_asm.mates[0][6], 0)
        self.assertEqual(angle_asm.mates[0][7], 0)
        self.assertAlmostEqual(angle_asm.mates[0][8], math.radians(30.0))
        self.assertAlmostEqual(angle_result["executed_mates"][0]["angle_rad"], math.radians(30.0))
        self.assertEqual(angle_result["executed_mates"][0]["constraint_role"], "design_angle")

    def test_executes_parallel_and_perpendicular_as_supporting_orientation_mates(self):
        parallel_manifest = self.manifest()
        parallel_manifest["macros"][0]["mate_type"] = "parallel"
        parallel_manifest["macros"][0]["expected_mate_name"] = "MG_cover_orientation_parallel"
        parallel_asm = FakeAssembly()

        parallel_result = mod.execute_manifest(parallel_manifest, parallel_asm)

        self.assertTrue(parallel_result["ok"], parallel_result)
        self.assertEqual(parallel_asm.mates[0][0], mod.MATE_TYPES["parallel"])
        parallel_mate = parallel_result["executed_mates"][0]
        self.assertTrue(parallel_mate["orientation_constraint"])
        self.assertEqual(parallel_mate["constraint_role"], "supporting_orientation")

        perpendicular_manifest = self.manifest()
        perpendicular_manifest["macros"][0]["mate_type"] = "perpendicular"
        perpendicular_manifest["macros"][0]["expected_mate_name"] = "MG_cover_orientation_perpendicular"
        perpendicular_asm = FakeAssembly()

        perpendicular_result = mod.execute_manifest(perpendicular_manifest, perpendicular_asm)

        self.assertTrue(perpendicular_result["ok"], perpendicular_result)
        self.assertEqual(perpendicular_asm.mates[0][0], mod.MATE_TYPES["perpendicular"])
        perpendicular_mate = perpendicular_result["executed_mates"][0]
        self.assertTrue(perpendicular_mate["orientation_constraint"])
        self.assertEqual(perpendicular_mate["constraint_role"], "supporting_orientation")

    def test_executes_limit_distance_and_angle_bounds_in_addmate5_parameter_slots(self):
        distance_manifest = self.manifest()
        distance_manifest["macros"][0]["mate_type"] = "limit_distance"
        distance_manifest["macros"][0]["distance_m"] = 0.02
        distance_manifest["macros"][0]["distance_min_m"] = 0.01
        distance_manifest["macros"][0]["distance_max_m"] = 0.03
        distance_asm = FakeAssembly()

        distance_result = mod.execute_manifest(distance_manifest, distance_asm)

        self.assertTrue(distance_result["ok"], distance_result)
        self.assertEqual(distance_asm.mates[0][0], mod.MATE_TYPES["limit_distance"])
        self.assertEqual(distance_asm.mates[0][3], 0.02)
        self.assertEqual(distance_asm.mates[0][4], 0.03)
        self.assertEqual(distance_asm.mates[0][5], 0.01)
        self.assertEqual(distance_result["executed_mates"][0]["distance_max_m"], 0.03)
        self.assertEqual(distance_result["executed_mates"][0]["distance_min_m"], 0.01)
        self.assertEqual(distance_result["executed_mates"][0]["constraint_role"], "bounded_linear_motion")

        angle_manifest = self.manifest()
        angle_manifest["macros"][0]["mate_type"] = "limit_angle"
        angle_manifest["macros"][0]["angle_deg"] = 45.0
        angle_manifest["macros"][0]["angle_min_deg"] = 15.0
        angle_manifest["macros"][0]["angle_max_deg"] = 75.0
        angle_asm = FakeAssembly()

        angle_result = mod.execute_manifest(angle_manifest, angle_asm)

        self.assertTrue(angle_result["ok"], angle_result)
        self.assertEqual(angle_asm.mates[0][0], mod.MATE_TYPES["limit_angle"])
        self.assertEqual(angle_asm.mates[0][6], 0)
        self.assertEqual(angle_asm.mates[0][7], 0)
        self.assertAlmostEqual(angle_asm.mates[0][8], math.radians(45.0))
        self.assertAlmostEqual(angle_asm.mates[0][9], math.radians(75.0))
        self.assertAlmostEqual(angle_asm.mates[0][10], math.radians(15.0))
        self.assertAlmostEqual(angle_result["executed_mates"][0]["angle_max_rad"], math.radians(75.0))
        self.assertAlmostEqual(angle_result["executed_mates"][0]["angle_min_rad"], math.radians(15.0))
        self.assertEqual(angle_result["executed_mates"][0]["constraint_role"], "bounded_angular_motion")

    def test_executes_width_mate_with_four_native_planar_faces(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "width"
        manifest["macros"][0]["expected_mate_name"] = "MG_slider_guide_01_width"
        manifest["macros"][0]["width_constraint_type"] = 0
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "guide_left-1:plane:y_min",
                "component": "guide_left-1",
                "width_role": "width_face",
                "fallback": {"type": "bbox_planar_face", "normal": [0.0, -1.0, 0.0], "origin_m": [0.0, -0.02, 0.0]},
            },
            {
                "stable_id": "guide_right-1:plane:y_max",
                "component": "guide_right-1",
                "width_role": "width_face",
                "fallback": {"type": "bbox_planar_face", "normal": [0.0, 1.0, 0.0], "origin_m": [0.0, 0.02, 0.0]},
            },
            {
                "stable_id": "slider-1:plane:y_min",
                "component": "slider-1",
                "width_role": "tab_face",
                "fallback": {"type": "bbox_planar_face", "normal": [0.0, -1.0, 0.0], "origin_m": [0.0, -0.01, 0.0]},
            },
            {
                "stable_id": "slider-1:plane:y_max",
                "component": "slider-1",
                "width_role": "tab_face",
                "fallback": {"type": "bbox_planar_face", "normal": [0.0, 1.0, 0.0], "origin_m": [0.0, 0.01, 0.0]},
            },
        ]
        guide_left_face = FakeFace(FakeSurface("plane", [0.0, -0.02, 0.0, 0.0, -1.0, 0.0]), [-0.02, -0.021, -0.01, 0.02, -0.019, 0.01])
        guide_right_face = FakeFace(FakeSurface("plane", [0.0, 0.02, 0.0, 0.0, 1.0, 0.0]), [-0.02, 0.019, -0.01, 0.02, 0.021, 0.01])
        slider_left_face = FakeFace(FakeSurface("plane", [0.0, -0.01, 0.0, 0.0, -1.0, 0.0]), [-0.015, -0.011, -0.01, 0.015, -0.009, 0.01])
        slider_right_face = FakeFace(FakeSurface("plane", [0.0, 0.01, 0.0, 0.0, 1.0, 0.0]), [-0.015, 0.009, -0.01, 0.015, 0.011, 0.01])
        asm = FakeAssembly([
            FakeComponent("guide_left-1", [guide_left_face]),
            FakeComponent("guide_right-1", [guide_right_face]),
            FakeComponent("slider-1", [slider_left_face, slider_right_face]),
        ])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["executed_mates"][0]["api"], "CreateMateData/CreateMate")
        self.assertEqual(result["executed_mates"][0]["mate_type"], "width")
        self.assertEqual(result["executed_mates"][0]["constraint_role"], "centered_linear_guidance")
        self.assertEqual(result["executed_mates"][0]["width_selection_count"], 2)
        self.assertEqual(result["executed_mates"][0]["tab_selection_count"], 2)
        self.assertEqual(asm.mate_data[0].Type, mod.MATE_TYPES["width"])
        self.assertEqual(asm.mate_data[0].WidthSelection, [guide_left_face, guide_right_face])
        self.assertEqual(asm.mate_data[0].TabSelection, [slider_left_face, slider_right_face])
        self.assertNotIn("entity", result["executed_mates"][0]["selection_guard"]["selection_reports"][0])

    def test_create_mate_false_return_blocks_width_acceptance(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "width"
        manifest["macros"][0]["expected_mate_name"] = "MG_slider_guide_01_width"
        manifest["macros"][0]["selection_selectors"] = [
            {"stable_id": "guide_left-1:plane:y_min", "component": "guide_left-1", "fallback": {"type": "bbox_planar_face", "normal": [0.0, -1.0, 0.0], "origin_m": [0.0, -0.02, 0.0]}},
            {"stable_id": "guide_right-1:plane:y_max", "component": "guide_right-1", "fallback": {"type": "bbox_planar_face", "normal": [0.0, 1.0, 0.0], "origin_m": [0.0, 0.02, 0.0]}},
            {"stable_id": "slider-1:plane:y_min", "component": "slider-1", "fallback": {"type": "bbox_planar_face", "normal": [0.0, -1.0, 0.0], "origin_m": [0.0, -0.01, 0.0]}},
            {"stable_id": "slider-1:plane:y_max", "component": "slider-1", "fallback": {"type": "bbox_planar_face", "normal": [0.0, 1.0, 0.0], "origin_m": [0.0, 0.01, 0.0]}},
        ]
        guide_left_face = FakeFace(FakeSurface("plane", [0.0, -0.02, 0.0, 0.0, -1.0, 0.0]), [-0.02, -0.021, -0.01, 0.02, -0.019, 0.01])
        guide_right_face = FakeFace(FakeSurface("plane", [0.0, 0.02, 0.0, 0.0, 1.0, 0.0]), [-0.02, 0.019, -0.01, 0.02, 0.021, 0.01])
        slider_left_face = FakeFace(FakeSurface("plane", [0.0, -0.01, 0.0, 0.0, -1.0, 0.0]), [-0.015, -0.011, -0.01, 0.015, -0.009, 0.01])
        slider_right_face = FakeFace(FakeSurface("plane", [0.0, 0.01, 0.0, 0.0, 1.0, 0.0]), [-0.015, 0.009, -0.01, 0.015, 0.011, 0.01])
        asm = FakeFalseCreateMateAssembly([
            FakeComponent("guide_left-1", [guide_left_face]),
            FakeComponent("guide_right-1", [guide_right_face]),
            FakeComponent("slider-1", [slider_left_face, slider_right_face]),
        ])

        result = mod.execute_manifest(manifest, asm)

        self.assertFalse(result["ok"], result)
        self.assertEqual(result["counts"]["executed_mates"], 0)
        self.assertEqual(result["findings"]["blocking"][0]["kind"], "addmate_failed")
        self.assertEqual(result["executed_mates"][0]["ok"], False)
        self.assertEqual(result["executed_mates"][0]["api"], "CreateMateData/CreateMate")

    def test_executes_symmetry_mate_with_two_faces_and_reference_plane(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "symmetry"
        manifest["macros"][0]["expected_mate_name"] = "MG_left_right_01_symmetry"
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "left_tab-1:plane:y_max",
                "component": "left_tab-1",
                "fallback": {"type": "bbox_planar_face", "normal": [0.0, 1.0, 0.0], "origin_m": [0.0, -0.02, 0.0]},
            },
            {
                "stable_id": "right_tab-1:plane:y_min",
                "component": "right_tab-1",
                "fallback": {"type": "bbox_planar_face", "normal": [0.0, -1.0, 0.0], "origin_m": [0.0, 0.02, 0.0]},
            },
            {
                "stable_id": "frame-1:plane:center",
                "component": "frame-1",
                "fallback": {"type": "bbox_planar_face", "normal": [0.0, 1.0, 0.0], "origin_m": [0.0, 0.0, 0.0]},
            },
        ]
        left_face = FakeFace(FakeSurface("plane", [0.0, -0.02, 0.0, 0.0, 1.0, 0.0]), [-0.02, -0.021, -0.01, 0.02, -0.019, 0.01])
        right_face = FakeFace(FakeSurface("plane", [0.0, 0.02, 0.0, 0.0, -1.0, 0.0]), [-0.02, 0.019, -0.01, 0.02, 0.021, 0.01])
        center_plane = FakeFace(FakeSurface("plane", [0.0, 0.0, 0.0, 0.0, 1.0, 0.0]), [-0.05, -0.001, -0.05, 0.05, 0.001, 0.05])
        asm = FakeAssembly([
            FakeComponent("left_tab-1", [left_face]),
            FakeComponent("right_tab-1", [right_face]),
            FakeComponent("frame-1", [center_plane]),
        ])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["symmetry"])
        self.assertEqual(result["executed_mates"][0]["mate_type"], "symmetry")
        self.assertEqual(result["executed_mates"][0]["constraint_role"], "symmetric_alignment")
        self.assertEqual(result["executed_mates"][0]["selected_entities"], 3)
        self.assertEqual(left_face.select_calls, [(False, {"mark": 0})])
        self.assertEqual(right_face.select_calls, [(True, {"mark": 0})])
        self.assertEqual(center_plane.select_calls, [(True, {"mark": 0})])

    def test_executes_gear_mate_with_native_cylindrical_faces_and_ratio(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "gear"
        manifest["macros"][0]["expected_mate_name"] = "MG_pinion_spur_01_gear"
        manifest["macros"][0]["gear_ratio_numerator"] = 18
        manifest["macros"][0]["gear_ratio_denominator"] = 54
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "pinion-1:cylinder:pitch_axis",
                "component": "pinion-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [0.0, 0.0, 1.0],
                    "origin_m": [0.0, 0.0, 0.0],
                    "radius_m": 0.018,
                },
            },
            {
                "stable_id": "spur_gear-1:cylinder:pitch_axis",
                "component": "spur_gear-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [0.0, 0.0, 1.0],
                    "origin_m": [0.07, 0.0, 0.0],
                    "radius_m": 0.054,
                },
            },
        ]
        pinion_face = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.018]),
            [-0.018, -0.018, -0.01, 0.018, 0.018, 0.01],
        )
        gear_face = FakeFace(
            FakeSurface("cylinder", [0.07, 0.0, 0.0, 0.0, 0.0, 1.0, 0.054]),
            [0.016, -0.054, -0.01, 0.124, 0.054, 0.01],
        )
        asm = FakeAssembly([FakeComponent("pinion-1", [pinion_face]), FakeComponent("spur_gear-1", [gear_face])])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["gear"])
        self.assertEqual(asm.mates[0][6], 18.0)
        self.assertEqual(asm.mates[0][7], 54.0)
        self.assertEqual(result["executed_mates"][0]["mate_type"], "gear")
        self.assertEqual(result["executed_mates"][0]["constraint_role"], "rotary_ratio_coupling")
        self.assertEqual(result["executed_mates"][0]["gear_ratio_numerator"], 18.0)
        self.assertEqual(result["executed_mates"][0]["gear_ratio_denominator"], 54.0)
        self.assertEqual(pinion_face.select_calls, [(False, {"mark": 0})])
        self.assertEqual(gear_face.select_calls, [(True, {"mark": 0})])

    def test_executes_cam_follower_mate_with_native_faces(self):
        manifest = self.manifest()
        manifest["macros"][0]["mate_type"] = "cam"
        manifest["macros"][0]["expected_mate_name"] = "MG_cam_follower_01_cam"
        manifest["macros"][0]["selection_selectors"] = [
            {
                "stable_id": "cam_plate-1:cylinder:cam_surface",
                "component": "cam_plate-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [0.0, 0.0, 1.0],
                    "origin_m": [0.0, 0.0, 0.0],
                    "radius_m": 0.03,
                },
            },
            {
                "stable_id": "follower-1:cylinder:roller",
                "component": "follower-1",
                "fallback": {
                    "type": "cylindrical_axis",
                    "axis": [0.0, 0.0, 1.0],
                    "origin_m": [0.05, 0.0, 0.0],
                    "radius_m": 0.012,
                },
            },
        ]
        cam_face = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.03]),
            [-0.03, -0.03, -0.01, 0.03, 0.03, 0.01],
        )
        follower_face = FakeFace(
            FakeSurface("cylinder", [0.05, 0.0, 0.0, 0.0, 0.0, 1.0, 0.012]),
            [0.038, -0.012, -0.01, 0.062, 0.012, 0.01],
        )
        asm = FakeAssembly([FakeComponent("cam_plate-1", [cam_face]), FakeComponent("follower-1", [follower_face])])

        result = mod.execute_manifest(manifest, asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(asm.mates[0][0], mod.MATE_TYPES["cam"])
        self.assertEqual(result["executed_mates"][0]["mate_type"], "cam")
        self.assertEqual(result["executed_mates"][0]["constraint_role"], "cam_follower_contact")
        self.assertEqual(cam_face.select_calls, [(False, {"mark": 0})])
        self.assertEqual(follower_face.select_calls, [(True, {"mark": 0})])

    def test_dry_run_reports_repair_actions_without_solidworks(self):
        manifest = self.manifest()
        manifest["execution_actions"] = [{"action": "suppress_mate", "target_mate": "Broken_Bolt_Mate"}]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest_path = root / "manifest.json"
            out = root / "execute.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest_path), "--out", str(out), "--dry-run")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["counts"]["planned_actions"], 1)
            self.assertEqual(data["planned_actions"][0]["target_mate"], "Broken_Bolt_Mate")

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
            self.assertEqual(data["planned_mates"][0]["distance_m"], 0.0)
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
