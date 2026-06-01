"""Audit the release tree for generated artifacts and personal files."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

RULES: list[tuple[str, str]] = [
    ("reports", "tools/solidworks_codex/reports/"),
    ("backups", "tools/solidworks_codex/backups/"),
    ("exports", "tools/solidworks_codex/exports/"),
    ("logs", "tools/solidworks_codex/logs/"),
    ("generated_macros", "tools/solidworks_codex/macros/"),
    ("pycache", "__pycache__/"),
    ("personal_config", ".codex/config.toml"),
    ("personal_config", "c:/users/alphahui/.codex/config.toml"),
]

ALLOWED = {
    "tools/solidworks_codex/sandbox/report_before.json",
    "tools/solidworks_codex/sandbox/report_after.json",
}


def norm(path: str) -> str:
    return path.strip().replace("\\", "/").lower().lstrip("./")


def git_visible_files() -> list[str]:
    proc = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr or proc.stdout or "git ls-files failed")
    return [line for line in proc.stdout.splitlines() if line.strip()]


def file_list(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8-sig").splitlines() if line.strip()]


def classify(files: list[str]) -> tuple[dict[str, Any], list[dict[str, str]]]:
    checks: dict[str, Any] = {kind: {"ok": True, "matches": []} for kind, _ in RULES}
    violations: list[dict[str, str]] = []
    for original in files:
        n = norm(original)
        if n in ALLOWED:
            continue
        for kind, prefix in RULES:
            p = norm(prefix)
            matched = n.startswith(p) or p in n
            if kind == "generated_macros":
                matched = n.startswith(p) and n.endswith(".swp.vba")
            if matched:
                checks[kind]["ok"] = False
                checks[kind]["matches"].append(original)
                violations.append({"kind": kind, "path": original})
    return checks, violations


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/release_tree.json")
    parser.add_argument("--from-file", default="")
    args = parser.parse_args()

    files = file_list(Path(args.from_file)) if args.from_file else git_visible_files()
    checks, violations = classify(files)
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not violations,
        "files_checked": len(files),
        "checks": checks,
        "violations": violations,
    }
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out), "violations": len(violations)}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
