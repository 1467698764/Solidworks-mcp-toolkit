"""Guard public-facing copy against rank boasting and overclaiming."""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
PUBLIC_PATTERNS = ["*.md", "*.toml", "*.yml", "*.yaml", "*.ps1", "*.py", "*.cjs"]
EXCLUDE_PARTS = {"__pycache__", "reports", "backups", "logs", "exports", ".git", "node_modules", "tests", "tools\\mcp-solidworks-ts"}
MOJIBAKE_PATTERNS = [
    re.compile("\u6d93"),
    re.compile("\u9225"),
    re.compile("\u9241"),
    re.compile("\u9242"),
    re.compile("\u951b"),
    re.compile("\u9286"),
    re.compile("\u8b72"),
    re.compile("\u59af"),
    re.compile("\u6f98"),
    re.compile("\ufffd"),
]

FORBIDDEN = [
    re.compile(r"\btop\s*3\b", re.I),
    re.compile(r"\btop3\b", re.I),
    re.compile(r"\brobot[- ]joint\b", re.I),
    re.compile(r"\bjoint-baseline\b", re.I),
    re.compile(r"\bjoint\.SLDASM\b", re.I),
    re.compile(r"\bexports[/\\]joint\.step\b", re.I),
    re.compile(r"\bC:[/\\]robot[/\\]", re.I),
    re.compile(r"\bbearing\s+encoder\s+flange\b", re.I),
    re.compile("\u6bd5\u8bbe"),
    re.compile("\u6bd5\u4e1a"),
    re.compile("\u673a\u5668\u4eba\u5173\u8282"),
    re.compile("\u4f18\u5316\u4e00\u4e0b\u6574\u4e2a\u5173\u8282"),
    re.compile("\u81f3\u5c11\u524d\u4e09"),
    re.compile("\u540c\u7c7b\u524d\u4e09"),
    re.compile("\u6392\u7b2c[\u4e00\u4e8c\u4e09123]"),
    *MOJIBAKE_PATTERNS,
]


def public_files() -> list[Path]:
    files: list[Path] = []
    for pattern in PUBLIC_PATTERNS:
        for p in ROOT.rglob(pattern):
            if any(part in EXCLUDE_PARTS for part in p.parts) or any(str(p).replace("/", "\\").endswith(ex) or ex in str(p).replace("/", "\\") for ex in EXCLUDE_PARTS):
                continue
            if p.suffix == ".pyc":
                continue
            files.append(p)
    return sorted(set(files))


def scan() -> dict[str, Any]:
    violations = []
    for path in public_files():
        rel = str(path.relative_to(ROOT))
        if rel == "tools\\solidworks_codex\\scripts\\sw_public_copy_guard.py":
            continue
        try:
            text = path.read_text(encoding="utf-8-sig")
        except UnicodeDecodeError:
            continue
        for i, line in enumerate(text.splitlines(), start=1):
            for pattern in FORBIDDEN:
                if pattern.search(line):
                    violations.append({"path": str(path.relative_to(ROOT)), "line": i, "text": line.strip(), "pattern": pattern.pattern.encode("unicode_escape").decode("ascii")})
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": not violations,
        "files_checked": len(public_files()),
        "violations": violations,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/public_copy_guard.json")
    args = parser.parse_args()
    report = scan()
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": report["ok"], "out": str(out), "files_checked": report["files_checked"], "violations": len(report["violations"])}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["ok"] else 1)


if __name__ == "__main__":
    main()
