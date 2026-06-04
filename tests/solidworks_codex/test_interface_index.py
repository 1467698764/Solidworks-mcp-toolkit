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
            self.assertIn("reopen_repair_selector", selector["tags"])

            systems = {item["component"]: item for item in data["coordinate_systems"]}
            csys_selector = systems["base_plate-1"]["selector"]
            self.assertEqual(csys_selector["stable_id"], "base_plate-1:csys:bbox_center")
            self.assertEqual(csys_selector["fallback"]["type"], "bbox_center_coordinate_system")
            self.assertEqual(data["interfaces"][0]["selector_refs"]["a"], "base_plate-1:plane:z_max")
            self.assertEqual(data["interfaces"][0]["selector_refs"]["b"], "cover_plate-1:plane:z_min")

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
