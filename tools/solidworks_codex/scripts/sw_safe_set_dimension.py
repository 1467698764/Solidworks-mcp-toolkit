"""Run a guarded one-dimension edit pipeline.

The command intentionally composes existing narrow tools instead of embedding CAD logic:
backup -> inspect before -> set one dimension -> rebuild -> inspect after -> compare -> change-verify.
It stops on the first failed step and records enough artifacts to replay or roll back.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SWCTL = ROOT / "tools" / "solidworks_codex" / "swctl.ps1"


def resolve(path: str | Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def command_prefix(swctl: str) -> list[str]:
    path = Path(swctl)
    if path.suffix.lower() == ".ps1":
        return ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(path)]
    if path.suffix.lower() == ".py":
        return [sys.executable, str(path)]
    return [str(path)]


def run_step(name: str, args: list[str], swctl: str) -> dict[str, Any]:
    cmd = command_prefix(swctl) + args
    proc = subprocess.run(
        cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "name": name,
        "command": cmd,
        "returncode": proc.returncode,
        "ok": proc.returncode == 0,
        "stdout_tail": proc.stdout[-4000:],
        "stderr_tail": proc.stderr[-4000:],
    }


def write_report(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def guarded_pipeline(args: argparse.Namespace) -> dict[str, Any]:
    out_dir = resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    artifacts = {
        "backup": out_dir / "01_backup.json",
        "before": out_dir / "02_inspect_before.json",
        "set_dimension": out_dir / "03_set_dimension.json",
        "rebuild": out_dir / "04_rebuild.json",
        "after": out_dir / "05_inspect_after.json",
        "delta_md": out_dir / "06_delta.md",
        "delta_json": out_dir / "06_delta.json",
        "verify": out_dir / "07_change_verify.json",
    }

    model = str(resolve(args.model))
    steps_spec: list[tuple[str, list[str]]] = [
        ("backup", ["backup", "-Files", model, "-Out", str(artifacts["backup"])]),
        ("inspect_before", ["inspect", "-Model", model, "-Out", str(artifacts["before"])]),
        ("set_dimension", ["set-dimension", "-Model", model, "-Dimension", args.dimension, "-ValueM", str(args.value_m), "-Out", str(artifacts["set_dimension"])]),
        ("rebuild", ["rebuild", "-Model", model, "-Out", str(artifacts["rebuild"])]),
        ("inspect_after", ["inspect", "-Model", model, "-Out", str(artifacts["after"])]),
        ("compare", ["compare", "-Before", str(artifacts["before"]), "-After", str(artifacts["after"]), "-Out", str(artifacts["delta_md"]), "-JsonOut", str(artifacts["delta_json"])]),
        ("change_verify", ["change-verify", "-Report", str(artifacts["delta_json"]), "-AllowDimension", args.dimension, "-RequireAllowedChange", "-Out", str(artifacts["verify"])]),
    ]

    if args.save:
        # Saving is still guarded, but never implicit. Keep it on the actual mutation/rebuild commands only.
        steps_spec[2][1].append("-Save")
        steps_spec[3][1].append("-Save")

    steps: list[dict[str, Any]] = []
    failed_step: str | None = None
    for name, step_args in steps_spec:
        result = run_step(name, step_args, args.swctl)
        steps.append(result)
        if not result["ok"]:
            failed_step = name
            break

    ok = failed_step is None
    rollback = f"powershell.exe -NoProfile -ExecutionPolicy Bypass -File {DEFAULT_SWCTL} restore-backup -Report {artifacts['backup']} -Apply"
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "failed_step": failed_step,
        "model": model,
        "dimension": args.dimension,
        "requested_system_value_m": args.value_m,
        "saved": bool(args.save),
        "artifacts": {k: str(v) for k, v in artifacts.items()},
        "steps": steps,
        "rollback_command": rollback,
        "next_action": "review change_verify and save/export if acceptable" if ok and not args.save else "review artifacts before continuing",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, help="SolidWorks model file to guard and edit.")
    parser.add_argument("--dimension", required=True, help="Full SolidWorks dimension/parameter name.")
    parser.add_argument("--value-m", required=True, type=float, help="New SystemValue in meters.")
    parser.add_argument("--save", action="store_true", help="Save during set/rebuild. Default leaves save decisions explicit.")
    parser.add_argument("--out-dir", default="tools/solidworks_codex/reports/safe_set_dimension")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/safe_set_dimension.json")
    parser.add_argument("--swctl", default=str(DEFAULT_SWCTL), help=argparse.SUPPRESS)
    args = parser.parse_args()

    result = guarded_pipeline(args)
    out = resolve(args.out)
    write_report(out, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    raise SystemExit(0 if result["ok"] else 1)


if __name__ == "__main__":
    main()
