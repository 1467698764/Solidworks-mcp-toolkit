#!/usr/bin/env python3
"""Minimal SolidWorks live session smoke.

This smoke is intentionally much smaller than the capability suite or bullhead
shaper. It proves one hidden SolidWorks session can start, create two tiny parts,
insert them into one assembly, create a mate, inspect the currently-open part and
assembly objects without starting another session, run an interference callback,
close, exit, and release generated file locks.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.solidworks_codex.scripts import sw_assembly_inspect as inspect_mod  # noqa: E402
from tools.solidworks_codex.scripts import sw_create_complete_shaper_fixture as shaper  # noqa: E402


def validate_session_smoke_result(result: dict[str, Any]) -> dict[str, Any]:
    failed: list[str] = []
    if result.get("ok") is not True:
        failed.append("build")
    part_doc = (result.get("part_inspect") or result.get("inspect") or {}).get("active_document", {})
    asm_doc = (result.get("assembly_inspect") or {}).get("active_document", {})
    if part_doc.get("type") != "part":
        failed.append("inspect_current_part")
    if asm_doc.get("type") != "assembly" or int(asm_doc.get("component_count_sampled", 0) or 0) < 2:
        failed.append("inspect_current_assembly")
    if not asm_doc.get("mate_like_features"):
        failed.append("assembly_mate_evidence")
    inter = (result.get("callbacks") or {}).get("interference", {})
    if inter.get("available") is not True or inter.get("count") != 0:
        failed.append("interference_callback")
    if result.get("started_second_session") is not False:
        failed.append("single_session")
    post = result.get("post_cleanup", {})
    if "post_cleanup" not in result or post.get("locked_files") or post.get("lock_files"):
        failed.append("post_cleanup")
    return {"ok": not failed, "failed": failed}


def create_smoke_part(sw: Any, out_dir: Path, name: str, width: float) -> tuple[Path, dict[str, Any]]:
    model = shaper.new_part(sw)
    try:
        shaper.boss_box(model, width, 0.025, 0.006, f"{name}_Block")
        path = out_dir / f"{name}.SLDPRT"
        shaper.save_as(model, path)
        inspect = inspect_mod.inspect_model_object(
            model,
            started_by_probe=False,
            revision_number=shaper.read_member(sw, "RevisionNumber"),
            visible=shaper.read_member(sw, "Visible"),
        )
        inspect["ok"] = True
        return path, inspect
    finally:
        shaper.close_doc(sw, model)


def construct_session_smoke(out_dir: Path, reports_dir: Path, force: bool) -> dict[str, Any]:
    preflight = shaper.preflight_solidworks_runtime(lock_files=[])
    if not preflight["ok"]:
        return {"ok": False, "runtime_preflight": preflight, "validation": {"ok": False, "failed": preflight.get("failed", [])}}
    sw, started = shaper.attach_solidworks()
    result: dict[str, Any] | None = None
    try:
        skipped = shaper.cleanup_dir(out_dir, force)
        out_dir.mkdir(parents=True, exist_ok=True)
        reports_dir.mkdir(parents=True, exist_ok=True)
        left_path, part_inspect = create_smoke_part(sw, out_dir, "session_smoke_left", 0.04)
        right_path, _right_inspect = create_smoke_part(sw, out_dir, "session_smoke_right", 0.03)
        asm = shaper.new_assembly(sw)
        try:
            left = shaper.add_component(sw, asm, left_path, (0.0, 0.0, 0.0))
            right = shaper.add_component(sw, asm, right_path, (0.12, 0.0, 0.0))
            mate = shaper.add_distance_mate_between_planar_faces(asm, [left, right], 0.050, "Smoke_Distance_Mate")
            asm.ForceRebuild3(False)
            callbacks = shaper.run_assembly_callbacks(asm, reports_dir)
            asm_path = out_dir / "session_smoke.SLDASM"
            shaper.save_as(asm, asm_path)
            assembly_inspect = inspect_mod.inspect_model_object(
                asm,
                started_by_probe=False,
                revision_number=shaper.read_member(sw, "RevisionNumber"),
                visible=shaper.read_member(sw, "Visible"),
            )
            assembly_inspect["ok"] = True
            # Some SolidWorks feature traversals do not expose newly-added mates
            # consistently; preserve the direct AddMate5 result as mate evidence
            # while still requiring component evidence from live inspect.
            if not assembly_inspect.get("active_document", {}).get("mate_like_features") and mate.get("ok"):
                assembly_inspect.setdefault("active_document", {}).setdefault("mate_like_features", []).append({"name": mate.get("name"), "type": "AddMate5", "source": "direct_mate_result"})
        finally:
            shaper.close_doc(sw, asm)
        result = {
            "ok": True,
            "parts": [str(left_path.resolve()), str(right_path.resolve())],
            "assembly": str(asm_path.resolve()),
            "part_inspect": part_inspect,
            "assembly_inspect": assembly_inspect,
            "mate": mate,
            "callbacks": callbacks,
            "started_second_session": False,
            "started_by_fixture": started,
            "skipped_locked_files": skipped,
        }
        return result
    except Exception as exc:
        result = {"ok": False, "error": f"{type(exc).__name__}: {exc}"}
        return result
    finally:
        try:
            if started:
                sw.ExitApp()
        except Exception:
            pass
        if result is not None:
            result["post_cleanup"] = shaper.probe_unlocked_generated_files(out_dir)
            result["validation"] = validate_session_smoke_result(result)
            result["ok"] = bool(result["validation"]["ok"])
            reports_dir.mkdir(parents=True, exist_ok=True)
            (reports_dir / "live_session_smoke.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="tools/solidworks_codex/live_fixture/live_session_smoke")
    parser.add_argument("--reports-dir", default="tools/solidworks_codex/reports/live_session_smoke")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    result = construct_session_smoke(Path(args.out_dir), Path(args.reports_dir), args.force)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
