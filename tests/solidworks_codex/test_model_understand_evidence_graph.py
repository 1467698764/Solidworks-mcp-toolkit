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


class ModelUnderstandEvidenceGraphTests(unittest.TestCase):
    def make_report(self, root: Path) -> Path:
        report = {
            "active_document": {
                "title": "fixture_evidence.SLDASM",
                "path": "C:/machines/fixture_evidence.SLDASM",
                "type": "assembly",
                "components": [
                    {"name2": "base_plate-1", "path": "C:/machines/base_plate.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [-0.10, -0.07, 0.0, 0.10, 0.07, 0.012], "transform_array": [1,0,0,0,1,0,0,0,1,0,0,0,1,0,0,0]},
                    {"name2": "locator_block-1", "path": "C:/machines/locator_block.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.04, -0.025, 0.012, 0.04, 0.025, 0.05], "transform_array": [0,-1,0,1,0,0,0,0,1,0.01,0.02,0.012,1,0,0,0]},
                    {"name2": "cover_plate-1", "path": "C:/machines/cover_plate.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.045, -0.03, 0.050, 0.045, 0.03, 0.058]},
                    {"name2": "dowel_pin-1", "path": "C:/machines/dowel_pin.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [-0.034, -0.019, 0.0, -0.028, -0.013, 0.058]},
                    {"name2": "bolt_m6-1", "path": "C:/machines/bolt_m6.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0.028, 0.013, -0.004, 0.036, 0.021, 0.061]},
                ],
                "dimensions": [
                    {"full_name": "DowelHoleDia@Sketch1@base_plate.SLDPRT", "system_value_m": 0.006, "feature": "Sketch1"},
                    {"full_name": "BoltCirclePitch@Sketch2@cover_plate.SLDPRT", "system_value_m": 0.064, "feature": "Sketch2"},
                    {"full_name": "ClampClearance@Sketch3@locator_block.SLDPRT", "system_value_m": 0.0015, "feature": "Sketch3"},
                ],
                "features": [
                    {"name": "ConcentricMate-dowel-base", "type": "Mate", "entities": ["dowel_pin-1", "base_plate-1"]},
                    {"name": "CoincidentMate-cover-locator", "type": "Mate", "entities": ["cover_plate-1", "locator_block-1"]},
                    {"name": "HoleWizard-M6-clearance", "type": "HoleWzd", "component": "cover_plate-1"},
                    {"name": "TappedHole-M8", "type": "HoleWzd", "component": "locator_block-1"},
                    {"name": "DowelHolePattern", "type": "LPattern", "component": "base_plate-1"},
                    {"name": "CutAccessWindow", "type": "Cut", "component": "locator_block-1"},
                ],
            }
        }
        path = root / "fixture_evidence.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        return path

    def test_evidence_graph_fuses_mates_holes_spatial_and_manufacturing_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_json = root / "understanding.json"
            out_md = root / "understanding.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(self.make_report(root)),
                "--task", "评估夹具定位孔、压板装配约束、间隙和加工可行性",
                "--view", "manufacturing-holes",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            graph = data["cad_evidence_graph"]
            self.assertIn("mate_evidence", graph)
            self.assertIn("manufacturing_evidence", graph)
            self.assertIn("spatial_evidence", graph)
            mate_pairs = {(m["a"], m["b"], m["mate_type"]) for m in graph["mate_evidence"]}
            self.assertIn(("dowel_pin-1", "base_plate-1", "concentric"), mate_pairs)
            self.assertIn(("cover_plate-1", "locator_block-1", "coincident"), mate_pairs)
            feature_names = {f["name"] for f in graph["manufacturing_evidence"]["features"]}
            self.assertIn("HoleWizard-M6-clearance", feature_names)
            self.assertIn("DowelHolePattern", feature_names)
            feature_kinds = {f["name"]: f["kind"] for f in graph["manufacturing_evidence"]["features"]}
            self.assertEqual(feature_kinds["TappedHole-M8"], "thread")
            dimension_names = {d["name"] for d in graph["manufacturing_evidence"]["dimensions"]}
            self.assertIn("BoltCirclePitch@Sketch2@cover_plate.SLDPRT", dimension_names)
            hole_groups = graph["manufacturing_evidence"]["hole_groups"]
            cover_group = next(g for g in hole_groups if g["component"] == "cover_plate-1")
            self.assertIn("HoleWizard-M6-clearance", cover_group["features"])
            self.assertIn("BoltCirclePitch@Sketch2@cover_plate.SLDPRT", cover_group["dimensions"])
            self.assertIn("bolt_m6-1", cover_group["nearby_fastener_or_locator_components"])
            self.assertIn("thread_or_fit_spec", cover_group["missing_engineering_detail"])
            self.assertIn("tool_access_direction", cover_group["missing_engineering_detail"])
            gap_kinds = {g["kind"] for g in graph["evidence_gaps"]}
            self.assertIn("thread_or_fit_spec_missing", gap_kinds)
            self.assertIn("manufacturing_process_missing", gap_kinds)
            self.assertIn("tool_access_unproven", gap_kinds)
            pair_names = {(p["a"], p["b"]) for p in graph["spatial_evidence"]["near_or_overlap_pairs"]}
            self.assertTrue(any("dowel_pin-1" in pair for pair in pair_names))
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn("CAD evidence graph", text)
            self.assertIn("Manufacturing evidence", text)
            self.assertIn("Evidence gaps", text)

    def test_constraint_network_links_components_features_dimensions_and_gaps(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_json = root / "network.json"
            out_md = root / "network.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(self.make_report(root)),
                "--task", "????????????????????????????????",
                "--view", "manufacturing-holes",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            network = data["cad_evidence_graph"]["constraint_network"]
            node_ids = {n["id"] for n in network["nodes"]}
            self.assertIn("component:base_plate-1", node_ids)
            self.assertIn("component:dowel_pin-1", node_ids)
            self.assertIn("feature:ConcentricMate-dowel-base", node_ids)
            self.assertIn("dimension:BoltCirclePitch@Sketch2@cover_plate.SLDPRT", node_ids)
            edge_keys = {(e["source"], e["target"], e["relation"]) for e in network["edges"]}
            self.assertIn(("component:dowel_pin-1", "component:base_plate-1", "mate:concentric"), edge_keys)
            self.assertIn(("feature:ConcentricMate-dowel-base", "component:dowel_pin-1", "references_component"), edge_keys)
            self.assertIn(("feature:HoleWizard-M6-clearance", "component:cover_plate-1", "manufacturing_feature_on"), edge_keys)
            self.assertIn(("manufacturing_hole_group:cover_plate-1", "component:cover_plate-1", "manufacturing:hole_group_on"), edge_keys)
            self.assertIn(("manufacturing_hole_group:cover_plate-1", "component:bolt_m6-1", "manufacturing:nearby_fastener_or_locator"), edge_keys)
            self.assertIn(("dimension:BoltCirclePitch@Sketch2@cover_plate.SLDPRT", "feature:Sketch2", "drives_or_measures_feature"), edge_keys)
            self.assertTrue(any(e["relation"] in {"spatial:overlap", "spatial:near"} for e in network["edges"]))
            self.assertTrue(any(e["relation"] == "evidence_gap" and e["target"].startswith("gap:") for e in network["edges"]))
            summary = network["summary"]
            self.assertGreaterEqual(summary["component_nodes"], 5)
            self.assertGreaterEqual(summary["mate_edges"], 2)
            self.assertGreaterEqual(summary["manufacturing_edges"], 2)
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn("Constraint network", text)
            self.assertIn("mate:concentric", text)

    def test_model_understand_uses_mate_like_features_and_flags_one_mate_cloud(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = {
                "active_document": {
                    "title": "one_mate_cloud.SLDASM",
                    "path": "C:/machines/one_mate_cloud.SLDASM",
                    "type": "assembly",
                    "components": [
                        {"name2": "base-1", "path": "C:/machines/base.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [0, 0, 0, 0.1, 0.1, 0.01]},
                        {"name2": "ram-1", "path": "C:/machines/ram.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0.2, 0, 0, 0.3, 0.1, 0.01]},
                        {"name2": "link-1", "path": "C:/machines/link.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0.4, 0, 0, 0.5, 0.1, 0.01]},
                        {"name2": "pin-1", "path": "C:/machines/pin.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0.6, 0, 0, 0.7, 0.1, 0.01]},
                    ],
                    "features": [],
                    "mate_like_features": [
                        {"name": "shaper_distance", "type": "MateDistanceDim", "components": ["base-1", "ram-1"], "suppressed": False}
                    ],
                }
            }
            report_path = root / "one_mate_cloud.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            out_json = root / "one_mate_cloud_understanding.json"
            out_md = root / "one_mate_cloud_understanding.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(report_path),
                "--task", "装配体只有一个配合时判断是否可信",
                "--view", "assembly-constraints",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            graph = data["cad_evidence_graph"]
            mate = graph["mate_evidence"][0]
            self.assertEqual(mate["name"], "shaper_distance")
            self.assertEqual(mate["a"], "base-1")
            self.assertEqual(mate["b"], "ram-1")
            gap_kinds = {g["kind"] for g in graph["evidence_gaps"]}
            self.assertIn("constraint_network_underconnected", gap_kinds)
            self.assertIn("link-1", " ".join(g.get("objects", "") for g in graph["evidence_gaps"]))
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn("constraint_network_underconnected", text)

    def test_model_understand_prefers_explicit_mate_like_refs_over_sparse_feature_duplicate(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = {
                "active_document": {
                    "title": "duplicate_mate_ref.SLDASM",
                    "path": "C:/machines/duplicate_mate_ref.SLDASM",
                    "type": "assembly",
                    "components": [
                        {"name2": "base-1", "path": "C:/machines/base.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [0, 0, 0, 0.1, 0.1, 0.01]},
                        {"name2": "ram-1", "path": "C:/machines/ram.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0, 0, 0.01, 0.1, 0.1, 0.02]},
                    ],
                    "features": [
                        {"name": "coincident_base_ram", "type": "Mate", "entities": []}
                    ],
                    "mate_like_features": [
                        {"name": "coincident_base_ram", "type": "Mate", "components": ["base-1", "ram-1"], "suppressed": False}
                    ],
                }
            }
            report_path = root / "duplicate_mate_ref.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            out_json = root / "duplicate_mate_ref_understanding.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(report_path),
                "--task", "verify duplicate mate readback keeps explicit components",
                "--view", "assembly-constraints",
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            graph = json.loads(out_json.read_text(encoding="utf-8-sig"))["cad_evidence_graph"]
            self.assertEqual(len(graph["mate_evidence"]), 1)
            mate = graph["mate_evidence"][0]
            self.assertEqual((mate["a"], mate["b"]), ("base-1", "ram-1"))
            self.assertEqual(mate["source"], "mate_like_features")
            gap_kinds = {g["kind"] for g in graph["evidence_gaps"]}
            self.assertNotIn("mate_reference_partial", gap_kinds)
            self.assertNotIn("constraint_network_underconnected", gap_kinds)

    def test_two_component_single_mate_is_not_underconnected(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            report = {
                "active_document": {
                    "title": "two_component_single_mate.SLDASM",
                    "path": "C:/machines/two_component_single_mate.SLDASM",
                    "type": "assembly",
                    "components": [
                        {"name2": "base-1", "path": "C:/machines/base.SLDPRT", "suppressed": False, "hidden": False, "fixed": True, "bbox_m": [0, 0, 0, 0.1, 0.1, 0.01]},
                        {"name2": "ram-1", "path": "C:/machines/ram.SLDPRT", "suppressed": False, "hidden": False, "fixed": False, "bbox_m": [0, 0, 0.01, 0.1, 0.1, 0.02]},
                    ],
                    "mate_like_features": [
                        {"name": "base_ram_coincident", "type": "Mate", "components": ["base-1", "ram-1"], "suppressed": False}
                    ],
                }
            }
            report_path = root / "two_component_single_mate.json"
            report_path.write_text(json.dumps(report), encoding="utf-8")
            out_json = root / "two_component_single_mate_understanding.json"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(report_path),
                "--task", "verify two component assembly does not overstate underconnection",
                "--view", "assembly-constraints",
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            graph = json.loads(out_json.read_text(encoding="utf-8-sig"))["cad_evidence_graph"]
            gap_kinds = {g["kind"] for g in graph["evidence_gaps"]}
            self.assertNotIn("constraint_network_underconnected", gap_kinds)

    def test_decision_readiness_marks_supported_and_blocked_cad_tasks(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_json = root / "readiness.json"
            out_md = root / "readiness.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(self.make_report(root)),
                "--task", "?????????????????????????????????????????????????",
                "--view", "manufacturing-holes",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            readiness = data["decision_readiness"]
            by_task = {item["task"]: item for item in readiness}
            self.assertEqual(by_task["dimension_edit"]["status"], "needs_evidence")
            self.assertIn("backup", " ".join(by_task["dimension_edit"]["missing_evidence"]).lower())
            self.assertEqual(by_task["assembly_constraints"]["status"], "ready_for_review")
            self.assertEqual(by_task["interference_clearance"]["status"], "needs_live_check")
            self.assertTrue(any("interference" in q["tool"] for q in by_task["interference_clearance"]["recommended_next_queries"]))
            self.assertEqual(by_task["manufacturing_holes"]["status"], "needs_engineering_detail")
            self.assertIn("thread", " ".join(by_task["manufacturing_holes"]["missing_evidence"]).lower())
            text = out_md.read_text(encoding="utf-8-sig")
            self.assertIn("Decision readiness", text)
            self.assertIn("manufacturing_holes", text)

    def test_transform_evidence_exposes_component_origin_and_local_axes(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            out_json = root / "transform.json"
            out_md = root / "transform.md"
            proc = run_py(
                "tools/solidworks_codex/scripts/sw_model_understand.py",
                "--report", str(self.make_report(root)),
                "--task", "????????????????????????????",
                "--view", "spatial-assembly",
                "--out", str(out_md),
                "--json-out", str(out_json),
            )
            self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)
            data = json.loads(out_json.read_text(encoding="utf-8-sig"))
            transforms = data["cad_evidence_graph"]["transform_evidence"]
            by_name = {item["name"]: item for item in transforms["components"]}
            self.assertEqual(by_name["base_plate-1"]["origin_m"], [0.0, 0.0, 0.0])
            self.assertEqual(by_name["locator_block-1"]["origin_m"], [0.01, 0.02, 0.012])
            self.assertEqual(by_name["locator_block-1"]["local_axes"]["x"], [0.0, -1.0, 0.0])
            self.assertEqual(by_name["locator_block-1"]["local_axes"]["y"], [1.0, 0.0, 0.0])
            relations = transforms["relationships"]
            self.assertTrue(any(r["relation"] == "transform:axis_parallel" and r["axis_a"] == "z" and r["axis_b"] == "z" for r in relations))
            self.assertTrue(any(r["relation"] == "transform:axis_orthogonal" and r["axis_a"] == "x" and r["axis_b"] == "x" for r in relations))
            self.assertTrue(any(r["relation"] == "transform:origin_offset" and r["a"] == "base_plate-1" and r["b"] == "locator_block-1" for r in relations))
            network_edges = data["cad_evidence_graph"]["constraint_network"]["edges"]
            self.assertTrue(any(e["relation"] == "transform:axis_parallel" for e in network_edges))
            self.assertTrue(any(e["relation"] == "transform:origin_offset" for e in network_edges))
            self.assertIn("Transform evidence", out_md.read_text(encoding="utf-8-sig"))


if __name__ == "__main__":
    unittest.main()
