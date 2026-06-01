"""Generate a 5-minute offline demo bundle for GitHub readers."""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "tools" / "solidworks_codex" / "scripts"
FIXTURE = ROOT / "tools" / "solidworks_codex" / "sandbox" / "report_after.json"


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
    return {"cmd": sanitize_cmd(cmd), "returncode": proc.returncode, "stdout": sanitize_text(proc.stdout), "stderr": sanitize_text(proc.stderr)}


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        return "<generated-demo-path>"


def sanitize_text(text: str) -> str:
    import re

    root_plain = str(ROOT)
    root_json = root_plain.replace("\\", "\\\\")
    text = text.replace(root_plain, "<repo>")
    text = text.replace(root_json, "<repo>")
    text = re.sub(r"C:\\\\Users\\\\[^\\\\]+\\\\AppData\\\\Local\\\\Temp\\\\[^\\\\\s\"`]+", "<generated-demo-path>", text)
    text = re.sub(r"C:\\Users\\[^\\]+\\AppData\\Local\\Temp\\[^\\\s\"`]+", "<generated-demo-path>", text)
    text = re.sub(r"C:\\\\Users\\\\[^\\\\]+\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\[^\\\\]+\\\\python\.exe", "<python>", text)
    text = re.sub(r"C:\\Users\\[^\\]+\\AppData\\Local\\Programs\\Python\\[^\\]+\\python\.exe", "<python>", text)
    return text


def sanitize_cmd(cmd: list[str]) -> list[str]:
    sanitized: list[str] = []
    for i, part in enumerate(cmd):
        p = Path(part)
        if i == 0:
            sanitized.append("<python>")
        elif p.is_absolute():
            sanitized.append(display_path(p))
        else:
            sanitized.append(part)
    return sanitized


def readme(files: list[str]) -> str:
    return "\n".join([
        "# SolidWorks Codex 5-minute offline demo",
        "",
        "This demo proves the practical differentiator without requiring SolidWorks to be open:",
        "Codex can inspect a saved report, build context, record decisions, package handoff, and list tools.",
        "",
        "## What to read",
        "",
        "- `tool_catalog.md`: all MCP tools grouped by workflow.",
        "- `context.md`: report-context output with anchors and risks.",
        "- `worklog.md`: durable decision/verification history.",
        "- `handoff/README.md`: what a future Codex turn should read first.",
        "",
        "## Why this matters",
        "",
        "A raw API wrapper can expose many calls. This project focuses on safe, multi-turn SolidWorks work:",
        "`report-context`, `worklog`, `handoff-bundle`, and `tool-catalog` keep the next step grounded in evidence.",
        "",
        "## Files",
        "",
        *[f"- `{f}`" for f in files],
        "",
    ])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="docs/demo/offline")
    args = parser.parse_args()
    out_dir = resolve(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    commands = []
    commands.append(run([sys.executable, str(SCRIPTS / "sw_tool_catalog.py"), "--out", str(out_dir / "tool_catalog.md"), "--json-out", str(out_dir / "tool_catalog.json")]))
    commands.append(run([sys.executable, str(SCRIPTS / "sw_report_context.py"), "--report", str(FIXTURE), "--focus", "current model evidence, constraints, clearance, and manufacturing gaps", "--out", str(out_dir / "context.md"), "--json-out", str(out_dir / "context.json")]))
    commands.append(run([sys.executable, str(SCRIPTS / "sw_worklog.py"), "--log", str(out_dir / "worklog.jsonl"), "--summary-out", str(out_dir / "worklog.md"), "--session", "offline-demo", "--event", "decision", "--message", "Use report-context and tool-catalog before any template or write operation", "--artifact", "context.md", "--next", "Generate handoff bundle"]))
    commands.append(run([sys.executable, str(SCRIPTS / "sw_handoff_bundle.py"), "--report", str(FIXTURE), "--worklog", str(out_dir / "worklog.jsonl"), "--focus", "current model evidence, constraints, clearance, and manufacturing gaps", "--out-dir", str(out_dir / "handoff")]))

    files = [
        "README.md",
        "tool_catalog.md",
        "tool_catalog.json",
        "context.md",
        "context.json",
        "worklog.jsonl",
        "worklog.md",
        "handoff/README.md",
        "handoff/manifest.json",
    ]
    ok = all(c["returncode"] == 0 for c in commands) and all((out_dir / f).exists() for f in files if f != "README.md")
    (out_dir / "README.md").write_text(readme(files), encoding="utf-8")
    manifest = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "out_dir": display_path(out_dir),
        "files": files,
        "commands": commands,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sanitize_outputs(out_dir)
    print(json.dumps({"ok": ok, "out_dir": str(out_dir), "files": files}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


def sanitize_outputs(out_dir: Path) -> None:
    for path in out_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".jsonl"}:
            continue
        path.write_text(sanitize_text(path.read_text(encoding="utf-8-sig", errors="replace")), encoding="utf-8")


if __name__ == "__main__":
    main()
