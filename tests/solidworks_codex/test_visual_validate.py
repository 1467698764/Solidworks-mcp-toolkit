import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_visual_validate.py"
CAPTURE_SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_visual_capture.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def run_capture(*args: str):
    return subprocess.run(
        [sys.executable, str(CAPTURE_SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


class VisualValidateTests(unittest.TestCase):
    def inspect_report(self):
        return {
            "active_document": {
                "type": "assembly",
                "title": "visual_fixture.SLDASM",
                "components": [
                    {"name2": "base-1"},
                    {"name2": "slide-1"},
                ],
            }
        }

    def test_visual_gate_accepts_present_screenshot_and_nonblocking_review(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            review = root / "review.json"
            screenshot = root / "solidworks_window.png"
            out = root / "visual.json"
            report.write_text(json.dumps(self.inspect_report()), encoding="utf-8")
            review.write_text(json.dumps({"findings": [{"severity": "warning", "kind": "needs_better_angle"}]}), encoding="utf-8")
            screenshot.write_bytes(b"\x89PNG\r\n\x1a\nfake")

            proc = run_py("--report", str(report), "--screenshot", str(screenshot), "--visual-review", str(review), "--out", str(out))

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["counts"]["screenshots"], 1)
            self.assertEqual(data["findings"]["warning"][0]["kind"], "needs_better_angle")

    def test_visual_gate_blocks_missing_screenshot_and_contradiction(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            review = root / "review.json"
            out = root / "visual.json"
            report.write_text(json.dumps(self.inspect_report()), encoding="utf-8")
            review.write_text(json.dumps({"findings": [{"severity": "blocking", "kind": "visually_scattered", "reason": "slide floats far from base"}]}), encoding="utf-8")

            proc = run_py("--report", str(report), "--screenshot", str(root / "missing.png"), "--visual-review", str(review), "--out", str(out))

            self.assertEqual(proc.returncode, 1, proc.stderr + proc.stdout)
            data = json.loads(out.read_text(encoding="utf-8-sig"))
            kinds = {item["kind"] for item in data["findings"]["blocking"]}
            self.assertIn("screenshot_missing", kinds)
            self.assertIn("visually_scattered", kinds)

    def test_swctl_routes_visual_validate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = root / "inspect.json"
            screenshot = root / "solidworks_window.jpg"
            out = root / "visual.json"
            report.write_text(json.dumps(self.inspect_report()), encoding="utf-8")
            screenshot.write_bytes(b"\xff\xd8fake")

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "visual-validate",
                    "-Report", str(report),
                    "-Files", str(screenshot),
                    "-Out", str(out),
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            self.assertTrue(json.loads(out.read_text(encoding="utf-8-sig"))["ok"])

    def test_visual_capture_writes_reviewable_manifest_and_placeholder(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "screens"
            manifest = root / "capture.json"

            proc = run_capture("--out-dir", str(out_dir), "--manifest", str(manifest), "--placeholder")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["capture_method"], "placeholder_png")
            self.assertEqual(len(data["screenshots"]), 1)
            screenshot = Path(data["screenshots"][0]["path"])
            self.assertTrue(screenshot.exists())
            self.assertGreater(screenshot.stat().st_size, 0)
            self.assertEqual(data["screenshots"][0]["evidence_role"], "solidworks_window_capture")

    def test_swctl_routes_visual_capture(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_dir = root / "screens"
            manifest = root / "capture.json"

            proc = subprocess.run(
                [
                    "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "visual-capture",
                    "-OutDir", str(out_dir),
                    "-Out", str(manifest),
                    "-ValidateOnly",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(manifest.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["capture_method"], "placeholder_png")


if __name__ == "__main__":
    unittest.main()
