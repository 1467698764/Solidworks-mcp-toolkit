# Troubleshooting

This guide covers setup, runtime, live SolidWorks, and release-check failures for the SolidWorks Codex MCP control layer. Start with the narrowest check that can prove or disprove the symptom.

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

## Python is not found or pywin32 is missing

Symptoms:

```text
No usable Python found. Install Python 3 or set SWCODEX_PYTHON to a python.exe path.
No usable Python with pywin32 found.
```

Fix options:

1. Install Python 3.12 and ensure `python` is on PATH.
2. Install pywin32 into the Python used for live SolidWorks commands.
3. Set `SWCODEX_PYTHON` to a specific `python.exe` that can import `pythoncom` and `win32com.client`.

Verify:

```powershell
python --version
python -c "import pythoncom, win32com.client; print('pywin32 ok')"
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
```

## Node or MCP smoke fails

Verify the offline pieces first:

```powershell
node --version
node --check tools\solidworks_codex\mcp\server.cjs
node --check tools\solidworks_codex\mcp\smoke-test.cjs
node tools\solidworks_codex\mcp\smoke-test.cjs
```

If syntax checks pass but smoke fails, inspect the first `is_error: true` field and rerun the matching `swctl.ps1` command directly.

## MCP config points at the wrong command

Check that your local config uses:

```text
tools/solidworks_codex/mcp/server.cjs
```

Use `examples/codex-mcp-config.example.toml` as a reference. This repository should not edit global Codex config automatically.

## SolidWorks COM is missing

Symptom in preflight:

```text
SldWorks.Application: MISSING
```

Likely causes:

- SolidWorks is not installed on this Windows machine.
- SolidWorks is installed but COM registration is broken.
- You are running on a CI runner or non-Windows host.

Offline gates still work without SolidWorks. Live commands such as inspect, rebuild, export, mass, set-dimension, mate creation, and live-gate require local SolidWorks COM.

## No active SolidWorks document

Symptom:

```text
No active SolidWorks document. Open a document or pass --model.
```

Fix:

1. Open the target `.SLDASM` or `.SLDPRT` in SolidWorks.
2. Save it once so backup paths are stable.
3. Rerun the command.

Use `start-inspect` only when you intentionally allow the command to launch SolidWorks.

## A guarded write fails

For `safe-set-dimension`, component state changes, generated macro workflows, rebuild/export failures, or feature creation failures:

1. Stop after the first failure.
2. Read the generated JSON report in `tools/solidworks_codex/reports/`.
3. Confirm a backup exists before trying another write.
4. Inspect again and compare before/after reports.
5. If the feature does not match the selected sketch, check active document title, selection count before feature creation, selected sketch name, and rebuild errors.

Useful commands:

```powershell
.\tools\solidworks_codex\swctl.ps1 backup -Files 'C:\path\to\model.SLDASM' -Out tools\solidworks_codex\reports\backup_before_change.json
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild_latest.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\before.json -After tools\solidworks_codex\reports\after.json -Out tools\solidworks_codex\reports\delta.md -JsonOut tools\solidworks_codex\reports\delta.json
```

## Mates look created but assembly is still loose

Do not trust file existence or a mate count alone. Check:

- `inspect` mate type and suppressed state;
- mate participating component names;
- selection evidence from the live operation;
- component Transform/origin against the accepted placement contract;
- whether the component was fixed before or after mate creation;
- whether a verified mate network is available as functional connection evidence.

For a reusable check, write an `assembly-contract` manifest and run it against the inspect report.

## Live gate reports low memory, hidden windows, or crash

Symptoms include `timeout_after_<seconds>s`, `SLDWORKS.exe Responding=False`, high private memory, or generated `~$*.SLDPRT` / `~$*.SLDASM` lock files under `tools\solidworks_codex\live_fixture`.

Use a narrow process/lock check before rerunning heavy gates:

```powershell
$locks = Get-ChildItem -LiteralPath 'tools\solidworks_codex\live_fixture' -Recurse -Force -Filter '~$*' -ErrorAction SilentlyContinue | Select-Object -ExpandProperty FullName
$procs = Get-Process SLDWORKS -ErrorAction SilentlyContinue | Select-Object Id,PrivateMemorySize64,WorkingSet64,Responding,StartTime
[pscustomobject]@{LockFiles=$locks; Processes=$procs} | ConvertTo-Json -Depth 4
```

Then run live checks serially:

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
```

`CleanupStale` only removes known generated stale shaper directories. It should not touch `shaper_machine_v5`, `live_capability_suite`, user models, or unrelated workspace files. If SolidWorks repeatedly crashes, run the smaller checks first through the gate report rather than immediately rerunning the full shaper fixture.

## Live shaper status looks stale

The current stress fixture is `shaper_machine_v5`. Expected evidence in `tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json` includes `24 parts`, `58 components`, `19 MateLock layout stabilizers`, structural-reference fixed evidence only, attached detail-instance layout, `Transform2.ArrayData` placement readback, and `0 interference` when healthy. Treat MateLock as fixture-layout stabilization evidence, not as proof of complete mechanism DOF or motion sweep. If the report shows functional components fixed, stale display-strip detail instances, mate errors, placement drift, or interference, treat the fixture as a failing test rather than a cosmetic display issue.

## Public copy guard or repo-health fails

Run the gates directly and inspect the JSON:

```powershell
.\tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard.json
.\tools\solidworks_codex\swctl.ps1 repo-health -Out tools\solidworks_codex\reports\repo_health.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
```

Common causes are stale generated reports becoming Git-visible, personal paths leaking into docs, mojibake, or outdated docs that no longer mention current live/native validation behavior.
