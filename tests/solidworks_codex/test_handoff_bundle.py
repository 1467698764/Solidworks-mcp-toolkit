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


class HandoffBundleTests(unittest.TestCase):
    def test_handoff_bundle_collects_report_context_worklog_and_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "handoff"
            worklog = Path(d) / "worklog.jsonl"
            # Seed a worklog event so the bundle proves it can carry decision history.
            seed = run_py(
                "tools/solidworks_codex/scripts/sw_worklog.py",
                "--log", str(worklog),
                "--summary-out", str(Path(d) / "worklog.md"),
                "--session", "sample-machine-baseline",
                "--event", "decision",
                "--message", "Prefer report-driven anchors over template-only generation",
                "--artifact", "tools/solidworks_codex/sandbox/report_after.json",
                "--next", "Generate handoff bundle",
            )
            self.assertEqual(seed.returncode, 0, seed.stderr + seed.stdout)

            proc = run_py(
                "tools/solidworks_codex/scripts/sw_handoff_bundle.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--worklog", str(worklog),
                "--focus", "mounting interface thickness",
                "--out-dir", str(out_dir),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8-sig"))
            readme = (out_dir / "README.md").read_text(encoding="utf-8-sig")
            context = (out_dir / "context.md").read_text(encoding="utf-8-sig")
            self.assertTrue(manifest["ok"])
            self.assertEqual(manifest["document"]["title"], "sample_machine.SLDASM")
            self.assertIn("context.md", manifest["files"])
            self.assertIn("worklog.md", manifest["files"])
            self.assertIn("audit_latest.json", manifest["suggested_inputs"])
            self.assertIn("SolidWorks Codex Handoff Bundle", readme)
            self.assertIn("Do not blindly replay templates", readme)
            self.assertIn("Prefer report-driven anchors", readme)
            self.assertIn("support_bushing-1", context)


class SessionSnapshotEncodingTests(unittest.TestCase):
    def test_run_captures_non_gbk_output_without_reader_thread_decode_error(self):
        with tempfile.TemporaryDirectory() as d:
            script = Path(d) / "emit_unicode.py"
            script.write_text("print('SolidWorks ?? ? ?')", encoding="utf-8")
            code = (
                "from tools.solidworks_codex.scripts import sw_session_snapshot as mod; "
                "import sys, json; "
                f"result = mod.run([sys.executable, {str(script)!r}]); "
                "print(json.dumps(result, ensure_ascii=False))"
            )
            proc = subprocess.run(
                [sys.executable, "-c", code],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(proc.stdout)
            self.assertEqual(data["returncode"], 0)
            self.assertIn("??", data["stdout"])
            self.assertIn("?", data["stdout"])


if __name__ == "__main__":
    unittest.main()

