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


class ReportContextTests(unittest.TestCase):
    def test_context_pack_builds_freeform_handoff_from_report(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "context.md"
            out_json = Path(d) / "context.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_report_context.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--focus", "mounting interface thickness",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            text = out_md.read_text(encoding="utf-8-sig")
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            self.assertIn("SolidWorks Codex Context Pack", text)
            self.assertIn("support_bushing-1", text)
            self.assertIn("D1@Sketch1@plate.SLDPRT", text)
            self.assertIn("Do not blindly replay templates", text)
            self.assertIn("report-search", text)
            self.assertEqual(data["document"]["title"], "sample_machine.SLDASM")
            self.assertGreaterEqual(data["inventory"]["component_count"], 3)
            self.assertTrue(any(r["kind"] == "suppressed_component" for r in data["risks"]))
            self.assertTrue(any(a["kind"] == "dimension" for a in data["anchors"]))


if __name__ == "__main__":
    unittest.main()
