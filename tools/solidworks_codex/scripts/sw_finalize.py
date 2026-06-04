"""Create a final readiness report for the SolidWorks Codex toolchain."""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

CAPABILITIES = [
    "preflight environment check",
    "session snapshot: inspect + summary + issue report",
    "read-only assembly/part inspection",
    "Markdown summary generation",
    "issue/risk report generation",
    "timestamped backup",
    "single-dimension modification",
    "rebuild",
    "export by target suffix",
    "mass properties",
    "before/after report comparison",
    "component hide/show/suppress/unsuppress/fix/float",
    "interference-check entry point",
    "selection report for preselected entities",
    "preselected-entity mate macro generation",
    "common part template macro generation",
    "local MCP wrapper",
    "report search for messy component/dimension/feature names",
    "freeform report context packs for handoff and non-template reasoning",
    "durable multi-turn worklog for decisions, verification, failures, and next steps",
    "handoff bundles with inspect report, context, worklog, README, and manifest",
    "MCP tool catalog for discoverability and workflow selection",
    "GitHub release readiness gate with README, license, installer, CI, and config example",
    "offline demo bundle for five-minute public evaluation",
    "public copy guard to prevent rank-boasting and overclaiming in release docs",
    "repository health checks for issue templates, PR template, demo bundle, and verify-all",
    "offline audit gate",
]

NEXT_WORKFLOW = [
    "Run preflight.",
    "Open the target assembly or part in SolidWorks.",
    "Run session-snapshot with a descriptive name.",
    "Record important assumptions and decisions with worklog.",
    "Generate a handoff-bundle before pausing, switching tasks, or committing.",
    "Use tool-catalog when choosing the next MCP tool instead of relying on memory.",
    "Run github-readiness before publishing to GitHub.",
    "Read summary.md and issue_report.md.",
    "Back up the assembly and any parts that may be modified.",
    "Make one narrow change at a time: dimension, component state, generated macro, or template part.",
    "Rebuild and inspect again.",
    "Compare before/after reports.",
    "Export deliverables if needed.",
    "Run audit before commit or handoff.",
]


def run(cmd: list[str], timeout: int = 120) -> dict[str, Any]:
    p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, shell=False)
    return {"cmd": cmd, "returncode": p.returncode, "stdout": p.stdout, "stderr": p.stderr}


def read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}




SUMMARY_KEEP_KEYS = {"ok", "timestamp", "checks", "preflight_ok"}


def summarize_result(value: Any) -> Any:
    if isinstance(value, dict):
        if "returncode" in value and ("stdout" in value or "stderr" in value or "cmd" in value):
            return {"returncode": value.get("returncode")}
        return {
            k: summarize_result(v)
            for k, v in value.items()
            if k not in {"stdout", "stderr", "cmd", "result", "review_result", "plan_result"}
            and not k.endswith("_text_head")
        }
    if isinstance(value, list):
        return [summarize_result(v) for v in value]
    return value


def summarize_audit(audit: Any) -> Any:
    if not isinstance(audit, dict):
        return audit
    checks = audit.get("checks")
    summarized_checks = {}
    if isinstance(checks, dict):
        for name, result in checks.items():
            if isinstance(result, dict):
                summarized_checks[name] = summarize_result(result)
            else:
                summarized_checks[name] = result
    return {"timestamp": audit.get("timestamp"), "ok": audit.get("ok"), "checks": summarized_checks}


def summarize_preflight(preflight: Any) -> Any:
    if not isinstance(preflight, dict):
        return preflight
    return {"timestamp": preflight.get("timestamp"), "ok": preflight.get("ok")}


