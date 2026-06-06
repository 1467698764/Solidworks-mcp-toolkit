# SolidWorks Codex MCP

SolidWorks Codex MCP is a local, evidence-first toolchain for inspecting and safely editing SolidWorks models through MCP and PowerShell/Python automation.

It is built for agentic CAD work where every mutation should have a source model, a reviewed selector/spec, a backup path, execution evidence, rebuild evidence, and follow-up validation.

## What It Can Do

- Inspect active or specified `.SLDASM/.SLDPRT` and `.SLDDRW` documents.
- Search and summarize inspect reports for components, dimensions, features, mates, interfaces, and risks.
- Plan CAD workflows from a user goal with validation profile, runtime budget, assumptions, and rebuild authorization gates.
- Execute guarded edits: dimensions, component state, component insertion, feature state, part features, metadata, and mate groups.
- Diagnose assemblies: component inventory, mate graph, bad mates, isolated components, bbox proximity, standard-part host gaps, and rollback scope.
- Validate outputs with rebuild health, report compare, change verification, geometry contracts, interference checks, motion sweep lite, visual evidence, and engineering-lite BOM/DFM/DFA review.
- Produce worklogs and handoff bundles so interrupted work can resume from evidence instead of memory.
- Use interface indexing to turn inspect evidence into face, axis, proximity, standard-part, and suppression candidates for downstream mate planning.

## What It Is Not

- It is not a magic model generator that guesses correct faces, axes, mates, or dimensions without evidence.
- It is not a replacement for final engineering review, manufacturing sign-off, or full motion/FEA analysis.
- It does not treat a demo fixture as proof of general CAD correctness.
- It should not write native files without backup and validation gates.

## Repository Map

| Path | Purpose |
| --- | --- |
| `tools/solidworks_codex/mcp/server.cjs` | MCP server exposing the SolidWorks Codex tools. |
| `tools/solidworks_codex/swctl.ps1` | Local CLI router used by MCP, tests, and manual workflows. |
| `tools/solidworks_codex/scripts/` | Python implementations for inspection, execution, validation, planning, and reports. |
| `tests/solidworks_codex/` | Offline regression tests for tool behavior and report contracts. |
| `docs/mcp-tools.md` | Human-readable MCP tool reference with parameters, scope, and limits. |
| `docs/solidworks-automation-plan.md` | Long-running implementation plan. |
| `docs/solidworks-codex-capability-gap-checklist.md` | Capability checklist and remaining gap tracker. |

## Quick Start

### 1. Run Preflight

```powershell
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
```

### 2. Inspect a Model

Use an already-open SolidWorks document:

```powershell
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\inspect.json
```

Or inspect a specific model:

```powershell
.\tools\solidworks_codex\swctl.ps1 inspect `
  -Model C:\path\to\model.SLDASM `
  -Out tools\solidworks_codex\reports\inspect.json
```

### 3. Build Task Context

```powershell
.\tools\solidworks_codex\swctl.ps1 model-understand `
  -Report tools\solidworks_codex\reports\inspect.json `
  -Target "mate errors, interfaces, editable dimensions, clearance" `
  -Out tools\solidworks_codex\reports\understanding.md `
  -JsonOut tools\solidworks_codex\reports\understanding.json
```

### 4. Plan Before Editing

```powershell
.\tools\solidworks_codex\swctl.ps1 workflow-plan `
  -Target "repair hostless fastener mates and verify clearance" `
  -Out tools\solidworks_codex\reports\workflow_plan.md `
  -JsonOut tools\solidworks_codex\reports\workflow_plan.json
```

### 5. Back Up Before Mutation

```powershell
.\tools\solidworks_codex\swctl.ps1 backup `
  -Files C:\path\to\part.SLDPRT,C:\path\to\assembly.SLDASM `
  -Out tools\solidworks_codex\reports\backup.json
```

### 6. Execute One Reviewed Change

Example: safe dimension edit.

```powershell
.\tools\solidworks_codex\swctl.ps1 safe-set-dimension `
  -Model C:\path\to\part.SLDPRT `
  -Dimension "D1@Sketch1@part.SLDPRT" `
  -ValueM 0.025 `
  -OutDir tools\solidworks_codex\reports\dimension_edit
```

### 7. Validate the Result

```powershell
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\after.json
.\tools\solidworks_codex\swctl.ps1 compare `
  -Before tools\solidworks_codex\reports\before.json `
  -After tools\solidworks_codex\reports\after.json `
  -JsonOut tools\solidworks_codex\reports\delta.json
.\tools\solidworks_codex\swctl.ps1 change-verify `
  -Report tools\solidworks_codex\reports\delta.json `
  -AllowDimension "D1@Sketch1@part.SLDPRT" `
  -Out tools\solidworks_codex\reports\change_verify.json
```

## MCP Tool Reference

The MCP server currently exposes **56 tools**. See the full tool manual:

- `docs/mcp-tools.md`

The manual lists each tool with:

- capability scope;
- practical upper limits;
- required parameters;
- optional parameters;
- common safety notes.

Useful MCP utility tools in this area include `solidworks_tool_catalog`, `solidworks_report_context`, `solidworks_worklog`, and `solidworks_handoff_bundle`.

Their CLI names are `tool-catalog`, `report-context`, `worklog`, and `handoff-bundle`.

## Practical Workflows

### Existing Assembly Diagnosis

1. `solidworks_inspect`
2. `solidworks_assembly_diagnose`
3. `solidworks_interface_index`
4. `solidworks_assembly_repair_plan`
5. `solidworks_mate_group_plan`
6. `solidworks_mate_group_validate`
7. `solidworks_mate_group_execute`
8. `solidworks_mate_group_execution_check`
9. `solidworks_interference_check`
10. `solidworks_visual_validate`

### Single-Part Feature Editing

1. `solidworks_inspect`
2. `solidworks_backup`
3. `solidworks_part_feature_execute` with a reviewed JSON spec
4. `solidworks_rebuild`
5. `solidworks_inspect`
6. `solidworks_part_geometry_validate`
7. `solidworks_change_verify`

### Interrupted Work Handoff

1. `solidworks_worklog`
2. `solidworks_report_context`
3. `solidworks_handoff_bundle`

## Safety Model

| Layer | Gate |
| --- | --- |
| File safety | `backup`, `backup-status`, `restore-backup` |
| Selector safety | `selection-report`, `mate-selection-check`, native identity envelopes |
| Execution safety | reviewed specs, exact feature/component names, dry-run modes |
| Rebuild safety | `rebuild` with health evidence |
| Delta safety | `compare` and `change-verify` |
| Assembly safety | mate graph checks, interference checks, visual validation |
| Handoff safety | worklog and handoff bundle |

## Verification

Run the offline gate:

```powershell
$py = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
& $py -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
git diff --check
```

## Current Project Trackers

- Plan: `docs/solidworks-automation-plan.md`
- Capability checklist: `docs/solidworks-codex-capability-gap-checklist.md`
- MCP manual: `docs/mcp-tools.md`
