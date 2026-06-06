import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tests.solidworks_codex.test_mate_group_execute import (
    FakeAssembly,
    FakeComponent,
    FakeFace,
    FakeSurface,
)
from tools.solidworks_codex.scripts import sw_mate_intent_execute as mod

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "tools" / "solidworks_codex" / "scripts" / "sw_mate_intent_execute.py"


def run_py(*args: str):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def cylindrical_selector(component: str, stable_id: str, origin=None):
    return {
        "stable_id": stable_id,
        "component": component,
        "fallback": {
            "type": "cylindrical_axis",
            "axis": [0.0, 0.0, 1.0],
            "origin_m": origin or [0.0, 0.0, 0.0],
            "radius_m": 0.01,
        },
    }


def planar_selector(component: str, stable_id: str, normal, origin):
    return {
        "stable_id": stable_id,
        "component": component,
        "fallback": {
            "type": "bbox_planar_face",
            "normal": normal,
            "origin_m": origin,
        },
    }


class MateIntentExecuteTests(unittest.TestCase):
    def revolute_spec(self):
        return {
            "mode": "engineering_mate_intent",
            "design_intent": {"goal": "shaft mounted in bearing with axial locator"},
            "mate_intents": [
                {
                    "id": "main_shaft_bearing",
                    "kind": "revolute",
                    "components": ["shaft-1", "bearing-1"],
                    "axial_clearance_m": 0.001,
                    "axial_min_m": 0.0,
                    "axial_max_m": 0.002,
                    "interfaces": {
                        "shaft_axis": cylindrical_selector("shaft-1", "shaft-1:cylinder:axis"),
                        "bore_axis": cylindrical_selector("bearing-1", "bearing-1:cylinder:bore"),
                        "shaft_axial_face": planar_selector("shaft-1", "shaft-1:face:z_max", [0.0, 0.0, 1.0], [0.0, 0.0, 0.05]),
                        "housing_axial_face": planar_selector("bearing-1", "bearing-1:face:z_min", [0.0, 0.0, -1.0], [0.0, 0.0, 0.049]),
                    },
                }
            ],
        }

    def test_expands_revolute_intent_into_concentric_and_axial_locator(self):
        manifest = mod.expand_intent_spec(self.revolute_spec())

        self.assertEqual(manifest["mode"], "mate_intent_execute_manifest")
        self.assertEqual(len(manifest["macros"]), 2)
        self.assertEqual([item["mate_type"] for item in manifest["macros"]], ["concentric", "limit_distance"])
        self.assertEqual(manifest["macros"][0]["intent_kind"], "revolute")
        self.assertEqual(manifest["macros"][1]["distance_min_m"], 0.0)
        self.assertEqual(manifest["macros"][1]["distance_max_m"], 0.002)

    def test_executes_revolute_intent_through_existing_mate_executor(self):
        shaft_cylinder = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.01]),
            [-0.01, -0.01, -0.05, 0.01, 0.01, 0.05],
        )
        bearing_bore = FakeFace(
            FakeSurface("cylinder", [0.0, 0.0, 0.0, 0.0, 0.0, 1.0, 0.01]),
            [-0.01, -0.01, -0.02, 0.01, 0.01, 0.02],
        )
        shaft_end = FakeFace(
            FakeSurface("plane", [0.0, 0.0, 0.05, 0.0, 0.0, 1.0]),
            [-0.01, -0.01, 0.049, 0.01, 0.01, 0.051],
        )
        bearing_face = FakeFace(
            FakeSurface("plane", [0.0, 0.0, 0.049, 0.0, 0.0, -1.0]),
            [-0.02, -0.02, 0.048, 0.02, 0.02, 0.050],
        )
        asm = FakeAssembly([
            FakeComponent("shaft-1", [shaft_cylinder, shaft_end]),
            FakeComponent("bearing-1", [bearing_bore, bearing_face]),
        ])

        result = mod.execute_intent(self.revolute_spec(), asm)

        self.assertTrue(result["ok"], result)
        self.assertEqual(result["mode"], "mate_intent_execute")
        self.assertEqual(result["intent_counts"], {"mate_intents": 1, "expanded_mates": 2})
        self.assertEqual([mate["mate_type"] for mate in result["executed_mates"]], ["concentric", "limit_distance"])
        self.assertEqual([call[0] for call in asm.mates], [1, 5])
        self.assertEqual(asm.mates[1][3], 0.001)
        self.assertEqual(asm.mates[1][4], 0.002)
        self.assertEqual(asm.mates[1][5], 0.0)

    def test_expands_prismatic_intent_into_width_and_travel_limit(self):
        spec = {
            "mate_intents": [
                {
                    "id": "ram_ways",
                    "kind": "prismatic",
                    "components": ["ram-1", "left_way-1", "right_way-1"],
                    "distance_m": 0.025,
                    "distance_min_m": 0.0,
                    "distance_max_m": 0.05,
                    "interfaces": {
                        "guide_left_face": planar_selector("left_way-1", "left_way-1:face:y_max", [0, 1, 0], [0, -0.02, 0]),
                        "guide_right_face": planar_selector("right_way-1", "right_way-1:face:y_min", [0, -1, 0], [0, 0.02, 0]),
                        "slider_left_face": planar_selector("ram-1", "ram-1:face:y_min", [0, -1, 0], [0, -0.01, 0]),
                        "slider_right_face": planar_selector("ram-1", "ram-1:face:y_max", [0, 1, 0], [0, 0.01, 0]),
                        "travel_stop_face": planar_selector("ram-1", "ram-1:face:x_min", [-1, 0, 0], [-0.10, 0, 0]),
                        "travel_reference_face": planar_selector("frame-1", "frame-1:face:x_max", [1, 0, 0], [-0.125, 0, 0]),
                    },
                }
            ]
        }

        manifest = mod.expand_intent_spec(spec)

        self.assertEqual([item["mate_type"] for item in manifest["macros"]], ["width", "limit_distance"])
        self.assertEqual(manifest["macros"][1]["distance_max_m"], 0.05)

    def test_cli_dry_run_reports_expanded_intent_without_solidworks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec_path = root / "intent.json"
            out_path = root / "intent_execute.json"
            spec_path.write_text(json.dumps(self.revolute_spec()), encoding="utf-8")

            proc = run_py("--intent-spec", str(spec_path), "--out", str(out_path), "--dry-run")

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_path.read_text(encoding="utf-8-sig"))
            self.assertTrue(data["ok"], data)
            self.assertEqual(data["mode"], "mate_intent_execute")
            self.assertEqual(data["intent_counts"]["expanded_mates"], 2)
            self.assertEqual([item["mate_type"] for item in data["planned_mates"]], ["concentric", "limit_distance"])

    def test_swctl_routes_mate_intent_execute_dry_run(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            spec_path = root / "intent.json"
            out_path = root / "intent_execute.json"
            spec_path.write_text(json.dumps(self.revolute_spec()), encoding="utf-8")

            proc = subprocess.run(
                [
                    "powershell.exe",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    str(ROOT / "tools/solidworks_codex/swctl.ps1"),
                    "mate-intent-execute",
                    "-Report",
                    str(spec_path),
                    "-Out",
                    str(out_path),
                    "-ValidateOnly",
                ],
                cwd=ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )

            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_path.read_text(encoding="utf-8-sig"))
            self.assertEqual(data["intent_counts"]["mate_intents"], 1)


if __name__ == "__main__":
    unittest.main()