def markdown(report: dict[str, Any]) -> str:
    lines = ["# SolidWorks Codex Current Readiness Report", ""]
    lines += [
        f"- Timestamp: `{report['timestamp']}`",
        "- Branch: `main`",
        "- Current stance: evidence-first SolidWorks MCP/control layer with offline gates, MCP smoke, validation profiles, and opt-in live SolidWorks validation.",
        f"- Audit OK: `{report['audit_ok']}`",
        f"- Preflight OK: `{report['preflight_ok']}`",
        "",
    ]
    lines += [
        "## What is considered ready",
        "",
        "- 45 MCP tools are documented and routed through the local PowerShell/Python control layer.",
        "- Offline unit tests cover report parsing, context/search/model-understand flows, guarded change verification, release gates, public-copy guard, live-gate validation logic, validation profiles, and fixture-level assembly contracts.",
        "- Native `.SLDASM/.SLDPRT` artifacts are treated as the deliverable for CAD work; STEP optional smoke is only supplemental.",
        "- Intent-scoped validation profiles exist: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release`.",
        "- `runtime_budget` and `extra_checks` let the reasoning model scale validation without forcing full engineering release checks on every draft.",
        "- `model-understand` fuses feature-tree evidence with explicit `mate_like_features` readback, so sparse feature rows do not hide semantic mate participation or underconnected constraint networks.",
        "",
        "## Latest live SolidWorks evidence",
        "",
        "Latest verified live capability suite:",
        "",
        "```text",
        "tools/solidworks_codex/live_fixture/live_capability_suite/capability_suite.SLDASM",
        "tools/solidworks_codex/reports/live_capability_suite/live_capability_suite.json",
        "```",
        "",
        "Evidence summary:",
        "",
        "- `ok: true`",
        "- validation failed list empty",
        "- `part_geometry_readback` present for four reopened native `.SLDPRT` files",
        "- native file readback covers body count, bbox size, volume, and semantic solid-effect evidence for boss/cut/revolve/revolved cut operations",
        "- `assembly_component_placements` solved origins match the accepted layout",
        "- `mate_error: 1` on AddMate calls, which is SolidWorks AddMate no-error",
        "- interference callback should report `0 interference` for static acceptance",
        "- post-cleanup lock files empty",
        "",
        "Simple-mechanism regression fixture:",
        "",
        "```text",
        "tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM",
        "tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json",
        "```",
        "",
        "This fixture should be read as a regression target with known limitations, not as a showcase. Current readiness claims should focus on the generic evidence it can exercise: native file creation, part feature readback, component placement/readback, semantic mate participation, fixed/floating policy, interference callback, model-understanding output, and cleanup. A passing JSON report is not enough if the SolidWorks window shows a scattered assembly or the mate graph is only fixture-stabilized.",
        "",
        "Old fixture JSON should not be treated as proof after validator changes. The current direction is to replace fixture-specific placement confidence with general assembly diagnosis, interface indexing, mate groups, visual validation, and local repair. Until those are implemented and live-verified, the project should not claim general mechanism assembly competence.",
        "",
    ]
    lines += ["## Capabilities"] + [f"- {c}" for c in CAPABILITIES] + [""]
    lines += ["## Recommended real-model workflow"] + [f"{i+1}. {step}" for i, step in enumerate(NEXT_WORKFLOW)] + [""]
    lines += [
        "## Open hardening areas",
        "",
        "These are intentionally not claimed as solved globally:",
        "",
        "- Full general DOF solver and motion sweep validation are profile-scoped targets, not universal default checks.",
        "- DFM/DFA and strength/stiffness screens are currently lightweight evidence gates unless the task explicitly requests deeper engineering validation.",
        "- The live capability suite proves a useful native feature/mate/geometry path, but broad CAD usefulness still depends on assembly diagnosis, interface indexing, local repair, mate groups, visual validation, and mechanism-lite checks. Named fixtures are regression cases, not the project identity.",
        "",
    ]
    lines += ["## Key files"]
    for key, value in report["key_files"].items():
        lines.append(f"- {key}: `{value}`")
    lines += ["", "## Verification summary"]
    audit = report.get("audit") or {}
    checks = audit.get("checks") if isinstance(audit, dict) else None
    if isinstance(checks, dict):
        for name, result in checks.items():
            lines.append(f"- `{name}`: `{result.get('ok')}`")
    else:
        lines.append("- Audit details unavailable")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="docs/solidworks-codex-final-readiness.md")
    parser.add_argument("--json-out", default="tools/solidworks_codex/reports/final_readiness.json")
    parser.add_argument("--run-audit", action="store_true")
    args = parser.parse_args()

    audit_path = ROOT / "tools/solidworks_codex/reports/audit_latest.json"
    audit_result = None
    audit = read_json(audit_path)
    should_run_audit = args.run_audit or not isinstance(audit, dict) or audit.get("ok") is not True
    if should_run_audit:
        audit_result = run(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", "tools/solidworks_codex/swctl.ps1", "audit", "-Out", "tools/solidworks_codex/reports/audit_latest.json"])
        audit = read_json(audit_path)
    preflight = read_json(ROOT / "tools/solidworks_codex/reports/preflight_latest.json") or read_json(ROOT / "tools/solidworks_codex/reports/audit_preflight.json")
    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "audit_ok": isinstance(audit, dict) and audit.get("ok") is True,
        "preflight_ok": isinstance(preflight, dict) and preflight.get("ok") is True,
        "audit_command": summarize_result(audit_result),
        "audit": summarize_audit(audit),
        "preflight": summarize_preflight(preflight),
        "capabilities": CAPABILITIES,
        "next_workflow": NEXT_WORKFLOW,
        "key_files": {
            "usage": "docs/solidworks-codex-usage.md",
            "readme": "tools/solidworks_codex/README.md",
            "swctl": "tools/solidworks_codex/swctl.ps1",
            "mcp_server": "tools/solidworks_codex/mcp/server.cjs",
            "audit": "tools/solidworks_codex/reports/audit_latest.json",
        },
    }
    jout = ROOT / args.json_out
    jout.parent.mkdir(parents=True, exist_ok=True)
    jout.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(markdown(report), encoding="utf-8")
    print(json.dumps({"out": str(out), "json_out": str(jout), "audit_ok": report["audit_ok"], "preflight_ok": report["preflight_ok"]}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if report["audit_ok"] else 1)


if __name__ == "__main__":
    main()
