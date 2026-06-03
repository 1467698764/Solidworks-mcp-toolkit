"""Run the offline assembly review chain from a single inspect report.

The pipeline is read-only: it writes review artifacts derived from an inspect
JSON report and does not open or mutate SolidWorks files.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from sw_assembly_diagnose import diagnose
from sw_assembly_repair_plan import build_plan as build_repair_plan
from sw_assembly_repair_plan import markdown as repair_markdown
from sw_interface_index import build_index
from sw_mate_group_plan import build_plan as build_mate_group_plan
from sw_mate_group_plan import markdown as mate_group_markdown


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def build_pipeline(
    report: dict[str, Any],
    *,
    out_dir: Path,
    near_tolerance_m: float,
    standard_part_regex: str,
) -> dict[str, Any]:
    diagnosis = diagnose(report, near_tolerance_m=near_tolerance_m, standard_part_regex=standard_part_regex)
    interface_index = build_index(report, near_tolerance_m=near_tolerance_m, standard_part_regex=standard_part_regex)
    repair_plan = build_repair_plan(diagnosis)
    mate_group_plan = build_mate_group_plan(repair_plan, interface_index)

    paths = {
        "diagnosis": out_dir / "assembly_diagnosis.json",
        "interface_index": out_dir / "interface_index.json",
        "repair_plan": out_dir / "assembly_repair_plan.json",
        "repair_plan_md": out_dir / "assembly_repair_plan.md",
        "mate_group_plan": out_dir / "mate_group_plan.json",
        "mate_group_plan_md": out_dir / "mate_group_plan.md",
    }
    write_json(paths["diagnosis"], diagnosis)
    write_json(paths["interface_index"], interface_index)
    write_json(paths["repair_plan"], repair_plan)
    write_text(paths["repair_plan_md"], repair_markdown(repair_plan))
    write_json(paths["mate_group_plan"], mate_group_plan)
    write_text(paths["mate_group_plan_md"], mate_group_markdown(mate_group_plan))

    manifest = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": True,
        "mode": "read_only_assembly_review_pipeline",
        "document": diagnosis.get("document") or interface_index.get("document") or {},
        "artifacts": {key: rel(path, out_dir) for key, path in paths.items()},
        "counts": {
            "components": diagnosis.get("inventory", {}).get("component_count", 0),
            "bad_mates": len(diagnosis.get("mates", {}).get("bad_mates", [])),
            "repair_actions": len(repair_plan.get("actions", [])),
            "mate_groups": len(mate_group_plan.get("mate_groups", [])),
            "interface_candidates": len(interface_index.get("interfaces", [])),
        },
        "operator_notes": [
            "read_only_artifacts",
            "use_mate_group_plan_for_live_selection_and_groupwise_validation",
            "rerun_pipeline_after_each_live_repair_checkpoint",
        ],
    }
    write_json(out_dir / "manifest.json", manifest)
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the read-only assembly review pipeline from an inspect JSON report")
    parser.add_argument("--report", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--near-tolerance-m", type=float, default=0.002)
    parser.add_argument("--standard-part-regex", default=r"bolt|washer|nut|screw|pin|bearing|key|retaining|oil")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    manifest = build_pipeline(
        load_json(Path(args.report)),
        out_dir=out_dir,
        near_tolerance_m=args.near_tolerance_m,
        standard_part_regex=args.standard_part_regex,
    )
    print(json.dumps({"ok": True, "out": str(out_dir / "manifest.json"), "counts": manifest["counts"]}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
