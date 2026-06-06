import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(ROOT / "tools/solidworks_codex/scripts/sw_standard_part_resolve.py"), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class StandardPartResolveTests(unittest.TestCase):
    def test_resolves_reviewed_catalog_part_to_component_insert_spec(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            library = root / "hardware"
            library.mkdir()
            part = library / "M6_socket_head.SLDPRT"
            part.write_text("sample", encoding="utf-8")
            catalog = root / "catalog.json"
            request = root / "request.json"
            out = root / "resolved.json"
            component_spec = root / "component_insert.json"
            catalog.write_text(json.dumps({
                "approved_roots": [str(library)],
                "items": [
                    {
                        "id": "m6_socket_head",
                        "path": str(part),
                        "standard": "ISO 4762",
                        "supplier": "local-vault",
                        "license": "reviewed_local_library",
                        "role": "fastener",
                        "required_mates": ["concentric", "coincident"],
                        "configuration": "M6x20",
                        "inserted_selector": {
                            "stable_id": "m6_socket_head:axis:shank",
                            "native_identity": {"kind": "axis", "tracking_id": "bolt-axis"},
                        },
                    }
                ],
            }), encoding="utf-8")
            request.write_text(json.dumps({
                "id": "m6_socket_head",
                "component_name": "standard_m6_socket_head-1",
                "origin_m": [0, 0, 0.02],
                "attachment": {
                    "host_component": "base_plate-1",
                    "host_interface_id": "base_plate-1:hole:m6_01",
                    "mate_group_id": "MG_m6_socket_head_01",
                    "host_selector": {
                        "stable_id": "base_plate-1:hole:m6_01",
                        "native_identity": {"kind": "face_or_axis", "tracking_id": "host-hole"},
                    },
                },
            }), encoding="utf-8")

            proc = run_py("--catalog", str(catalog), "--request", str(request), "--out", str(out), "--component-spec-out", str(component_spec))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["source_policy"]["status"], "approved_local_source")
            self.assertEqual(data["resolved_item"]["id"], "m6_socket_head")
            self.assertEqual(data["component_insert_spec"]["part_path"], str(part))
            self.assertEqual(data["component_insert_spec"]["standard_part"], True)
            self.assertEqual(data["component_insert_spec"]["attachment"]["required_mates"], ["concentric", "coincident"])
            self.assertEqual(data["component_insert_spec"]["attachment"]["host_selector"]["stable_id"], "base_plate-1:hole:m6_01")
            self.assertEqual(data["component_insert_spec"]["attachment"]["inserted_selector"]["stable_id"], "m6_socket_head:axis:shank")
            self.assertEqual(json.loads(component_spec.read_text(encoding="utf-8-sig")), data["component_insert_spec"])

    def test_blocks_unapproved_or_missing_standard_part_sources(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            approved = root / "approved"
            outside = root / "outside"
            approved.mkdir()
            outside.mkdir()
            part = outside / "bearing.SLDPRT"
            part.write_text("sample", encoding="utf-8")
            catalog = root / "catalog.json"
            request = root / "request.json"
            out = root / "resolved.json"
            catalog.write_text(json.dumps({
                "approved_roots": [str(approved)],
                "items": [{"id": "bearing", "path": str(part), "supplier": "unknown"}],
            }), encoding="utf-8")
            request.write_text(json.dumps({"id": "bearing"}), encoding="utf-8")

            proc = run_py("--catalog", str(catalog), "--request", str(request), "--out", str(out))

            self.assertNotEqual(proc.returncode, 0)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"])
            self.assertIn("unapproved_source_root", {item["kind"] for item in data["blockers"]})

    def test_swctl_routes_standard_part_resolve(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            library = root / "hardware"
            library.mkdir()
            part = library / "dowel_pin.SLDPRT"
            part.write_text("sample", encoding="utf-8")
            catalog = root / "catalog.json"
            request = root / "request.json"
            out = root / "resolved.json"
            component_spec = root / "component_insert.json"
            catalog.write_text(json.dumps({
                "approved_roots": [str(library)],
                "items": [{"id": "dowel_pin", "path": str(part), "supplier": "local-vault", "license": "reviewed_local_library"}],
            }), encoding="utf-8")
            request.write_text(json.dumps({"id": "dowel_pin"}), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "standard-part-resolve",
                    "-Manifest", str(catalog),
                    "-Report", str(request),
                    "-Out", str(out),
                    "-JsonOut", str(component_spec),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(json.loads(component_spec.read_text(encoding="utf-8-sig"))["part_path"], str(part))


if __name__ == "__main__":
    unittest.main()
