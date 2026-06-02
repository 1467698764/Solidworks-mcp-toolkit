# Troubleshooting

This guide covers common setup, runtime, and release-check failures for the SolidWorks Codex MCP control layer. Start with `preflight`, then use the symptom sections below.

## Quick diagnosis

```powershell
.\tools\solidworks_codex\install.ps1 -CheckOnly
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\scripts\verify-all.ps1 -SkipMcpSmoke
```

If `verify-all` fails, fix the first failing gate before running later gates.

## PowerShell ExecutionPolicy blocks scripts

Symptom:

```text
File ... cannot be loaded because running scripts is disabled on this system.
```

Use the same bounded invocation used by CI and MCP:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\solidworks_codex\swctl.ps1 preflight
```

Do not change machine-wide policy unless you intentionally manage that system.

## Python is not found

Symptom:

```text
No usable Python found. Install Python 3 or set SWCODEX_PYTHON to a python.exe path.
```

Fix options:

1. Install Python 3.12 and ensure `python` is on PATH.
2. Set `SWCODEX_PYTHON` to a specific `python.exe`.
3. In Codex runtime environments, confirm the bundled Python path exists under `.cache\codex-runtimes`.

Verify:

```powershell
python --version
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
```

## Node or MCP smoke fails

Symptoms include `node` not found, syntax errors in `server.cjs`, or an MCP smoke timeout.

Verify the offline pieces first:

```powershell
node --version
node --check tools\solidworks_codex\mcp\server.cjs
node --check tools\solidworks_codex\mcp\smoke-test.cjs
node tools\solidworks_codex\mcp\smoke-test.cjs
```

If syntax checks pass but smoke fails, inspect the first `is_error: true` field in the smoke output and rerun the matching `swctl.ps1` command directly.

## SolidWorks COM is missing

Symptom in preflight:

```text
SldWorks.Application: MISSING
```

Likely causes:

- SolidWorks is not installed on this Windows machine.
- SolidWorks is installed but COM registration is broken.
- You are running on a CI runner or non-Windows host.

Offline gates should still work without SolidWorks. Live commands such as inspect, rebuild, export, and set-dimension require local SolidWorks COM.

## No active SolidWorks document

Symptom:

```text
No active SolidWorks document. Open a document or pass --model.
```

Fix:

1. Open the target `.SLDASM` or `.SLDPRT` in SolidWorks.
2. Save it once so backup paths are stable.
3. Rerun the command.

For read-only attach tests, use:

```powershell
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\inspect_latest.json
```

Only use `start-inspect` if you intentionally allow the command to launch SolidWorks.

## A guarded write fails

For `set-dimension`, `component-state`, generated macro workflows, or rebuild/export failures:

1. Stop after the first failure.
2. Check the generated JSON report in `tools\solidworks_codex\reports\`.
3. Confirm a backup exists before trying another write.
4. Run inspect again and compare before/after reports.

Useful commands:

```powershell
.\tools\solidworks_codex\swctl.ps1 backup -Files 'C:\path\to\model.SLDASM' -Out tools\solidworks_codex\reports\backup_before_change.json
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild_latest.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\before.json -After tools\solidworks_codex\reports\after.json -Out tools\solidworks_codex\reports\delta.md
```

## Live gate times out or SolidWorks becomes unresponsive

Symptoms include `timeout_after_<seconds>s`, `SLDWORKS.exe Responding=False`, high private memory, or generated `~$*.SLDPRT` / `~$*.SLDASM` lock files under `tools\solidworks_codex\live_fixture`.

Recommended sequence:

1. Do not immediately rerun the heavy check.
2. Inspect `tools\solidworks_codex\reports\live_validation_gate.json`; timeout entries include `timeout_cleanup` with any terminated PIDs.
3. Confirm no generated lock files remain:

```powershell
Get-ChildItem tools\solidworks_codex\live_fixture -Filter '~$*' -Recurse -Force
```

4. If lock files remain only under generated fixture directories and no `SLDWORKS.exe` is running, remove those generated locks before rerunning.
5. Rerun the minimal session smoke or `live-gate -ValidateOnly` before attempting the full gate again.

The live gate intentionally runs checks serially, refuses stale generated locks before launching SolidWorks, and only terminates SolidWorks on timeout when the process is not responding or exceeds the configured memory threshold.

## Release gates fail

Run the focused gate directly:

```powershell
.\tools\solidworks_codex\swctl.ps1 repo-health -Out tools\solidworks_codex\reports\repo_health.json
.\tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
```

- `repo-health` usually means a public asset, README link, or workflow gate is missing.
- `public-copy-guard` means release-facing copy includes blocked ranking or overclaim wording.
- `release-tree` means Git-visible files include generated reports, backups, exports, caches, macros, logs, or personal config paths.

## MCP config is not active

This repository does not edit `<codex-home>\config.toml` automatically. Copy from `examples/codex-mcp-config.example.toml` only when you intentionally register the MCP server. After editing config, restart the Codex session and run the MCP smoke test again.

## What to attach to a bug report

Include:

- Exact command run.
- Exit code and first error message.
- Relevant JSON report from `tools\solidworks_codex\reports\`.
- Whether SolidWorks was open and which model type was active.
- Output from `preflight` and `repo-health`.

