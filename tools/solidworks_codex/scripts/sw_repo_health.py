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
        "demo_static_bundle": check("docs/demo/offline/README.md", ["5-minute offline demo", "report-context", "handoff-bundle"]),
        "readme_demo_link": check("README.md", ["docs/demo/README.md", "verify-all.ps1"]),
        "release_checklist_verify_all": check("docs/github-release-checklist.md", ["verify-all.ps1", "Do not commit"]),
        "changelog_release_notes": check("CHANGELOG.md", ["Unreleased", "Added", "Release gates", "offline demo"]),
        "roadmap_public_direction": check("ROADMAP.md", ["Near term", "Future", "Non-goals", "SolidWorks"]),
        "readme_project_lifecycle_links": check("README.md", ["CHANGELOG.md", "ROADMAP.md"]),
        "release_tree_gate": check("scripts/verify-all.ps1", ["release-tree", "release_tree.json"]),
        "architecture_doc": check("docs/architecture.md", ["Layer map", "Data flow", "Safety model", "release-tree", "MCP"]),
        "readme_architecture_link": check("README.md", ["docs/architecture.md"]),
        "troubleshooting_doc": check("docs/troubleshooting.md", ["ExecutionPolicy", "No active SolidWorks document", "SldWorks.Application", "release-tree", "MCP config"]),
        "readme_troubleshooting_link": check("README.md", ["docs/troubleshooting.md"]),
        "workflows_doc": check("docs/workflows/README.md", ["offline demo", "session-snapshot", "report-context", "backup", "rebuild", "compare", "handoff-bundle", "public-copy-guard"]),
        "readme_workflows_link": check("README.md", ["docs/workflows/README.md"]),
        "capability_matrix_doc": check("docs/capability-matrix.md", ["SolidWorks Codex Capability Matrix", "guarded_write", "solidworks_report_context", "CLI for every local MCP tool"]),
        "capability_matrix_json": check("docs/capability-matrix.json", ["has_cli_for_every_local_mcp", "solidworks_report_context", "guarded_write"]),
        "readme_capability_matrix_link": check("README.md", ["docs/capability-matrix.md", "capability-matrix"]),
        "prompt_library_doc": check("docs/prompts.md", ["Codex Prompt Library", "Guarded one-variable CAD edit", "report-context", "handoff-bundle", "public-copy-guard", "release-tree"]),
        "readme_prompt_library_link": check("README.md", ["docs/prompts.md", "Prompt library"]),
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
