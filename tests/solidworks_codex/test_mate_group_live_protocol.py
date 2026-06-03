import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_group_live_protocol.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class MateGroupLiveProtocolTests(unittest.TestCase):
    def manifest(self):
        return {
            "mode": "reviewable_mate_group_macros",
            "macros": [
                {
                    "group_id": "ram_to_ways",
                    "mate_type": "coincident",
                    "expected_mate_name": "MG_ram_to_ways_01_coincident",
                    "macro": "C:/work/macros/ram_to_ways_01_coincident.swp.vba",
                    "components": ["ram-1", "bed_ways-1"],
                    "verification": ["rebuild", "mate_errors"],
                },
                {
                    "group_id": "ram_to_ways",
                    "mate_type": "parallel",
                    "expected_mate_name": "MG_ram_to_ways_02_parallel",
                    "macro": "C:/work/macros/ram_to_ways_02_parallel.swp.vba",
                    "components": ["ram-1", "bed_ways-1"],
                    "verification": ["rebuild", "mate_errors"],
                },
                {
                    "group_id": "crank_shaft",
                    "mate_type": "concentric",
                    "expected_mate_name": "MG_crank_shaft_01_concentric",
                    "macro": "C:/work/macros/crank_shaft_01_concentric.swp.vba",
                    "components": ["crank_disk-1", "crank_shaft-1"],
                    "verification": ["rebuild", "mate_errors"],
                },
            ],
        }

    def validation_ok(self):
        return {
            "ok": True,
            "counts": {"blocking_findings": 0},
            "findings": {"blocking": [], "warning": []},
        }

    def test_live_protocol_expands_macros_into_grouped_stop_checked_steps(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "macro_manifest.json"
            validation = root / "validation.json"
            out = root / "live_protocol.json"
            md = root / "live_protocol.md"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            validation.write_text(json.dumps(self.validation_ok()), encoding="utf-8")

            proc = run_py(
                "--macro-manifest", str(manifest),
                "--validation-report", str(validation),
                "--model", "C:/models/shaper.SLDASM",
                "--out", str(out),
                "--markdown-out", str(md),
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["model"], "C:/models/shaper.SLDASM")
            self.assertTrue(data["policy"]["one_group_at_a_time"])
            self.assertTrue(data["policy"]["stop_on_blocker"])
            self.assertEqual(data["counts"]["groups"], 2)
            self.assertEqual(data["counts"]["expected_mates"], 3)
            group_ids = [group["group_id"] for group in data["groups"]]
            self.assertEqual(group_ids, ["ram_to_ways", "crank_shaft"])
            first_steps = [step["action"] for step in data["groups"][0]["steps"]]
            for action in [
                "backup_native_files",
                "capture_before_snapshot",
                "select_live_entities_for_macro",
                "mate_selection_check",
                "run_reviewed_macro",
                "rebuild",
                "inspect_after_group",
                "mate_group_execution_check",
                "interference_check",
                "cleanup_locks_and_windows",
            ]:
                self.assertIn(action, first_steps)
            self.assertIn("MG_ram_to_ways_01_coincident", md.read_text(encoding="utf-8-sig"))

    def test_live_protocol_blocks_when_validation_has_blocking_findings(self):
        validation = self.validation_ok()
        validation["ok"] = False
        validation["findings"]["blocking"] = [{"kind": "unsupported_mate_type", "group_id": "bad"}]
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "macro_manifest.json"
            validation_path = root / "validation.json"
            out = root / "live_protocol.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            validation_path.write_text(json.dumps(validation), encoding="utf-8")

            proc = run_py("--macro-manifest", str(manifest), "--validation-report", str(validation_path), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            self.assertEqual(data["groups"], [])
            self.assertEqual(data["findings"]["blocking"][0]["kind"], "validation_not_ok")

    def test_swctl_routes_mate_group_live_protocol(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            manifest = root / "macro_manifest.json"
            validation = root / "validation.json"
            out = root / "live_protocol.json"
            manifest.write_text(json.dumps(self.manifest()), encoding="utf-8")
            validation.write_text(json.dumps(self.validation_ok()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-group-live-protocol",
                    "-Report", str(manifest),
                    "-FromReport", str(validation),
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"])


if __name__ == "__main__":
    unittest.main()
