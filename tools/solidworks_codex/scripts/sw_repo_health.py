"""Check public repository health assets for GitHub collaboration."""
from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def read(rel: str) -> str:
    path = ROOT / rel
    return path.read_text(encoding="utf-8-sig") if path.exists() else ""


def check(rel: str, needles: list[str]) -> dict[str, Any]:
    text = read(rel)
    present = {n: n in text for n in needles}
    return {"ok": bool(text) and all(present.values()), "path": rel, "present": present}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/repo_health.json")
    args = parser.parse_args()

    checks = {
        "verify_script": check("scripts/verify-all.ps1", ["unittest", "py_compile", "node --check", "audit"]),
        "issue_template_bug": check(".github/ISSUE_TEMPLATE/bug_report.md", ["Reproduction", "Environment", "backup"]),
        "issue_template_feature": check(".github/ISSUE_TEMPLATE/feature_request.md", ["Workflow problem", "Safety", "report-context"]),
        "pull_request_template": check(".github/pull_request_template.md", ["Safety model", "Verification", "verify-all.ps1"]),
        "readme_quickstart": check("README.md", ["Quick Start", "Inspect a Model", "Validate the Result"]),
        "readme_project_trackers": check("README.md", ["docs/solidworks-automation-plan.md", "docs/solidworks-codex-capability-gap-checklist.md", "docs/mcp-tools.md"]),
        "release_tree_gate": check("scripts/verify-all.ps1", ["release-tree", "release_tree.json"]),
        "mcp_manual": check("docs/mcp-tools.md", ["MCP Tool Manual", "Required parameters", "Optional parameters", "Capability scope", "Limits and notes"]),
        "mcp_manual_tools": check("docs/mcp-tools.md", ["solidworks_inspect", "solidworks_part_feature_execute", "solidworks_mate_group_execute", "solidworks_handoff_bundle"]),
        "automation_plan": check("docs/solidworks-automation-plan.md", ["SolidWorks", "MCP"]),
        "capability_checklist": check("docs/solidworks-codex-capability-gap-checklist.md", ["present/guarded", "Capability", "Acceptance"]),
    }
    ok = all(v["ok"] for v in checks.values())
    report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "ok": ok, "checks": checks}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": ok, "out": str(out), "checks": {k: v["ok"] for k, v in checks.items()}}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
