"""Check whether the repository is ready for a competitive GitHub release."""
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


def exists(rel: str) -> bool:
    return (ROOT / rel).exists()


def check_contains(rel: str, needles: list[str]) -> dict[str, Any]:
    text = read(rel)
    present = {n: n in text for n in needles}
    return {"ok": bool(text) and all(present.values()), "path": rel, "present": present}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/github_readiness.json")
    args = parser.parse_args()

    checks = {
        "root_readme": check_contains("README.md", ["practical SolidWorks MCP", "51 MCP tools", "model-understand", "report-context", "handoff-bundle", "tool-catalog", "audit"]),
        "license": check_contains("LICENSE", ["Non-Commercial License", "non-commercial use only", "sell, rent, sublicense", "commercial licensing"]),
        "install_script": check_contains("tools/solidworks_codex/install.ps1", ["CheckOnly", "mcp", "preflight"]),
        "mcp_config_example": check_contains("examples/codex-mcp-config.example.toml", ["mcp_servers", "server.cjs"]),
        "ci_workflow": check_contains(".github/workflows/solidworks-codex-offline.yml", ["unittest", "py_compile", "node --check", "sw_github_readiness.py"]),
        "release_checklist": check_contains("docs/github-release-checklist.md", ["51 MCP tools", "model-understand", "handoff-bundle", "Do not commit", "audit"]),
        "security": check_contains("SECURITY.md", ["backup", "Generated macros", "Read-only"]),
        "contributing": check_contains("CONTRIBUTING.md", ["offline test", "audit", "MCP"]),
        "offline_demo": check_contains("docs/demo/README.md", ["offline demo", "report-context", "handoff-bundle"]),
        "public_copy_guard": check_contains("tools/solidworks_codex/scripts/sw_public_copy_guard.py", ["FORBIDDEN", "violations", "files_checked"]),
        "repo_health": check_contains("tools/solidworks_codex/scripts/sw_repo_health.py", ["verify_script", "pull_request_template", "demo_static_bundle"]),
        "usage_docs": check_contains("docs/solidworks-codex-usage.md", ["report-context", "worklog", "handoff-bundle", "tool-catalog"]),
        "tool_catalog_mention": check_contains("tools/solidworks_codex/README.md", ["solidworks_tool_catalog", "solidworks_handoff_bundle", "solidworks_worklog"]),
        "audit_gate": check_contains("tools/solidworks_codex/scripts/sw_audit.py", ["check_tool_catalog", "check_handoff_bundle", "check_worklog"]),
    }
    ok = all(c.get("ok") for c in checks.values())
    report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "ok": ok, "checks": checks}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": ok, "out": str(out), "checks": {k: v.get("ok") for k, v in checks.items()}}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
