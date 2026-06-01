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


class BackupStatusTests(unittest.TestCase):
    def write_report(self, root: Path, entries):
        report = root / "backup.json"
        report.write_text(json.dumps({
            "timestamp": "2026-06-01T00:00:00",
            "backup_root": str(root / "backup"),
            "files": entries,
        }), encoding="utf-8")
        return report

    def test_backup_status_marks_unchanged_and_changed_sources(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            unchanged = root / "unchanged.SLDPRT"
            changed = root / "changed.SLDASM"
            unchanged_bak = backup_dir / "unchanged.SLDPRT"
            changed_bak = backup_dir / "changed.SLDASM"
            unchanged.write_text("same", encoding="utf-8")
            unchanged_bak.write_text("same", encoding="utf-8")
            changed.write_text("after", encoding="utf-8")
            changed_bak.write_text("before", encoding="utf-8")
            report = self.write_report(root, [
                {"source": str(unchanged), "backup": str(unchanged_bak)},
                {"source": str(changed), "backup": str(changed_bak)},
            ])
            out = root / "status.json"
            proc = run_py("tools/solidworks_codex/scripts/sw_backup_status.py", "--report", str(report), "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            by_name = {Path(item["source"]).name: item for item in data["files"]}
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["summary"]["unchanged"], 1)
            self.assertEqual(data["summary"]["changed"], 1)
            self.assertEqual(by_name["unchanged.SLDPRT"]["status"], "unchanged")
            self.assertEqual(by_name["changed.SLDASM"]["status"], "changed")
            self.assertTrue(by_name["changed.SLDASM"]["restorable"])

    def test_backup_status_reports_missing_source_and_backup(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            backup_dir = root / "backup"
            backup_dir.mkdir()
            missing_source = root / "missing_source.SLDPRT"
            missing_backup = backup_dir / "missing_backup.SLDPRT"
            report = self.write_report(root, [
                {"source": str(missing_source), "backup": str(backup_dir / "existing.SLDPRT")},
                {"source": str(root / "existing.SLDPRT"), "backup": str(missing_backup)},
            ])
            (backup_dir / "existing.SLDPRT").write_text("backup", encoding="utf-8")
            (root / "existing.SLDPRT").write_text("source", encoding="utf-8")
            out = root / "status.json"
            proc = run_py("tools/solidworks_codex/scripts/sw_backup_status.py", "--report", str(report), "--out", str(out))
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            statuses = {Path(item["source"]).name: item for item in data["files"]}
            self.assertFalse(data["ok"], data)
            self.assertEqual(statuses["missing_source.SLDPRT"]["status"], "source_missing")
            self.assertIn("source_missing", statuses["missing_source.SLDPRT"]["errors"])
            self.assertEqual(statuses["existing.SLDPRT"]["status"], "backup_missing")
            self.assertFalse(statuses["existing.SLDPRT"]["restorable"])


if __name__ == "__main__":
    unittest.main()
