import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run_py(script: str, *args: str):
    return subprocess.run(
        [sys.executable, str(ROOT / script), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class RestoreBackupTests(unittest.TestCase):
    def make_backup_report(self, d: str):
        root = Path(d)
        source = root / "sample.SLDPRT"
        backup = root / "backup" / "sample.SLDPRT"
        source.write_text("modified", encoding="utf-8")
        backup.parent.mkdir()
        backup.write_text("original", encoding="utf-8")
        report = root / "backup.json"
        report.write_text(json.dumps({
            "timestamp": "2026-06-01T00:00:00",
            "backup_root": str(backup.parent),
            "files": [{"source": str(source), "backup": str(backup)}],
        }), encoding="utf-8")
        return source, backup, report

    def test_restore_backup_dry_run_does_not_modify_source(self):
        with tempfile.TemporaryDirectory() as d:
            source, _backup, report = self.make_backup_report(d)
            out = Path(d) / "restore.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_restore_backup.py",
                "--report", str(report),
                "--out", str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(source.read_text(encoding="utf-8"), "modified")
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertFalse(data["applied"])
            self.assertEqual(data["files"][0]["status"], "planned")
            self.assertEqual(data["files"][0]["source_sha256_before"], data["files"][0]["source_sha256_after"])

    def test_restore_backup_apply_restores_source_file(self):
        with tempfile.TemporaryDirectory() as d:
            source, backup, report = self.make_backup_report(d)
            out = Path(d) / "restore.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_restore_backup.py",
                "--report", str(report),
                "--apply",
                "--out", str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertEqual(source.read_text(encoding="utf-8"), backup.read_text(encoding="utf-8"))
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertTrue(data["applied"])
            self.assertEqual(data["files"][0]["status"], "restored")
            self.assertEqual(data["files"][0]["source_sha256_after"], data["files"][0]["backup_sha256"])

    def test_restore_backup_reports_missing_backup_without_overwriting(self):
        with tempfile.TemporaryDirectory() as d:
            source, backup, report = self.make_backup_report(d)
            backup.unlink()
            out = Path(d) / "restore.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_restore_backup.py",
                "--report", str(report),
                "--apply",
                "--out", str(out),
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            self.assertEqual(source.read_text(encoding="utf-8"), "modified")
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            self.assertEqual(data["files"][0]["status"], "error")
            self.assertIn("backup_missing", data["files"][0]["errors"])


if __name__ == "__main__":
    unittest.main()
