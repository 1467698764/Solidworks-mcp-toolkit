import json
import subprocess
import sys
import tempfile
import textwrap
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


class SafeSetDimensionTests(unittest.TestCase):
    def make_fake_swctl(self, root: Path, fail_command: str | None = None) -> Path:
        calls = root / "calls.jsonl"
        script = root / "fake_swctl.py"
        script.write_text(textwrap.dedent(f"""
            import json
            import sys
            from pathlib import Path

            args = sys.argv[1:]
            command = args[0] if args else ''
            calls = Path({str(calls)!r})
            with calls.open('a', encoding='utf-8') as fh:
                fh.write(json.dumps(args) + '\\n')

            def value_after(flag):
                if flag not in args:
                    return None
                idx = args.index(flag)
                return args[idx + 1]

            out = value_after('-Out')
            json_out = value_after('-JsonOut')
            fail_command = {fail_command!r}
            if fail_command and command == fail_command:
                if out:
                    Path(out).parent.mkdir(parents=True, exist_ok=True)
                    Path(out).write_text(json.dumps({{'ok': False, 'command': command}}), encoding='utf-8')
                sys.exit(9)

            if command == 'backup' and out:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_text(json.dumps({{'ok': True, 'files': [{{'source': 'model.SLDPRT', 'backup': 'backup/model.SLDPRT'}}]}}), encoding='utf-8')
            elif command in ('inspect', 'set-dimension', 'rebuild') and out:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_text(json.dumps({{'ok': True, 'command': command}}), encoding='utf-8')
            elif command == 'compare':
                if out:
                    Path(out).parent.mkdir(parents=True, exist_ok=True)
                    Path(out).write_text('# delta\\n', encoding='utf-8')
                if json_out:
                    Path(json_out).parent.mkdir(parents=True, exist_ok=True)
                    Path(json_out).write_text(json.dumps({{'dimensions': {{'changed': [{{'key': 'D1@Sketch1@part.SLDPRT', 'before_m': 0.01, 'after_m': 0.012}}]}}, 'components': {{'added': [], 'removed': [], 'changed': []}}, 'features': {{'count_changes': []}}}}), encoding='utf-8')
            elif command == 'change-verify' and out:
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_text(json.dumps({{'ok': True, 'unexpected': [], 'summary': {{'accepted': 1, 'unexpected': 0}}}}), encoding='utf-8')
            sys.exit(0)
        """), encoding="utf-8")
        return script

    def test_safe_set_dimension_runs_guarded_pipeline_in_order(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fake = self.make_fake_swctl(root)
            out = root / "safe_edit.json"
            out_dir = root / "artifacts"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_safe_set_dimension.py",
                "--swctl", str(fake),
                "--model", str(root / "part.SLDPRT"),
                "--dimension", "D1@Sketch1@part.SLDPRT",
                "--value-m", "0.012",
                "--out-dir", str(out_dir),
                "--out", str(out),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual([step["name"] for step in data["steps"]], [
                "backup", "inspect_before", "set_dimension", "rebuild", "inspect_after", "compare", "change_verify"
            ])
            self.assertIn("restore-backup", data["rollback_command"])
            calls = [json.loads(line) for line in (root / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([call[0] for call in calls], ["backup", "inspect", "set-dimension", "rebuild", "inspect", "compare", "change-verify"])
            self.assertIn("-AllowDimension", calls[-1])
            self.assertIn("D1@Sketch1@part.SLDPRT", calls[-1])

    def test_safe_set_dimension_stops_before_edit_when_backup_fails(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            fake = self.make_fake_swctl(root, fail_command="backup")
            out = root / "safe_edit.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_safe_set_dimension.py",
                "--swctl", str(fake),
                "--model", str(root / "part.SLDPRT"),
                "--dimension", "D1@Sketch1@part.SLDPRT",
                "--value-m", "0.012",
                "--out-dir", str(root / "artifacts"),
                "--out", str(out),
            )
            self.assertNotEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertFalse(data["ok"], data)
            self.assertEqual(data["failed_step"], "backup")
            calls = [json.loads(line) for line in (root / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual([call[0] for call in calls], ["backup"])


if __name__ == "__main__":
    unittest.main()
