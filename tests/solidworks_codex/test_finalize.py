
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class FinalizeTests(unittest.TestCase):
    def test_finalize_audit_timeout_covers_full_release_gate(self):
        script = (ROOT / "tools/solidworks_codex/scripts/sw_finalize.py").read_text(encoding="utf-8-sig")
        self.assertIn("timeout=300", script)

    def test_finalize_json_is_powershell_parseable_and_compact(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "final.md"
            jout = Path(d) / "final.json"
            proc = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "tools/solidworks_codex/scripts/sw_finalize.py"),
                    "--out", str(out),
                    "--json-out", str(jout),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(jout.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["audit_ok"], data)
            self.assertIn("checks", data["audit"])
            self.assertNotIn("stdout", json.dumps(data, ensure_ascii=False))
            ps = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-Command",
                    f"$j = Get-Content -Raw '{jout}' | ConvertFrom-Json; if (-not $j.audit_ok) {{ exit 2 }}",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            self.assertEqual(ps.returncode, 0, ps.stderr + ps.stdout)


if __name__ == "__main__":
    unittest.main()
