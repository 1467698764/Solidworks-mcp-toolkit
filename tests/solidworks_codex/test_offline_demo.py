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


class OfflineDemoTests(unittest.TestCase):
    def test_offline_demo_generates_reader_friendly_bundle(self):
        with tempfile.TemporaryDirectory() as d:
            out_dir = Path(d) / "demo"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_offline_demo.py",
                "--out-dir", str(out_dir),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            manifest = json.loads((out_dir / "manifest.json").read_text(encoding="utf-8-sig"))
            readme = (out_dir / "README.md").read_text(encoding="utf-8-sig")
            self.assertTrue(manifest["ok"])
            for name in [
                "tool_catalog.md",
                "context.md",
                "worklog.md",
                "handoff/README.md",
            ]:
                self.assertIn(name, manifest["files"])
                self.assertTrue((out_dir / name).exists(), name)
            self.assertIn("5-minute offline demo", readme)
            self.assertIn("practical differentiator", readme)
            self.assertIn("report-context", readme)
            self.assertIn("handoff-bundle", readme)
            context = (out_dir / "context.md").read_text(encoding="utf-8-sig").lower()
            handoff = (out_dir / "handoff" / "context.md").read_text(encoding="utf-8-sig").lower()
            self.assertIn("flexible next queries", context)
            self.assertIn("evidence gaps", context)
            self.assertNotIn("mounting interface", context + "\n" + handoff)
            public_text = "\n".join(
                p.read_text(encoding="utf-8-sig", errors="replace")
                for p in out_dir.rglob("*")
                if p.is_file() and p.suffix.lower() in {".md", ".json", ".jsonl"}
            )
            self.assertNotIn("C:\\Users\\", public_text)
            self.assertNotIn("AppData\\Local", public_text)


if __name__ == "__main__":
    unittest.main()
