
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


class ReleaseTreeTests(unittest.TestCase):
    def test_release_tree_allows_current_publishable_tree(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "release_tree.json"
            proc = run_py("tools/solidworks_codex/scripts/sw_release_tree.py", "--out", str(out))
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["violations"], [])
            for key in ["reports", "backups", "exports", "pycache", "personal_config", "generated_macros"]:
                self.assertIn(key, data["checks"])

    def test_release_tree_flags_forbidden_paths_in_file_list(self):
        with tempfile.TemporaryDirectory() as d:
            file_list = Path(d) / "files.txt"
            out = Path(d) / "release_tree.json"
            file_list.write_text(
                "README.md\n"
                "tools/solidworks_codex/reports/audit_latest.json\n"
                "tools/solidworks_codex/backups/20260601/model.SLDASM\n"
                "tools/solidworks_codex/macros/generated.swp.vba\n"
                "tests/solidworks_codex/__pycache__/test.cpython-312.pyc\n"
                "C:/Users/Alphahui/.codex/config.toml\n",
                encoding="utf-8",
            )
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_release_tree.py",
                "--from-file", str(file_list),
                "--out", str(out),
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            kinds = {v["kind"] for v in data["violations"]}
            self.assertTrue({"reports", "backups", "generated_macros", "pycache", "personal_config"}.issubset(kinds))


    def test_audit_includes_release_tree_gate(self):
        audit_source = (ROOT / "tools/solidworks_codex/scripts/sw_audit.py").read_text(encoding="utf-8-sig")
        self.assertIn("check_release_tree", audit_source)
        self.assertIn('"release_tree"', audit_source)


if __name__ == "__main__":
    unittest.main()
