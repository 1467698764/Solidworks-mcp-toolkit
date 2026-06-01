"""Preflight checks for SolidWorks Codex toolchain."""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]


def run(cmd: list[str], timeout: int = 20) -> dict[str, Any]:
    try:
        p = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout, shell=False)
        return {"cmd": cmd, "ok": p.returncode == 0, "returncode": p.returncode, "stdout": p.stdout.strip(), "stderr": p.stderr.strip()}
    except Exception as exc:
        return {"cmd": cmd, "ok": False, "error": f"{type(exc).__name__}: {exc}"}


def command_version(name: str, args: list[str] | None = None) -> dict[str, Any]:
    path = shutil.which(name)
    result = {"name": name, "path": path, "available": path is not None}
    if path:
        result["version"] = run([name, *(args or ["--version"])])
    return result


def com_probe() -> dict[str, Any]:
    ps = "try { $t=[type]::GetTypeFromProgID('SldWorks.Application'); if($t){'OK'} else {'MISSING'} } catch { $_.Exception.Message }"
    return run(["powershell.exe", "-NoProfile", "-Command", ps])


def file_check(rel: str) -> dict[str, Any]:
    path = ROOT / rel
    return {"path": rel, "exists": path.exists(), "length": path.stat().st_size if path.exists() else None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="tools/solidworks_codex/reports/preflight.json")
    parser.add_argument("--run-mcp-smoke", action="store_true")
    args = parser.parse_args()
    codex_python = ROOT.home() / ".cache" / "codex-runtimes" / "codex-primary-runtime" / "dependencies" / "python" / "python.exe"
    python_sources = [
        {"name": "current", "path": sys.executable, "available": bool(sys.executable), "version": run([sys.executable, "--version"]) if sys.executable else None},
        {"name": "SWCODEX_PYTHON", "path": os.environ.get("SWCODEX_PYTHON"), "available": bool(os.environ.get("SWCODEX_PYTHON")) and Path(os.environ["SWCODEX_PYTHON"]).exists()},
        {"name": "codex_runtime", "path": str(codex_python), "available": codex_python.exists()},
        command_version("py", ["--version"]),
        command_version("python", ["--version"]),
        command_version("python3", ["--version"]),
    ]
    checks = {
        "commands": [command_version("node", ["--version"]), command_version("npm", ["--version"]), command_version("git", ["--version"]), command_version("codex", ["--version"])],
        "python_sources": python_sources,
        "solidworks_com": com_probe(),
        "files": [
            file_check("tools/solidworks_codex/swctl.ps1"),
            file_check("tools/solidworks_codex/mcp/server.cjs"),
            file_check("tools/solidworks_codex/mcp/smoke-test.cjs"),
            file_check("docs/solidworks-codex-usage.md"),
        ],
        "mcp_smoke": None,
    }
    if args.run_mcp_smoke:
        checks["mcp_smoke"] = run(["node", "tools/solidworks_codex/mcp/smoke-test.cjs"], timeout=90)
    ok = any(c.get("available") for c in checks["python_sources"]) and all(c.get("available") for c in checks["commands"] if c["name"] in {"node", "git"})
    ok = ok and checks["solidworks_com"].get("stdout", "").strip() == "OK"
    ok = ok and all(f["exists"] for f in checks["files"])
    if checks["mcp_smoke"] is not None:
        ok = ok and checks["mcp_smoke"].get("ok") is True
    report = {"timestamp": datetime.now().isoformat(timespec="seconds"), "ok": ok, "checks": checks}
    out = ROOT / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"ok": ok, "out": str(out), "solidworks_com": checks["solidworks_com"].get("stdout"), "mcp_smoke": None if checks["mcp_smoke"] is None else checks["mcp_smoke"].get("ok")}, ensure_ascii=False, indent=2))
    raise SystemExit(0 if ok else 1)


if __name__ == "__main__":
    main()
