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


class PublicCopyGuardTests(unittest.TestCase):
    def test_public_copy_guard_blocks_rank_boasting_in_source_docs(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "copy_guard.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_public_copy_guard.py",
                "--out", str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["violations"], [])
            self.assertGreaterEqual(data["files_checked"], 10)

    def test_public_copy_guard_blocks_mojibake_patterns(self):
        source = (ROOT / "tools/solidworks_codex/scripts/sw_public_copy_guard.py").read_text(encoding="utf-8-sig")
        self.assertIn("MOJIBAKE_PATTERNS", source)
        samples = ["\u6d93", "\u9225", "\u9241", "\u951b", "\u9286"]
        patterns = [p.pattern for p in __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_public_copy_guard.py"))["MOJIBAKE_PATTERNS"]]
        for sample in samples:
            self.assertRegex(sample, "|".join(patterns))

    def test_public_copy_guard_blocks_personal_or_robot_specific_public_positioning(self):
        module = __import__("runpy").run_path(str(ROOT / "tools/solidworks_codex/scripts/sw_public_copy_guard.py"))
        patterns = module["FORBIDDEN"]
        samples = [
            "\u672c\u6587\u8bf4\u660e\u5982\u4f55\u8ba9 Codex \u53c2\u4e0e SolidWorks \u6bd5\u8bbe\u673a\u5668\u4eba\u5173\u8282\u6a21\u7ec4\u8bbe\u8ba1",
            "Open the target robot joint assembly in SolidWorks.",
            "session-snapshot -SessionName joint-baseline",
            "report-context -Target bearing encoder flange",
            "backup -Files 'C:/robot/joint.SLDASM'",
            "export -Target tools/solidworks_codex/exports/joint.step",
            "\u5e2e\u6211\u4f18\u5316\u4e00\u4e0b\u6574\u4e2a\u5173\u8282\u3002",
        ]
        for sample in samples:
            self.assertTrue(any(p.search(sample) for p in patterns), sample)


if __name__ == "__main__":
    unittest.main()
