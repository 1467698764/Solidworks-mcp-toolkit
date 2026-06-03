# SolidWorks Codex Usage Guide

The MCP wrapper currently exposes **35 MCP tools** across read-only inspection, analysis, handoff, guarded writes, export/verify, release gates, and the optional live SolidWorks gate.

This project is a general SolidWorks MCP/control layer. It does not try to replace engineering judgment with one rigid CAD template. It collects reviewable evidence from native `.SLDASM/.SLDPRT` models: components, features, dimensions, mates, transforms, spatial relationships, interference, mass, file locks, and runtime callbacks. A reasoning model can then choose an acceptance depth that matches the user intent.

The bullhead shaper is a stress test, not the project boundary. It exists because a hard mechanism exposes real failures in cuts, revolves, sketch selection, reopen/modify/rebuild persistence, mate creation/readback, component transforms, interference callbacks, and cleanup behavior. Lighter part work should not be blocked by full mechanism-release checks.

## Core rules

- Inspect model evidence before planning edits.
- Before feature creation, verify the active document, clear selection state, target sketch/entity, and expected feature consumer.
- Back up before writes; rebuild, inspect, compare, and verify after writes.
- Native `.SLDASM/.SLDPRT` artifacts are the main deliverables. STEP optional smoke can supplement export coverage but cannot replace native SolidWorks assembly validation.
- Do not globally force every heavy engineering check. Use validation profiles and task-specific extra checks.

## validation profiles

`tools/solidworks_codex/scripts/sw_validation_profiles.py` provides intent-scoped validation profiles. Every check has a layer, severity, reason, and evidence scope.

- layers: `geometry`, `assembly`, `engineering`, `mcp_quality`
- severities: `blocking`, `warning`, `not_applicable`
- runtime_budget: `fast`, `standard`, `strict`
- extra_checks: a reasoning model may add task-specific checks, but each extra check must include name/layer/severity/reason/evidence_scope.

Built-in profiles:

| Profile | Use case | Default blocking focus |
| --- | --- | --- |
| `draft_part` | quick draft or local experiment | native artifacts, rebuild health, requested part shape semantics |
| `single_part` | one part deliverable | part geometry/rebuild/semantic features; assembly checks are not_applicable |
| `assembly` | static assembly | mate semantics, component placements, static interference, functional adjacency |
| `mechanism_assembly` | sliding/rotating mechanism | assembly checks plus constraint/DOF intent, motion sweep collision, clearance tolerance screen |
| `engineering_release` | near-release engineering package | mechanism checks plus BOM, DFM/DFA, strength/stiffness, drawing/BOM readiness warnings |

This keeps validation proportional: simple work remains usable, while complex work can upgrade the profile or add extra_checks instead of making every draft fail release-grade gates.

## Read-only workflow

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_before.json
.\tools\solidworks_codex\swctl.ps1 summary -Report tools\solidworks_codex\reports\assembly_before.json -Out tools\solidworks_codex\reports\assembly_before.md
.\tools\solidworks_codex\swctl.ps1 model-understand -Report tools\solidworks_codex\reports\assembly_before.json -View spatial-assembly -Target "locating interfaces, editable dimensions, floating components, clearance, mate semantics, and manufacturing evidence" -Out tools\solidworks_codex\reports\understanding.md -JsonOut tools\solidworks_codex\reports\understanding.json
```

Allowing the command to launch SolidWorks is explicit:

```powershell
.\tools\solidworks_codex\swctl.ps1 start-inspect -Out tools\solidworks_codex\reports\assembly_before.json
```

## Guarded edit workflow

```powershell
.\tools\solidworks_codex\swctl.ps1 backup -Files 'C:\path\to\your\sample_machine.SLDASM','C:\path\to\changed_part.SLDPRT' -Out tools\solidworks_codex\reports\backup_before_change.json
.\tools\solidworks_codex\swctl.ps1 safe-set-dimension -Model 'C:\path\to\changed_part.SLDPRT' -Dimension 'D1@Sketch1@plate.SLDPRT' -ValueM 0.012 -Out tools\solidworks_codex\reports\safe_set_dimension.json
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_after.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\assembly_before.json -After tools\solidworks_codex\reports\assembly_after.json -Out tools\solidworks_codex\reports\assembly_delta.md -JsonOut tools\solidworks_codex\reports\assembly_delta.json
.\tools\solidworks_codex\swctl.ps1 change-verify -Report tools\solidworks_codex\reports\assembly_delta.json -AllowDimension 'D1@Sketch1@plate.SLDPRT'
```

## Assembly contract and model understanding

`assembly-contract` is a reusable offline gate for inspect reports. It checks document type, minimum component count, required component prefixes, Transform/origin tolerance, semantic mate type, mate suppression state, and expected participating components. Contract entries may set severity to `blocking`, `warning`, or `not_applicable`; warnings are reported without failing the command, while unknown severities fail so contracts stay reviewable. Component matching removes only SolidWorks instance suffixes such as `-1`, so hyphenated part names remain precise and substring pair matches are rejected.

```powershell
.\tools\solidworks_codex\swctl.ps1 assembly-contract `
  -Report tools\solidworks_codex\reports\assembly_before.json `
  -Manifest tools\solidworks_codex\reports\assembly_contract_manifest.json `
  -Out tools\solidworks_codex\reports\assembly_contract.json
```

`model-understand` must not be a placeholder. It cannot pass with only a component inventory or bounding-box proximity. A verified mate network may count as functional connection evidence only when mate semantics, selected entities, participating components, component index, and spatial model evidence are present.

## Live SolidWorks gate

Run the live gate only on a machine with SolidWorks and pywin32:

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
```

The underlying script flag is `--cleanup-stale`; `CleanupStale` is the PowerShell switch name. The gate is opt-in, serial, and attempts to keep SolidWorks hidden. It scans `tools/solidworks_codex/live_fixture/**/~$*` before startup and between checks.

Live gate layers:

- `live_session_smoke`: minimal COM/session/mate/interference/cleanup path.
- `live_capability_suite`: extrude, cut, revolve, revolved cut, sketch dimension read/modify/rebuild/save, assembly insertion, concentric mate, distance mate, interference callback, mass callback, close/cleanup, and selection-isolation evidence, and `assembly_component_placements` component Transform2/origin placement readback for the inserted assembly components.
- `complete_shaper_v5`: bullhead shaper stress test at `tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM` with report `tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json`.

Current shaper evidence:

- `24 parts`
- `58 components`
- `22 semantic mates`
- `21 restored/fixed primary components`
- primary component restore API: `Transform2.ArrayData`
- verified mate network
- mass callback available, assembly mass about `15.13 kg`
- interference callback available, `0 interference`
- empty validation failed list
- post cleanup has no `~$` lock files

`-CleanupStale` is bounded to old generated directories: `shaper_machine`, `shaper_machine_v2`, `shaper_machine_v3`, and `shaper_machine_v4`. It must not touch `shaper_machine_v5`, `live_capability_suite`, user models, or unrelated workspace files.

## Handoff workflow

```powershell
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 worklog -SessionName mechanical-interface-update -Action decision -Message "Use report-context and report-search before any write operation" -Artifact tools\solidworks_codex\reports\context.md -Next "backup target files before safe-set-dimension"
.\tools\solidworks_codex\swctl.ps1 handoff-bundle -Report tools\solidworks_codex\reports\assembly_before.json -FromReport tools\solidworks_codex\reports\worklog.jsonl -Target "current model evidence, constraints, clearance, and manufacturing gaps" -OutDir tools\solidworks_codex\reports\handoff\assembly-baseline
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

## Pre-commit checks

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
.\tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
```
