"""Generate reviewable preselect VBA macro drafts from a mate group plan."""
from __future__ import annotations

import argparse
import json
import math
import re
from datetime import datetime
from pathlib import Path
from typing import Any

from sw_mate_macro import MATE_TYPES, macro


SUPPORTED_TYPES = {"coincident", "concentric", "tangent", "distance", "limit_distance", "angle", "limit_angle", "parallel", "perpendicular"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8-sig"))


def safe_name(text: str) -> str:
    name = re.sub(r"[^A-Za-z0-9_.]+", "_", text).strip("_")
    return name or "mate"


def expected_mate_name(group_id: str, index: int, mate_type: str) -> str:
    return f"MG_{safe_name(group_id)}_{index:02d}_{safe_name(mate_type)}"


def angle_degrees(mate: dict[str, Any], degree_key: str, radian_key: str, default: float | None = None) -> float | None:
    raw_deg = mate.get(degree_key)
    if raw_deg not in (None, ""):
        return float(raw_deg)
    raw_rad = mate.get(radian_key)
    if raw_rad not in (None, ""):
        return math.degrees(float(raw_rad))
    return default


def annotated_macro(group: dict[str, Any], mate: dict[str, Any], mate_name: str) -> str:
    mate_type = str(mate.get("type", "")).casefold()
    base = macro(
        mate_type,
        float(mate.get("distance_m", 0.0) or 0.0),
        float(angle_degrees(mate, "angle_deg", "angle_rad", 0.0) or 0.0),
        bool(mate.get("flip", False)),
        float(mate["distance_min_m"]) if mate.get("distance_min_m") not in (None, "") else None,
        float(mate["distance_max_m"]) if mate.get("distance_max_m") not in (None, "") else None,
        angle_degrees(mate, "angle_min_deg", "angle_min_rad"),
        angle_degrees(mate, "angle_max_deg", "angle_max_rad"),
    )
    base = base.replace(
        "    Part.ForceRebuild3 False",
        f'    If Not MateFeature Is Nothing Then MateFeature.Name = "{mate_name}"\n    Part.ForceRebuild3 False',
    )
    header = [
        "' Mate group macro draft.",
        f"' Group: {group.get('group_id')}",
        f"' Expected mate name: {mate_name}",
        f"' Components: {', '.join(str(c) for c in group.get('components', []))}",
        f"' Selection intent: {mate.get('selection_intent', '')}",
        "' Review, preselect exactly two live SolidWorks entities, run, rebuild, then inspect.",
        "",
    ]
    return "\n".join(header) + base


def build_macros(plan: dict[str, Any], *, out_dir: Path) -> dict[str, Any]:
    macros: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    execution_actions: list[dict[str, Any]] = []
    for group in plan.get("mate_groups", []):
        group_id = str(group.get("group_id", "group"))
        for action in group.get("execution_actions", []) or []:
            if isinstance(action, dict):
                copied = dict(action)
                copied.setdefault("group_id", group_id)
                execution_actions.append(copied)
        mates = group.get("suggested_mates") or []
        if not mates:
            skipped.append({"group_id": group_id, "reason": "no_suggested_mates"})
            continue
        for index, mate in enumerate(mates, start=1):
            mate_type = str(mate.get("type", "")).casefold()
            if mate_type not in SUPPORTED_TYPES or mate_type not in MATE_TYPES:
                skipped.append({"group_id": group_id, "mate_type": mate_type, "reason": "unsupported_mate_type"})
                continue
            mate_name = expected_mate_name(group_id, index, mate_type)
            path = out_dir / f"{safe_name(group_id)}_{index:02d}_{mate_type}.swp.vba"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(annotated_macro(group, mate, mate_name), encoding="utf-8")
            macros.append({
                "group_id": group_id,
                "mate_type": mate_type,
                "expected_mate_name": mate_name,
                "macro": str(path.resolve()),
                "components": group.get("components", []),
                "selection_intent": mate.get("selection_intent", ""),
                "selection_selectors": mate.get("selection_selectors", []),
                "distance_m": float(mate.get("distance_m", 0.0) or 0.0),
                "distance_min_m": float(mate["distance_min_m"]) if mate.get("distance_min_m") not in (None, "") else None,
                "distance_max_m": float(mate["distance_max_m"]) if mate.get("distance_max_m") not in (None, "") else None,
                "angle_deg": float(angle_degrees(mate, "angle_deg", "angle_rad", 0.0) or 0.0),
                "angle_rad": float(mate.get("angle_rad", 0.0) or 0.0),
                "angle_min_deg": angle_degrees(mate, "angle_min_deg", "angle_min_rad"),
                "angle_max_deg": angle_degrees(mate, "angle_max_deg", "angle_max_rad"),
                "angle_min_rad": float(mate["angle_min_rad"]) if mate.get("angle_min_rad") not in (None, "") else None,
                "angle_max_rad": float(mate["angle_max_rad"]) if mate.get("angle_max_rad") not in (None, "") else None,
                "flip": bool(mate.get("flip", False)),
                "execution_actions": group.get("execution_actions", []),
                "verification": group.get("verification", []),
            })
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "mode": "reviewable_mate_group_macros",
        "ok": True,
        "document": plan.get("document", {}),
        "execution_actions": execution_actions,
        "macros": macros,
        "skipped": skipped,
        "preselect_required": True,
        "review_required": True,
        "operator_notes": [
            "review_before_running",
            "preselect_exactly_two_live_entities_for_each_macro",
            "apply_one_macro_then_rebuild_and_inspect",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate reviewable preselect VBA macro drafts from a mate group plan")
    parser.add_argument("--mate-group-plan", required=True)
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--manifest", required=True)
    args = parser.parse_args()

    result = build_macros(load_json(Path(args.mate_group_plan)), out_dir=Path(args.out_dir))
    manifest = Path(args.manifest)
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": True, "macro_count": len(result["macros"]), "manifest": str(manifest)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
