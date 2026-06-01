"""Create a SolidWorks Codex work-session snapshot package.

Live mode runs inspect first; offline mode accepts an existing inspect JSON. Then it
creates summary Markdown, issue Markdown/JSON, and a manifest that points to all files.
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
SCRIPTS = ROOT / "tools" / "solidworks_codex" / "scripts"


def run(cmd: list[str]) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, shell=False, encoding="utf-8", errors="replace")
    return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="session")
    parser.add_argument("--from-report", default="", help="Existing inspect JSON to use instead of live inspect")
    parser.add_argument("--start", action="store_true", help="Allow launching SolidWorks for live inspect")
    parser.add_argument("--out-dir", default="tools/solidworks_codex/reports/sessions")
    args = parser.parse_args()

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in args.name)
    out_dir = ROOT / args.out_dir / f"{stamp}-{safe_name}"
    out_dir.mkdir(parents=True, exist_ok=True)

    inspect_json = out_dir / "inspect.json"
    commands = []
    if args.from_report:
        inspect_json.write_text(Path(args.from_report).read_text(encoding="utf-8-sig"), encoding="utf-8")
        commands.append({"cmd": ["copy", args.from_report, str(inspect_json)], "returncode": 0, "stdout": "copied existing report", "stderr": ""})
    else:
        inspect_script = SCRIPTS / "sw_assembly_inspect.py"
        cmd = [sys.executable, str(inspect_script), "--out", str(inspect_json)]
        if args.start:
            cmd.insert(2, "--start")
        result = run(cmd)
        commands.append(result)
        if result["returncode"] != 0:
            manifest = {"timestamp": datetime.now().isoformat(timespec="seconds"), "ok": False, "out_dir": str(out_dir), "commands": commands}
            (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(manifest, ensure_ascii=False, indent=2))
            raise SystemExit(result["returncode"])

    summary_md = out_dir / "summary.md"
    issue_md = out_dir / "issue_report.md"
    issue_json = out_dir / "issue_report.json"
    commands.append(run([sys.executable, str(SCRIPTS / "sw_report_summary.py"), str(inspect_json), "--out", str(summary_md)]))
    commands.append(run([sys.executable, str(SCRIPTS / "sw_issue_report.py"), "--report", str(inspect_json), "--out", str(issue_md), "--json-out", str(issue_json)]))

    ok = all(c["returncode"] == 0 for c in commands)
    manifest = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "ok": ok,
        "name": args.name,
        "out_dir": str(out_dir),
        "inspect_json": str(inspect_json),
        "summary_md": str(summary_md),
        "issue_md": str(issue_md),
        "issue_json": str(issue_json),
        "commands": commands,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
