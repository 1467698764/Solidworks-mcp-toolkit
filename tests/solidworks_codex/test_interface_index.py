import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_interface_index.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class InterfaceIndexTests(unittest.TestCase):
    def test_indexes_bbox_contacts_standard_candidates_and_interface_roles(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "interface_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "path": "C:/m/cover_plate.SLDPRT", "fixed": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                    {"name2": "bolt_m6-1", "path": "C:/m/bolt_m6.SLDPRT", "fixed": False, "bbox_m": [0.05, 0.05, 0.024, 0.058, 0.058, 0.065]},
                    {"name2": "remote_handle-1", "path": "C:/m/remote_handle.SLDPRT", "fixed": False, "bbox_m": [1.0, 1.0, 1.0, 1.10, 1.10, 1.10]},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out), "--near-tolerance-m", "0.003", "--standard-part-regex", "bolt|washer|nut|screw")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["document"]["title"], "interface_fixture.SLDASM")
            by_name = {item["component"]: item for item in data["components"]}
            self.assertEqual(by_name["base_plate-1"]["role_hints"], ["fixed_root"])
            self.assertIn("standard_part", by_name["bolt_m6-1"]["role_hints"])
            contact = {(item["a"], item["b"]): item for item in data["interfaces"]}
            self.assertIn(("base_plate-1", "cover_plate-1"), contact)
            self.assertEqual(contact[("base_plate-1", "cover_plate-1")]["relation"], "touching_or_overlapping_bbox")
            self.assertEqual(by_name["bolt_m6-1"]["nearest_component"], "cover_plate-1")
            self.assertGreater(by_name["remote_handle-1"]["nearest_gap_m"], 1.0)
            self.assertIn("heuristic_bbox_only", data["operator_notes"])

    def test_indexes_named_planar_interfaces_with_local_frames(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "planar_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "path": "C:/m/cover_plate.SLDPRT", "fixed": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out), "--near-tolerance-m", "0.001")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            planes = {item["interface_id"]: item for item in data["planar_interfaces"]}
            self.assertIn("base_plate-1:plane:z_max", planes)
            self.assertIn("cover_plate-1:plane:z_min", planes)
            base_top = planes["base_plate-1:plane:z_max"]
            self.assertEqual(base_top["component"], "base_plate-1")
            self.assertEqual(base_top["role"], "contact_face")
            self.assertEqual(base_top["normal"], [0.0, 0.0, 1.0])
            self.assertEqual(base_top["local_frame"]["origin_m"], [0.1, 0.05, 0.012])
            self.assertEqual(base_top["source"], "axis_aligned_bbox_face")
            contact = data["interfaces"][0]
            self.assertEqual(contact["planar_interface_ids"]["a"], "base_plate-1:plane:z_max")
            self.assertEqual(contact["planar_interface_ids"]["b"], "cover_plate-1:plane:z_min")

    def test_indexes_component_coordinate_systems_from_bbox_evidence(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "coordinate_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "slide-1", "path": "C:/m/slide.SLDPRT", "fixed": False, "bbox_m": [0.05, 0.02, 0.012, 0.15, 0.08, 0.04]},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            systems = {item["component"]: item for item in data["coordinate_systems"]}
            base = systems["base_plate-1"]
            self.assertEqual(base["coordinate_system_id"], "base_plate-1:csys:bbox_center")
            self.assertEqual(base["origin_role"], "fixed_root_reference")
            self.assertEqual(base["origin_m"], [0.1, 0.05, 0.006])
            self.assertEqual(base["axes"]["x"], [1.0, 0.0, 0.0])
            self.assertEqual(base["source"], "axis_aligned_bbox")
            self.assertEqual(systems["slide-1"]["origin_role"], "component_bbox_center")

    def test_persists_interface_fallback_selectors_for_reopen_repair(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "persistent_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "path": "C:/m/cover_plate.SLDPRT", "fixed": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out), "--near-tolerance-m", "0.001")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            planes = {item["interface_id"]: item for item in data["planar_interfaces"]}
            selector = planes["base_plate-1:plane:z_max"]["selector"]
            self.assertEqual(selector["stable_id"], "base_plate-1:plane:z_max")
            self.assertEqual(selector["component"], "base_plate-1")
            self.assertEqual(selector["component_path"], "C:/m/base_plate.SLDPRT")
            self.assertEqual(selector["fallback"]["type"], "bbox_planar_face")
            self.assertEqual(selector["fallback"]["face"], "z_max")
            self.assertEqual(selector["fallback"]["origin_m"], [0.1, 0.05, 0.012])
            self.assertEqual(selector["strategy"], "native_identity_then_stable_id_then_bbox_fallback")
            self.assertEqual(selector["native_identity"]["stable_id"], "base_plate-1:plane:z_max")
            self.assertEqual(selector["native_identity"]["component_path"], "C:/m/base_plate.SLDPRT")
            self.assertEqual(selector["native_identity"]["kind"], "face")
            self.assertEqual(selector["native_identity"]["geometry_signature"]["type"], "bbox_planar_face")
            self.assertIn("tracking_id", selector["native_identity"]["resolution_order"])
            self.assertIn("native_identity_envelope", selector["tags"])
            self.assertIn("reopen_repair_selector", selector["tags"])

            systems = {item["component"]: item for item in data["coordinate_systems"]}
            csys_selector = systems["base_plate-1"]["selector"]
            self.assertEqual(csys_selector["stable_id"], "base_plate-1:csys:bbox_center")
            self.assertEqual(csys_selector["fallback"]["type"], "bbox_center_coordinate_system")
            self.assertEqual(csys_selector["native_identity"]["kind"], "coordinate_system")
            self.assertEqual(data["interfaces"][0]["selector_refs"]["a"], "base_plate-1:plane:z_max")
            self.assertEqual(data["interfaces"][0]["selector_refs"]["b"], "cover_plate-1:plane:z_min")

    def test_selectors_publish_live_identity_capture_protocols(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "identity_protocol_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "bearing_block-1", "path": "C:/m/bearing_block.SLDPRT", "bbox_m": [-0.04, -0.03, -0.02, 0.04, 0.03, 0.02]},
                    {"name2": "guide_plate-1", "path": "C:/m/guide_plate.SLDPRT", "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.06, 0.012]},
                ],
                "features": [
                    {"name": "BearingBore_D24_Z", "type": "HoleWizard", "components": ["bearing_block-1"]},
                    {"name": "SliderSlot_L120_W12_X", "type": "SlotCut", "components": ["guide_plate-1"]},
                ],
                "dimensions": [
                    {"full_name": "DIA24@BearingBore_D24_Z@bearing_block.SLDPRT", "system_value_m": 0.024, "feature": "BearingBore_D24_Z"},
                    {"full_name": "SlotWidth@SliderSlot_L120_W12_X@guide_plate.SLDPRT", "system_value_m": 0.012, "feature": "SliderSlot_L120_W12_X"},
                    {"full_name": "SlotLength@SliderSlot_L120_W12_X@guide_plate.SLDPRT", "system_value_m": 0.120, "feature": "SliderSlot_L120_W12_X"},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            selector_by_id = {
                data["planar_interfaces"][0]["selector"]["stable_id"]: data["planar_interfaces"][0]["selector"],
                data["cylindrical_interfaces"][0]["selector"]["stable_id"]: data["cylindrical_interfaces"][0]["selector"],
                data["slot_path_interfaces"][0]["selector"]["stable_id"]: data["slot_path_interfaces"][0]["selector"],
                data["coordinate_systems"][0]["selector"]["stable_id"]: data["coordinate_systems"][0]["selector"],
            }
            for selector in selector_by_id.values():
                protocol = selector["live_identity_capture_protocol"]
                self.assertEqual(protocol["target_stable_id"], selector["stable_id"])
                self.assertEqual(protocol["component"], selector["component"])
                self.assertEqual(protocol["patch_target"], "selector.native_identity")
                self.assertIn("persistent_reference", protocol["capture_fields"])
                self.assertIn("tracking_id", protocol["capture_fields"])
                self.assertIn("select_name", protocol["capture_fields"])
                self.assertIn("geometry_signature", protocol["readback_checks"])
                self.assertIn("capture_protocol", selector["tags"])

            self.assertEqual(selector_by_id["base_plate-1:plane:x_max"]["live_identity_capture_protocol"]["selection_entity"], "face")
            self.assertIn("IEntity::GetSafeEntity", selector_by_id["bearing_block-1:cylinder:BearingBore_D24_Z"]["live_identity_capture_protocol"]["solidworks_calls"])
            self.assertEqual(selector_by_id["guide_plate-1:slot:SliderSlot_L120_W12_X"]["live_identity_capture_protocol"]["selection_entity"], "edge_or_curve")
            self.assertEqual(selector_by_id["base_plate-1:csys:bbox_center"]["live_identity_capture_protocol"]["selection_entity"], "coordinate_system")
            self.assertIn("selectors_publish_live_identity_capture_protocols", data["operator_notes"])

    def test_scores_interface_confidence_and_blocks_weak_bbox_only_targets(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "confidence_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/m/base_plate.SLDPRT", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "path": "C:/m/cover_plate.SLDPRT", "fixed": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                    {"name2": "remote_bracket-1", "path": "C:/m/remote_bracket.SLDPRT", "fixed": False, "bbox_m": [0.50, 0.50, 0.0, 0.60, 0.60, 0.10]},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out), "--near-tolerance-m", "0.001")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            planes = {item["interface_id"]: item for item in data["planar_interfaces"]}
            contact_face = planes["base_plate-1:plane:z_max"]
            weak_face = planes["remote_bracket-1:plane:z_max"]
            self.assertEqual(contact_face["confidence_level"], "reviewable")
            self.assertTrue(contact_face["selection_policy"]["allow_reviewed_selection"])
            self.assertEqual(contact_face["selection_policy"]["block_automatic_selection"], False)
            self.assertEqual(weak_face["confidence_level"], "blocked")
            self.assertTrue(weak_face["selection_policy"]["block_automatic_selection"])
            self.assertIn("live_face_axis_selection_required", weak_face["selection_policy"]["required_evidence"])
            self.assertIn("interface_confidence_scoring_blocks_weak_bbox_only_targets", data["operator_notes"])

    def test_indexes_named_cylindrical_interfaces_from_hole_and_shaft_evidence(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "cylindrical_fixture.SLDASM",
                "components": [
                    {"name2": "bearing_block-1", "path": "C:/m/bearing_block.SLDPRT", "bbox_m": [-0.04, -0.03, -0.02, 0.04, 0.03, 0.02]},
                    {"name2": "drive_shaft-1", "path": "C:/m/drive_shaft.SLDPRT", "bbox_m": [-0.012, -0.012, -0.08, 0.012, 0.012, 0.08]},
                ],
                "features": [
                    {"name": "BearingBore_D24_Z", "type": "HoleWizard", "components": ["bearing_block-1"]},
                    {"name": "ShaftAxis_D24_Z", "type": "RevolveBoss", "components": ["drive_shaft-1"]},
                ],
                "dimensions": [
                    {"full_name": "DIA24@BearingBore_D24_Z@bearing_block.SLDPRT", "system_value_m": 0.024, "feature": "BearingBore_D24_Z"},
                    {"full_name": "DIA24@ShaftAxis_D24_Z@drive_shaft.SLDPRT", "system_value_m": 0.024, "feature": "ShaftAxis_D24_Z"},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            axes = {item["interface_id"]: item for item in data["cylindrical_interfaces"]}
            bore = axes["bearing_block-1:cylinder:BearingBore_D24_Z"]
            shaft = axes["drive_shaft-1:cylinder:ShaftAxis_D24_Z"]
            self.assertEqual(bore["role"], "bearing_bore")
            self.assertEqual(shaft["role"], "shaft_axis")
            self.assertEqual(bore["axis"], [0.0, 0.0, 1.0])
            self.assertEqual(bore["radius_m"], 0.012)
            self.assertEqual(bore["source_feature"], "BearingBore_D24_Z")
            self.assertEqual(bore["confidence_level"], "reviewable")
            self.assertEqual(bore["selector"]["fallback"]["type"], "cylindrical_axis")
            self.assertIn("named_cylindrical_interfaces_from_feature_and_dimension_evidence", data["operator_notes"])

    def test_indexes_slot_path_interfaces_from_slot_feature_evidence(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "slot_fixture.SLDASM",
                "components": [
                    {"name2": "guide_plate-1", "path": "C:/m/guide_plate.SLDPRT", "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.06, 0.012]},
                ],
                "features": [
                    {"name": "SliderSlot_L120_W12_X", "type": "SlotCut", "components": ["guide_plate-1"]},
                ],
                "dimensions": [
                    {"full_name": "SlotWidth@SliderSlot_L120_W12_X@guide_plate.SLDPRT", "system_value_m": 0.012, "feature": "SliderSlot_L120_W12_X"},
                    {"full_name": "SlotLength@SliderSlot_L120_W12_X@guide_plate.SLDPRT", "system_value_m": 0.120, "feature": "SliderSlot_L120_W12_X"},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            paths = {item["interface_id"]: item for item in data["slot_path_interfaces"]}
            slot = paths["guide_plate-1:slot:SliderSlot_L120_W12_X"]
            self.assertEqual(slot["role"], "slider_slot")
            self.assertEqual(slot["path_axis"], "x")
            self.assertEqual(slot["width_m"], 0.012)
            self.assertEqual(slot["length_m"], 0.12)
            self.assertEqual(slot["centerline_m"]["start"], [0.04, 0.03, 0.006])
            self.assertEqual(slot["centerline_m"]["end"], [0.16, 0.03, 0.006])
            self.assertEqual(slot["selector"]["fallback"]["type"], "slot_centerline")
            self.assertEqual(slot["slot_boundary_selectors"]["side_a"]["fallback"]["type"], "slot_side_wall")
            self.assertEqual(slot["slot_boundary_selectors"]["side_b"]["fallback"]["type"], "slot_side_wall")
            self.assertEqual(slot["slot_boundary_selectors"]["end_a"]["fallback"]["type"], "slot_end_arc")
            self.assertEqual(slot["slot_boundary_selectors"]["end_b"]["fallback"]["type"], "slot_end_arc")
            self.assertEqual(slot["slot_boundary_selectors"]["side_a"]["fallback"]["offset_m"], -0.006)
            self.assertEqual(slot["slot_boundary_selectors"]["side_b"]["fallback"]["offset_m"], 0.006)
            self.assertEqual(slot["mate_selector_refs"]["slot_centerline"], "guide_plate-1:slot:SliderSlot_L120_W12_X")
            self.assertEqual(slot["mate_selector_refs"]["side_a"], "guide_plate-1:slot:SliderSlot_L120_W12_X:side_a")
            self.assertEqual(slot["slot_boundary_selectors"]["side_a"]["native_identity"]["kind"], "face")
            self.assertEqual(slot["slot_boundary_selectors"]["end_a"]["native_identity"]["kind"], "edge_or_face")
            self.assertIn("slot_path_interfaces_from_feature_dimension_bbox_evidence", data["operator_notes"])

    def test_indexes_edge_treatment_selectors_from_fillet_and_chamfer_features(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "edge_treatment_fixture.SLDASM",
                "components": [
                    {"name2": "cover_plate-1", "path": "C:/m/cover_plate.SLDPRT", "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                ],
                "features": [
                    {"name": "EdgeFillet_R3_top_outer", "type": "Fillet", "components": ["cover_plate-1"]},
                    {"name": "Chamfer_C1p5_bottom_front", "type": "Chamfer", "components": ["cover_plate-1"]},
                ],
                "dimensions": [
                    {"full_name": "R@EdgeFillet_R3_top_outer@cover_plate.SLDPRT", "system_value_m": 0.003, "feature": "EdgeFillet_R3_top_outer"},
                    {"full_name": "D1@Chamfer_C1p5_bottom_front@cover_plate.SLDPRT", "system_value_m": 0.0015, "feature": "Chamfer_C1p5_bottom_front"},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")

            proc = run_py("--report", str(src), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            treatments = {item["interface_id"]: item for item in data["edge_treatment_interfaces"]}
            fillet = treatments["cover_plate-1:edge_treatment:EdgeFillet_R3_top_outer"]
            chamfer = treatments["cover_plate-1:edge_treatment:Chamfer_C1p5_bottom_front"]
            self.assertEqual(fillet["role"], "edge_rounding")
            self.assertEqual(fillet["radius_m"], 0.003)
            self.assertEqual(fillet["definition_readback"]["definition_type"], "Fillet")
            self.assertEqual(fillet["definition_readback"]["parameters"]["radius_m"], 0.003)
            self.assertEqual(fillet["definition_readback"]["dimensions"][0]["full_name"], "R@EdgeFillet_R3_top_outer@cover_plate.SLDPRT")
            self.assertEqual(fillet["definition_edit_spec"]["action"], "edit-definition")
            self.assertEqual(fillet["definition_edit_spec"]["edits"][0]["property"], "DefaultRadius")
            self.assertEqual(fillet["selector"]["fallback"]["type"], "edge_treatment_feature")
            self.assertEqual(fillet["selector"]["native_identity"]["kind"], "edge_or_face")
            self.assertEqual(chamfer["role"], "edge_break")
            self.assertEqual(chamfer["distance_m"], 0.0015)
            self.assertEqual(chamfer["definition_readback"]["definition_type"], "Chamfer")
            self.assertEqual(chamfer["definition_readback"]["parameters"]["distance_m"], 0.0015)
            self.assertEqual(chamfer["definition_edit_spec"]["edits"][0]["property"], "Distance")
            self.assertIn("edge_treatment_selectors_from_feature_dimension_evidence", data["operator_notes"])

    def test_swctl_routes_interface_index(self):
        report = {
            "active_document": {
                "type": "assembly",
                "title": "interface_fixture.SLDASM",
                "components": [
                    {"name2": "base_plate-1", "fixed": True, "bbox_m": [0.0, 0.0, 0.0, 0.20, 0.10, 0.012]},
                    {"name2": "cover_plate-1", "fixed": False, "bbox_m": [0.0, 0.0, 0.012, 0.20, 0.10, 0.024]},
                ],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            src = root / "inspect.json"
            out = root / "interface_index.json"
            src.write_text(json.dumps(report), encoding="utf-8")
            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "interface-index",
                    "-Report", str(src),
                    "-Out", str(out),
                    "-DistanceMm", "3",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertEqual(len(data["interfaces"]), 1)


if __name__ == "__main__":
    unittest.main()
