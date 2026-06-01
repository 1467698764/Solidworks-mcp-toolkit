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


class WorklogTests(unittest.TestCase):
    def test_worklog_appends_decision_and_next_step(self):
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "joint_worklog.jsonl"
            md = Path(d) / "joint_worklog.md"

            first = run_py(
                "tools/solidworks_codex/scripts/sw_worklog.py",
                "--log", str(log),
                "--summary-out", str(md),
                "--session", "sample-machine-baseline",
                "--event", "decision",
                "--message", "Use report-context before editing flange thickness",
                "--artifact", "tools/solidworks_codex/sandbox/report_after.json",
                "--next", "Run backup before any write",
            )
            self.assertEqual(first.returncode, 0, first.stderr + first.stdout)

            second = run_py(
                "tools/solidworks_codex/scripts/sw_worklog.py",
                "--log", str(log),
                "--summary-out", str(md),
                "--session", "sample-machine-baseline",
                "--event", "verification",
                "--message", "MCP smoke passed with report-context exposed",
                "--artifact", "tools/solidworks_codex/mcp/smoke-test.cjs",
            )
            self.assertEqual(second.returncode, 0, second.stderr + second.stdout)

            events = [json.loads(line) for line in log.read_text(encoding="utf-8-sig").splitlines()]
            text = md.read_text(encoding="utf-8-sig")
            self.assertEqual(len(events), 2)
            self.assertEqual(events[0]["event"], "decision")
            self.assertIn("Use report-context", text)
            self.assertIn("Run backup before any write", text)
            self.assertIn("MCP smoke passed", text)
            self.assertIn("tools/solidworks_codex/sandbox/report_after.json", text)


if __name__ == "__main__":
    unittest.main()
