"""Append a durable SolidWorks Codex worklog event and regenerate a summary.

The worklog is deliberately generic: decisions, assumptions, checks, failures,
manual actions, and next steps. It helps later Codex turns understand *why* a
path was chosen instead of blindly replaying templates.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
EVENTS = {"note", "decision", "assumption", "verification", "failure", "manual_action", "next_step"}


def resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else ROOT / p


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


def load_events(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    events = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        try:
            item = json.loads(line)
            if isinstance(item, dict):
                events.append(item)
        except json.JSONDecodeError:
            events.append({"timestamp": "", "event": "failure", "session": "", "message": f"Unparseable log line: {line[:120]}", "artifacts": [], "next": ""})
    return events


def append_event(path: Path, event: dict[str, Any]) -> list[dict[str, Any]]:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(event, ensure_ascii=False, sort_keys=True) + "\n")
    return load_events(path)


def markdown(events: list[dict[str, Any]], log_path: Path) -> str:
    lines = ["# SolidWorks Codex Worklog", ""]
    lines += [f"- Log: `{display_path(log_path)}`", f"- Events: `{len(events)}`", ""]
    if not events:
        lines.append("- No events yet.")
        return "\n".join(lines) + "\n"

    by_session: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        by_session.setdefault(str(e.get("session") or "session"), []).append(e)

    for session, items in by_session.items():
        lines += [f"## Session `{session}`", ""]
        for e in items:
            lines.append(f"### {e.get('timestamp', '')} `{e.get('event', 'note')}`")
            lines.append("")
            lines.append(str(e.get("message") or ""))
            artifacts = e.get("artifacts") or []
            if artifacts:
                lines.append("")
                lines.append("Artifacts:")
                for a in artifacts:
                    lines.append(f"- `{a}`")
            if e.get("next"):
                lines.append("")
                lines.append(f"Next: {e.get('next')}")
            lines.append("")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", default="tools/solidworks_codex/reports/worklog.jsonl")
    parser.add_argument("--summary-out", default="tools/solidworks_codex/reports/worklog.md")
    parser.add_argument("--session", default="session")
    parser.add_argument("--event", choices=sorted(EVENTS), default="note")
    parser.add_argument("--message", required=True)
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--next", default="")
    args = parser.parse_args()

    event = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "session": args.session,
        "event": args.event,
        "message": args.message,
        "artifacts": args.artifact,
        "next": args.next,
    }
    log_path = resolve(args.log)
    events = append_event(log_path, event)
    summary_path = resolve(args.summary_out)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(markdown(events, log_path), encoding="utf-8")
    print(json.dumps({"ok": True, "log": str(log_path), "summary": str(summary_path), "events": len(events)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
