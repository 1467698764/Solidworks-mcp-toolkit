"""Create a compact handoff bundle for the next SolidWorks Codex iteration."""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "tools" / "solidworks_codex" / "scripts"


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def display_path(path_or_text: str | Path) -> str:
    p = Path(path_or_text)
    try:
        return str(p.resolve().relative_to(ROOT)).replace("\\", "/")
    except Exception:
        text = str(path_or_text).replace("\\", "/")
        return text


def sanitize_text(text: str) -> str:
    import re

    text = text.replace(str(ROOT), "<repo>")
    text = text.replace(str(ROOT).replace("\\", "\\\\"), "<repo>")
    text = re.sub(r"C:\\\\Users\\\\[^\\\\]+\\\\AppData\\\\Local\\\\Temp\\\\[^\\\\\s\"`]+", "<generated-demo-path>", text)
    text = re.sub(r"C:\\Users\\[^\\]+\\AppData\\Local\\Temp\\[^\\\s\"`]+", "<generated-demo-path>", text)
    text = re.sub(r"C:\\\\Users\\\\[^\\\\]+\\\\AppData\\\\Local\\\\Programs\\\\Python\\\\[^\\\\]+\\\\python\.exe", "<python>", text)
    text = re.sub(r"C:\\Users\\[^\\]+\\AppData\\Local\\Programs\\Python\\[^\\]+\\python\.exe", "<python>", text)
    return text


def sanitize_outputs(out_dir: Path) -> None:
    for path in out_dir.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in {".md", ".json", ".jsonl"}:
            continue
        path.write_text(sanitize_text(path.read_text(encoding="utf-8-sig", errors="replace")), encoding="utf-8")


def run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=False)
    return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def doc_from_report(report_path: Path) -> dict[str, Any]:
    report = read_json(report_path) or {}
    doc = report.get("active_document") if isinstance(report, dict) else {}
    return doc if isinstance(doc, dict) else {}


def render_readme(manifest: dict[str, Any], worklog_text: str) -> str:
    lines = ["# SolidWorks Codex Handoff Bundle", ""]
    lines += [
        f"- Created: `{manifest['timestamp']}`",
        f"- Focus: `{manifest['focus'] or '<none>'}`",
        f"- Document: `{manifest['document'].get('title')}`",
        f"- Source report: `{display_path(manifest['source_report'])}`",
        "",
        "## Principle",
        "Do not blindly replay templates: read `context.md`, `worklog.md`, and the source inspect JSON before choosing the next step for the current model.",
        "",
        "## Files",
    ]
    for name, rel in manifest["files"].items():
        lines.append(f"- {name}: `{rel}`")
    lines += ["", "## Suggested first actions"]
    lines += [
        "1. Read `context.md` for inventory, risks, anchors, and suggested commands.",
        "2. Read `worklog.md` for prior decisions, assumptions, verification, failures, and next steps.",
        "3. If making any write, run backup first and change one variable at a time.",
        "4. Rebuild, inspect, compare, and append worklog events after meaningful decisions.",
        "",
        "## Recent worklog excerpt",
    ]
    excerpt = "\n".join(worklog_text.splitlines()[:80]).strip()
    lines.append(excerpt if excerpt else "- No worklog was provided.")
    lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", required=True)
    parser.add_argument("--worklog", default="tools/solidworks_codex/reports/worklog.jsonl")
    parser.add_argument("--focus", default="")
    parser.add_argument("--out-dir", default="")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out_dir = resolve(args.out_dir) if args.out_dir else ROOT / "tools" / "solidworks_codex" / "reports" / "handoff" / stamp
    out_dir.mkdir(parents=True, exist_ok=True)

    report_path = resolve(args.report)
    copied_report = out_dir / "inspect.json"
    shutil.copyfile(report_path, copied_report)

    context_md = out_dir / "context.md"
    context_json = out_dir / "context.json"
    context_cmd = [
        sys.executable,
        str(SCRIPTS / "sw_report_context.py"),
        "--report", str(copied_report),
        "--focus", args.focus,
        "--out", str(context_md),
        "--json-out", str(context_json),
    ]
    context_result = run(context_cmd)

    worklog_src = resolve(args.worklog)
    worklog_jsonl = out_dir / "worklog.jsonl"
    worklog_md = out_dir / "worklog.md"
    if worklog_src.exists():
        shutil.copyfile(worklog_src, worklog_jsonl)
        worklog_events = []
        for line in worklog_jsonl.read_text(encoding="utf-8-sig").splitlines():
            if line.strip():
                try:
                    worklog_events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        # Reuse worklog renderer without appending a new event by importing through subprocess-free local code.
        import importlib.util

        spec = importlib.util.spec_from_file_location("sw_worklog", SCRIPTS / "sw_worklog.py")
        mod = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(mod)
        worklog_md.write_text(mod.markdown(worklog_events, worklog_jsonl), encoding="utf-8")
    else:
        worklog_jsonl.write_text("", encoding="utf-8")
        worklog_md.write_text("# SolidWorks Codex Worklog\n\n- No worklog was provided.\n", encoding="utf-8")

    context_data = read_json(context_json) or {}
    manifest = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": context_result["returncode"] == 0,
        "focus": args.focus,
        "source_report": display_path(report_path),
        "document": doc_from_report(report_path),
        "files": {
            "README.md": "handoff instructions",
            "inspect.json": "copied source inspect report",
            "context.md": "human-readable context pack",
            "context.json": "machine-readable context pack",
            "worklog.jsonl": "copied durable event log",
            "worklog.md": "human-readable worklog summary",
        },
        "suggested_inputs": [
            "audit_latest.json",
            "tools/solidworks_codex/reports/audit_latest.json",
            "tools/solidworks_codex/reports/final_readiness.json",
            "latest session-snapshot directory",
        ],
        "context_counts": context_data.get("inventory") if isinstance(context_data, dict) else None,
        "commands": [context_result],
    }
    worklog_text = worklog_md.read_text(encoding="utf-8-sig")
    (out_dir / "README.md").write_text(render_readme(manifest, worklog_text), encoding="utf-8")
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    sanitize_outputs(out_dir)
    print(json.dumps({"ok": manifest["ok"], "out_dir": str(out_dir), "manifest": str(out_dir / "manifest.json")}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if manifest["ok"] else 1)


if __name__ == "__main__":
    main()
