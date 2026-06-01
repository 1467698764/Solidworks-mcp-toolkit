"""Timestamped backup helper for SolidWorks source files.

Copies selected files into tools/solidworks_codex/backups/<timestamp>/ while preserving
relative names. This script never deletes or modifies source files.
"""
from __future__ import annotations

import argparse
import json
import shutil
from datetime import datetime
from pathlib import Path

ALLOWED_SUFFIXES = {".sldprt", ".sldasm", ".slddrw", ".SLDPRT", ".SLDASM", ".SLDDRW"}


def backup_file(src: Path, backup_root: Path) -> dict[str, str]:
    if not src.exists():
        raise FileNotFoundError(src)
    if not src.is_file():
        raise ValueError(f"not a file: {src}")
    if src.suffix not in ALLOWED_SUFFIXES:
        raise ValueError(f"refusing to back up unsupported file type {src.suffix}: {src}")
    dest = backup_root / src.name
    if dest.exists():
        stem = dest.stem
        suffix = dest.suffix
        i = 2
        while dest.exists():
            dest = backup_root / f"{stem}_{i}{suffix}"
            i += 1
    shutil.copy2(src, dest)
    return {"source": str(src.resolve()), "backup": str(dest.resolve())}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("files", nargs="+", help="SolidWorks files to back up")
    parser.add_argument("--out", default="tools/solidworks_codex/reports/backup.json")
    parser.add_argument("--backup-dir", default=None)
    args = parser.parse_args()

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = Path(args.backup_dir or f"tools/solidworks_codex/backups/{timestamp}")
    backup_root.mkdir(parents=True, exist_ok=True)

    result = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "backup_root": str(backup_root.resolve()),
        "files": [backup_file(Path(f), backup_root) for f in args.files],
    }
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
