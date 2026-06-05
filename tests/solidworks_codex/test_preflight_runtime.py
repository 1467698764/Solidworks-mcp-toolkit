import tempfile
import unittest
from pathlib import Path

from tools.solidworks_codex.scripts import sw_preflight as mod


class PreflightRuntimeTests(unittest.TestCase):
    def test_runtime_environment_reports_memory_locks_and_artifact_boundaries(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            generated = root / "generated"
            reports = root / "reports"
            screenshots = root / "screenshots"
            generated.mkdir()
            reports.mkdir()
            screenshots.mkdir()
            (generated / "~$fixture.SLDASM").write_text("", encoding="utf-8")
            (screenshots / "view.png").write_bytes(b"\x89PNG\r\n\x1a\n")

            result = mod.runtime_environment_report(
                generated_roots=[generated],
                report_roots=[reports],
                screenshot_roots=[screenshots],
                memory_budget_mb=512,
                process_rows=[{"name": "SLDWORKS", "private_memory_mb": 768}],
            )

        self.assertFalse(result["ok"])
        self.assertEqual(result["memory"]["budget_mb"], 512)
        self.assertEqual(result["memory"]["peak_private_memory_mb"], 768)
        self.assertEqual(result["lock_files"]["count"], 1)
        self.assertEqual(result["screenshots"]["count"], 1)
        self.assertEqual(result["artifact_hygiene"]["generated_roots"], [str(generated.resolve())])
        self.assertIn("memory_budget_exceeded", result["failed"])
        self.assertIn("generated_lock_files_present", result["failed"])


if __name__ == "__main__":
    unittest.main()
