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


class ReportSearchTests(unittest.TestCase):
    def test_search_finds_components_dimensions_and_features_by_query(self):
        with tempfile.TemporaryDirectory() as d:
            out_md = Path(d) / "search.md"
            out_json = Path(d) / "search.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_report_search.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--query", "support bushing D1 Fillet",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn("SolidWorks Report Search", text)
            self.assertIn("support_bushing-1", text)
            self.assertIn("D1@Sketch1@plate.SLDPRT", text)
            self.assertIn("Fillet1", text)
            self.assertGreaterEqual(data["counts"]["components"], 1)
            self.assertGreaterEqual(data["counts"]["dimensions"], 1)
            self.assertGreaterEqual(data["counts"]["features"], 1)

    def test_search_can_filter_only_suppressed_components(self):
        with tempfile.TemporaryDirectory() as d:
            out_json = Path(d) / "suppressed.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_report_search.py",
                "--report", "tools/solidworks_codex/sandbox/report_after.json",
                "--kind", "components",
                "--state", "suppressed",
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            names = [x["name2"] for x in data["components"]]
            self.assertEqual(names, ["support_bushing-1"])
            self.assertEqual(data["counts"]["dimensions"], 0)
            self.assertEqual(data["counts"]["features"], 0)


if __name__ == "__main__":
    unittest.main()
