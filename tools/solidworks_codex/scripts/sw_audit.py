"""Offline audit for the SolidWorks Codex toolchain.

Runs deterministic checks that do not require an active SolidWorks document:
- Python syntax compilation for scripts
- required artifact presence
- swctl command surface check
- fixture report comparison
- MCP smoke test
- usage guide command consistency
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
SCRIPTS = ROOT / "tools" / "solidworks_codex" / "scripts"
REPORTS = ROOT / "tools" / "solidworks_codex" / "reports"

REQUIRED = [
    "docs/solidworks-codex-usage.md",
    "docs/architecture.md",
    "docs/project-principles.md",
    "docs/github-release-checklist.md",
    "tools/solidworks_codex/swctl.ps1",
    "tools/solidworks_codex/mcp/server.cjs",
    "tools/solidworks_codex/mcp/smoke-test.cjs",
    "tools/solidworks_codex/sandbox/compare_fixture.json",
]


def run(cmd: list[str], timeout: int = 60) -> dict[str, Any]:
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout, shell=False)
    return {"cmd": cmd, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def check_required() -> dict[str, Any]:
    items = []
    ok = True
    for rel in REQUIRED:
        path = ROOT / rel
        exists = path.exists()
        ok = ok and exists
        items.append({"path": rel, "exists": exists, "length": path.stat().st_size if exists else None})
    return {"ok": ok, "items": items}


def check_py_compile() -> dict[str, Any]:
    files = [str(p) for p in sorted(SCRIPTS.glob("*.py"))]
    result = run([sys.executable, "-m", "py_compile", *files])
    return {"ok": result["returncode"] == 0, "files": files, "result": result}


def swctl_commands() -> set[str]:
    text = (ROOT / "tools/solidworks_codex/swctl.ps1").read_text(encoding="utf-8-sig")
    match = re.search(r"ValidateSet\(([^)]*)\)", text)
    if not match:
        return set()
    return set(re.findall(r"'([^']+)'", match.group(1)))


def guide_commands() -> set[str]:
    text = (ROOT / "docs/solidworks-codex-usage.md").read_text(encoding="utf-8-sig")
    return set(re.findall(r"swctl\.ps1\s+([a-zA-Z0-9-]+)", text))


def check_guide_commands() -> dict[str, Any]:
    sw = swctl_commands()
    guide = guide_commands()
    missing = sorted(guide - sw)
    return {"ok": not missing, "swctl_commands": sorted(sw), "guide_commands": sorted(guide), "missing_from_swctl": missing}


def check_compare_fixture() -> dict[str, Any]:
    out = "tools/solidworks_codex/reports/audit_compare.md"
    jout = "tools/solidworks_codex/reports/audit_compare.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "compare", "-Before", "tools/solidworks_codex/sandbox/report_before.json", "-After", "tools/solidworks_codex/sandbox/report_after.json", "-Out", out, "-JsonOut", jout,
    ])
    out_path = ROOT / out
    text = out_path.read_text(encoding="utf-8-sig") if out_path.exists() else ""
    expected = ["reference_sensor-1", "D1@Sketch1@plate.SLDPRT", "support_bushing-1"]
    return {"ok": result["returncode"] == 0 and all(e in text for e in expected), "result": result, "output": out, "expected_present": {e: e in text for e in expected}}


def check_mcp_smoke() -> dict[str, Any]:
    result = run(["node", "tools/solidworks_codex/mcp/smoke-test.cjs"], timeout=90)
    parsed = None
    try:
        parsed = json.loads(result["stdout"])
    except Exception:
        pass
    ok = result["returncode"] == 0 and isinstance(parsed, dict) and parsed.get("tool_count", 0) >= 12 and not parsed.get("backup_is_error") and not parsed.get("compare_is_error")
    return {"ok": ok, "result": result, "parsed": parsed}


def check_session_snapshot() -> dict[str, Any]:
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "session-snapshot", "-SessionName", "audit-fixture", "-FromReport", "tools/solidworks_codex/sandbox/report_after.json", "-OutDir", "tools/solidworks_codex/reports/sessions",
    ], timeout=90)
    manifest_ok = any(p.name == "manifest.json" and "\"ok\": true" in p.read_text(encoding="utf-8-sig") for p in (ROOT / "tools/solidworks_codex/reports/sessions").glob("*-audit-fixture/manifest.json"))
    ok = result["returncode"] == 0 and ("\"ok\": true" in result["stdout"] or manifest_ok)
    return {"ok": ok, "result": result, "manifest_ok": manifest_ok}



def check_design_tools() -> dict[str, Any]:
    review_md = "tools/solidworks_codex/reports/audit_design_review.md"
    review_json = "tools/solidworks_codex/reports/audit_design_review.json"
    plan_md = "tools/solidworks_codex/reports/audit_change_plan.md"
    plan_json = "tools/solidworks_codex/reports/audit_change_plan.json"
    r1 = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "design-review", "-Report", "tools/solidworks_codex/sandbox/report_after.json", "-Target", "locating interfaces, floating components, editable dimensions, and manufacturability evidence", "-Out", review_md, "-JsonOut", review_json,
    ])
    r2 = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "change-plan", "-Report", "tools/solidworks_codex/sandbox/report_after.json", "-Target", "adjust a critical mounting dimension and verify assembly, clearance, and manufacturing evidence", "-Out", plan_md, "-JsonOut", plan_json,
    ])
    review_text = (ROOT / review_md).read_text(encoding="utf-8-sig") if (ROOT / review_md).exists() else ""
    plan_text = (ROOT / plan_md).read_text(encoding="utf-8-sig") if (ROOT / plan_md).exists() else ""
    expected = {
        "review_title": "Mechanical CAD Evidence Review" in review_text,
        "review_bearing": "support_bushing-1" in review_text,
        "plan_title": "Mechanical CAD Change Plan" in plan_text,
        "plan_dimension": "D1@Sketch1@plate.SLDPRT" in plan_text,
        "plan_snapshot": "session-snapshot" in plan_text,
    }
    return {"ok": r1["returncode"] == 0 and r2["returncode"] == 0 and all(expected.values()), "review_result": r1, "plan_result": r2, "expected_present": expected}

def check_report_search() -> dict[str, Any]:
    out_md = "tools/solidworks_codex/reports/audit_report_search.md"
    out_json = "tools/solidworks_codex/reports/audit_report_search.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "report-search", "-Report", "tools/solidworks_codex/sandbox/report_after.json", "-Target", "support bushing D1 Fillet", "-Out", out_md, "-JsonOut", out_json,
    ])
    text = (ROOT / out_md).read_text(encoding="utf-8-sig") if (ROOT / out_md).exists() else ""
    expected = {"bearing": "support_bushing-1" in text, "dimension": "D1@Sketch1@plate.SLDPRT" in text, "feature": "Fillet1" in text}
    return {"ok": result["returncode"] == 0 and all(expected.values()), "result": result, "expected_present": expected}


def check_report_context() -> dict[str, Any]:
    out_md = "tools/solidworks_codex/reports/audit_report_context.md"
    out_json = "tools/solidworks_codex/reports/audit_report_context.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "report-context", "-Report", "tools/solidworks_codex/sandbox/report_after.json", "-Target", "understand current assembly constraints, editable dimensions, clearance, and manufacturing evidence", "-Out", out_md, "-JsonOut", out_json,
    ])
    text = (ROOT / out_md).read_text(encoding="utf-8-sig") if (ROOT / out_md).exists() else ""
    expected = {
        "title": "SolidWorks Codex Context Pack" in text,
        "bearing": "support_bushing-1" in text,
        "dimension": "D1@Sketch1@plate.SLDPRT" in text,
        "anti_template": "Do not blindly replay templates" in text,
        "flexible_queries": "Flexible next queries" in text,
        "evidence_gaps": "Evidence gaps" in text,
    }
    return {"ok": result["returncode"] == 0 and all(expected.values()), "result": result, "expected_present": expected}


def check_worklog() -> dict[str, Any]:
    log_path = "tools/solidworks_codex/reports/audit_worklog.jsonl"
    summary_path = "tools/solidworks_codex/reports/audit_worklog.md"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "worklog", "-SessionName", "audit", "-Action", "verification",
        "-Message", "Audit recorded a durable worklog event",
        "-Artifact", "tools/solidworks_codex/sandbox/report_after.json",
        "-Next", "Use worklog before multi-turn handoff",
        "-Out", log_path, "-JsonOut", summary_path,
    ])
    text = (ROOT / summary_path).read_text(encoding="utf-8-sig") if (ROOT / summary_path).exists() else ""
    expected = {
        "title": "SolidWorks Codex Worklog" in text,
        "message": "Audit recorded a durable worklog event" in text,
        "next": "Use worklog before multi-turn handoff" in text,
    }
    return {"ok": result["returncode"] == 0 and all(expected.values()), "result": result, "expected_present": expected}


def check_handoff_bundle() -> dict[str, Any]:
    out_dir = "tools/solidworks_codex/reports/audit_handoff"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "handoff-bundle", "-Report", "tools/solidworks_codex/sandbox/report_after.json",
        "-FromReport", "tools/solidworks_codex/reports/audit_worklog.jsonl",
        "-Target", "current model evidence, constraints, clearance, and manufacturing gaps",
        "-OutDir", out_dir,
    ])
    readme = ROOT / out_dir / "README.md"
    context = ROOT / out_dir / "context.md"
    manifest = ROOT / out_dir / "manifest.json"
    text = readme.read_text(encoding="utf-8-sig") if readme.exists() else ""
    context_text = context.read_text(encoding="utf-8-sig") if context.exists() else ""
    data = json.loads(manifest.read_text(encoding="utf-8-sig")) if manifest.exists() else {}
    expected = {
        "ok": data.get("ok") is True,
        "title": "SolidWorks Codex Handoff Bundle" in text,
        "anti_template": "Do not blindly replay templates" in text,
        "flexible_queries": "Flexible next queries" in context_text,
        "evidence_gaps": "Evidence gaps" in context_text,
        "context": context.exists(),
        "worklog": (ROOT / out_dir / "worklog.md").exists(),
    }
    return {"ok": result["returncode"] == 0 and all(expected.values()), "result": result, "expected_present": expected}


def check_tool_catalog() -> dict[str, Any]:
    out_md = "tools/solidworks_codex/reports/audit_tool_catalog.md"
    out_json = "tools/solidworks_codex/reports/audit_tool_catalog.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "tool-catalog", "-Out", out_md, "-JsonOut", out_json,
    ])
    data = json.loads((ROOT / out_json).read_text(encoding="utf-8-sig")) if (ROOT / out_json).exists() else {}
    text = (ROOT / out_md).read_text(encoding="utf-8-sig") if (ROOT / out_md).exists() else ""
    names = {t.get("name") for t in data.get("tools", [])} if isinstance(data, dict) else set()
    expected = {
        "title": "SolidWorks MCP Tool Catalog" in text,
        "handoff_tool": "solidworks_handoff_bundle" in names,
        "worklog_tool": "solidworks_worklog" in names,
        "count": data.get("count", 0) >= 28 if isinstance(data, dict) else False,
    }
    return {"ok": result["returncode"] == 0 and all(expected.values()), "result": result, "expected_present": expected}


def check_github_readiness() -> dict[str, Any]:
    out_json = "tools/solidworks_codex/reports/audit_github_readiness.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "github-readiness", "-Out", out_json,
    ])
    data = json.loads((ROOT / out_json).read_text(encoding="utf-8-sig")) if (ROOT / out_json).exists() else {}
    return {"ok": result["returncode"] == 0 and data.get("ok") is True, "result": result, "checks": data.get("checks")}


def check_public_copy_guard() -> dict[str, Any]:
    out_json = "tools/solidworks_codex/reports/audit_public_copy_guard.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "public-copy-guard", "-Out", out_json,
    ])
    data = json.loads((ROOT / out_json).read_text(encoding="utf-8-sig")) if (ROOT / out_json).exists() else {}
    return {"ok": result["returncode"] == 0 and data.get("ok") is True, "result": result, "violations": data.get("violations")}


def check_repo_health() -> dict[str, Any]:
    out_json = "tools/solidworks_codex/reports/audit_repo_health.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "repo-health", "-Out", out_json,
    ])
    data = json.loads((ROOT / out_json).read_text(encoding="utf-8-sig")) if (ROOT / out_json).exists() else {}
    return {"ok": result["returncode"] == 0 and data.get("ok") is True, "result": result, "checks": data.get("checks")}



def check_release_tree() -> dict[str, Any]:
    out_json = "tools/solidworks_codex/reports/audit_release_tree.json"
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "release-tree", "-Out", out_json,
    ])
    data = json.loads((ROOT / out_json).read_text(encoding="utf-8-sig")) if (ROOT / out_json).exists() else {}
    return {"ok": result["returncode"] == 0 and data.get("ok") is True, "result": result, "violations": data.get("violations"), "files_checked": data.get("files_checked")}


def check_preflight() -> dict[str, Any]:
    result = run([
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1",
        "preflight", "-Out", "tools/solidworks_codex/reports/audit_preflight.json",
    ], timeout=60)
    preflight_path = ROOT / "tools/solidworks_codex/reports/audit_preflight.json"
    preflight_ok = False
    if preflight_path.exists():
        try:
            preflight_ok = json.loads(preflight_path.read_text(encoding="utf-8-sig")).get("ok") is True
        except Exception:
            preflight_ok = False
    ok = result["returncode"] == 0 and ("\"ok\": true" in result["stdout"] or preflight_ok)
    return {"ok": ok, "result": result, "preflight_ok": preflight_ok}
def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/audit_latest.json")
    args = parser.parse_args()
    checks = {
        "required": check_required(),
        "py_compile": check_py_compile(),
        "guide_commands": check_guide_commands(),
        "compare_fixture": check_compare_fixture(),
        "mcp_smoke": check_mcp_smoke(),
        "session_snapshot": check_session_snapshot(),
        "design_tools": check_design_tools(),
        "report_search": check_report_search(),
        "report_context": check_report_context(),
        "worklog": check_worklog(),
        "handoff_bundle": check_handoff_bundle(),
        "tool_catalog": check_tool_catalog(),
        "github_readiness": check_github_readiness(),
        "public_copy_guard": check_public_copy_guard(),
        "repo_health": check_repo_health(),
        "release_tree": check_release_tree(),
        "preflight": check_preflight(),
    }
    ok = all(v.get("ok") for v in checks.values())
    report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "ok": ok, "checks": checks}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": ok, "out": str(out), "checks": {k: v.get("ok") for k, v in checks.items()}}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()






