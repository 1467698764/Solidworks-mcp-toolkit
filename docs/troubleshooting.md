# Troubleshooting

## PowerShell ExecutionPolicy

If scripts will not run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\tools\solidworks_codex\install.ps1 -CheckOnly
```

Use process scope unless you intentionally want a persistent policy change.

## No Active SolidWorks Document

Contract term: No active SolidWorks document.

Many commands require an open `.SLDASM` or `.SLDPRT`. Open the target file in SolidWorks, then run:

```powershell
.\tools\solidworks_codex\swctl.ps1 probe
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\inspect_latest.json
```

## Cannot Attach To SldWorks.Application

Check:

- SolidWorks is installed and running in the same user session
- Python has `pywin32`
- no modal SolidWorks dialog is blocking COM calls
- only one heavy live gate is running
- stale lock files `~$*` are not holding generated documents

## MCP Config Problems

Contract term: MCP config.

The server entry point is:

```text
tools/solidworks_codex/mcp/server.cjs
```

Use `examples/codex-mcp-config.example.toml` as the config reference. This repository does not edit global Codex config automatically.

## Selection Or Mate Failures

For mate and feature execution, validate selection before writing:

```powershell
.\tools\solidworks_codex\swctl.ps1 interface-index -Report tools\solidworks_codex\reports\inspect_latest.json -Out tools\solidworks_codex\reports\interfaces.json
.\tools\solidworks_codex\swctl.ps1 mate-group-plan -Report tools\solidworks_codex\reports\inspect_latest.json -Out tools\solidworks_codex\reports\mate_plan.json
.\tools\solidworks_codex\swctl.ps1 mate-selection-check -Manifest tools\solidworks_codex\reports\mate_plan.json -Out tools\solidworks_codex\reports\mate_selection.json
```

If AddMate reports `mate_error: 1`, treat it as SolidWorks no-error only after readback confirms mate type, component participation, suppression state, placements, and interference status.

## Live Gate Timeouts

Run:

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
```

`CleanupStale` is bounded to known old generated fixture directories. It does not delete `shaper_machine_v5` or unrelated project directories. If the gate fails, inspect the JSON first; findings are usually grouped as blocking, warning, or not_applicable.

## Release Gate Fails

Run the full gate:

```powershell
.\scripts\verify-all.ps1
```

Common causes:

- stale docs still mention old tool counts
- generated artifacts leaked into tracked release paths
- `release-tree` found reports/backups/exports that should remain runtime-only
- `repo-health` or `github-readiness` found missing public docs
- MCP smoke failed after changing `server.cjs` or `swctl.ps1`
