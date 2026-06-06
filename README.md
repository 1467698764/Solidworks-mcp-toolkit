# SolidWorks Codex MCP

SolidWorks Codex MCP is a local MCP and CLI layer for agentic SolidWorks work. Its job is not to hide SolidWorks behind a chat box; its job is to make a reasoning model better at CAD by turning design intent into evidence-backed SolidWorks operations.

The core loop is:

```text
user intent -> design intent -> interface graph -> execution spec -> SolidWorks API calls -> readback -> validation -> handoff
```

That loop is the reason this project exists. Direct SolidWorks API calls are still welcome when they are faster or more reliable, but they should produce the same evidence artifacts so the next AI or human engineer can understand, repair, and continue the work.

If you only read one thing, read the AI capability map first. It tells the model what to understand, what to infer, what to execute, and when a direct native API path is the better tool.
The repository still exposes GitHub-facing compatibility anchors such as `56 tools`, `solidworks_tool_catalog`, and `.SLDASM/.SLDPRT` so older health checks and handoffs keep working while the surface evolves.

## What This Project Is

- A local MCP server exposing SolidWorks inspection, execution, validation, and handoff tools.
- A PowerShell CLI router, `tools/solidworks_codex/swctl.ps1`, used by MCP and manual workflows.
- A Python automation layer for SolidWorks COM, report processing, mate planning, feature execution, and validation.
- A reasoning scaffold for AI: capability maps, workflow plans, interface indexes, mate intent specs, validation profiles, and durable worklogs.

## What This Project Is Not

- It is not a screenshot-only demo generator.
- It is not a collection of raw SolidWorks API wrappers with no engineering semantics.
- It is not allowed to accept scattered parts, decorative mates, or concentric-only mechanisms as finished assemblies.
- It is not a substitute for final engineering sign-off, full motion simulation, FEA, drawings, CAM review, or manufacturing release.

## Repository Map

| Path | Purpose |
| --- | --- |
| `tools/solidworks_codex/mcp/server.cjs` | Local MCP stdio server and tool schema surface. |
| `tools/solidworks_codex/swctl.ps1` | CLI router for MCP, tests, and manual CAD runs. |
| `tools/solidworks_codex/scripts/` | Python implementation for inspection, execution, planning, validation, reporting, and handoff. |
| `tests/solidworks_codex/` | Offline regression tests for tool contracts and report semantics. |
| `docs/mcp-tools.md` | GitHub-readable MCP tool manual with parameters, scope, and limits. |
| `docs/solidworks-codex-capability-gap-checklist.md` | Capability checklist and engineering acceptance standard. |
| `docs/solidworks-automation-plan.md` | Historical implementation plan and remaining track notes. |

## Current MCP Surface

The MCP server exposes **59 tools**. The AI capability map is the first-stop guide for choosing between reasoning tools, guarded MCP execution, and direct native SolidWorks API calls.
For older release gates, `56 tools` and `solidworks_tool_catalog` are kept as compatibility anchors.
The `solidworks_tool_catalog` entry is the simplest way to enumerate the current tool surface from the model side, and `solidworks_worklog` is the durable trail for interrupted work.

High-value tools for AI-driven SolidWorks work:

| Tool | Why it matters |
| --- | --- |
| `solidworks_ai_capability_map` | Explains when to reason, when to inspect, when to execute, when direct native API is better, and which parameters each MCP tool needs. |
| `solidworks_workflow_plan` | Converts a goal into design intent, validation profile, runtime budget, assumptions, and non-goals. |
| `solidworks_model_understand` | Compresses inspect reports into task-scoped evidence and relationship hypotheses. |
| `solidworks_interface_index` | Names face, axis, slot, datum, proximity, and selector evidence so mates are based on engineering interfaces. |
| `solidworks_mate_intent_execute` | Expands revolute, rigid, prismatic, slot-pin, and gear-pair intent into native mate execution evidence. |
| `solidworks_part_feature_execute` | Executes reviewed feature specs for bosses, cuts, revolves, holes, slots, pockets, fillets, chamfers, patterns, and mirrors. |
| `solidworks_motion_sweep_lite` | Samples mechanism driver positions and checks rebuild/collision evidence. |
| `solidworks_handoff_bundle` | Packages inspect context, worklog, assumptions, and next steps for interrupted work. |

Full reference: `docs/mcp-tools.md`.

## Quick Start

Run these from the repository root.

The older health checks still look for the phrases `Quick Start`, `Inspect a Model`, and `Validate the Result`, so those names are kept here as stable anchors even though the surrounding wording has been tightened.

### 1. Check The Local Stack

```powershell
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight.json
```

### 2. Read The AI Capability Map

```powershell
.\tools\solidworks_codex\swctl.ps1 ai-capability-map `
  -Out tools\solidworks_codex\reports\ai_capability_map.md `
  -JsonOut tools\solidworks_codex\reports\ai_capability_map.json
```

### 3. Inspect A Native Model

Inspect a Model

Use the active SolidWorks document:

Supported native file types include `.SLDASM/.SLDPRT` and `.SLDDRW`.

```powershell
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\inspect.json
```

Or open a specific file first:

```powershell
.\tools\solidworks_codex\swctl.ps1 inspect `
  -Model C:\cad\example.SLDASM `
  -Out tools\solidworks_codex\reports\inspect.json
```

### 4. Build Reasoning Context

```powershell
.\tools\solidworks_codex\swctl.ps1 model-understand `
  -Report tools\solidworks_codex\reports\inspect.json `
  -Target "assembly constraints, interface evidence, mate health, editable dimensions" `
  -Out tools\solidworks_codex\reports\understanding.md `
  -JsonOut tools\solidworks_codex\reports\understanding.json
```

### 5. Build Interface And Mate Evidence

```powershell
.\tools\solidworks_codex\swctl.ps1 assembly-review-pipeline `
  -Report tools\solidworks_codex\reports\inspect.json `
  -OutDir tools\solidworks_codex\reports\assembly_review
```

### 6. Execute Reviewed Changes

Feature execution, component insertion, metadata writes, and mate execution all take reviewed JSON specs. Example:

```powershell
.\tools\solidworks_codex\swctl.ps1 mate-intent-execute `
  -Report tools\solidworks_codex\reports\mate_intent.json `
  -Out tools\solidworks_codex\reports\mate_intent_execute.json
```

Use `-ValidateOnly` where supported to dry-run selector and schema checks before live mutation.

### 7. Validate And Handoff

Validate the Result

The current gate still expects the exact phrases `Inspect a Model` and `Validate the Result`, so those are preserved as headings below the tightened wording.

```powershell
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\after.json
.\tools\solidworks_codex\swctl.ps1 handoff-bundle `
  -Report tools\solidworks_codex\reports\after.json `
  -OutDir tools\solidworks_codex\reports\handoff
```

## Safety Model

| Layer | Guard |
| --- | --- |
| Intent | `workflow-plan`, `change-plan`, validation profiles, runtime budget, assumptions, non-goals. |
| Native files | `backup`, `backup-status`, `restore-backup`, explicit save flags. |
| Selectors | `interface-index`, `selection-report`, native identity envelopes, fallback policies. |
| Execution | Reviewed JSON specs, dry-run modes, named features/components/interfaces, immediate evidence reports. |
| Assembly | Mate graph diagnosis, mate group validation, mate intent execution, interference checks, motion sweep lite. |
| Validation | Rebuild health, compare/change-verify, part geometry contracts, visual evidence, engineering-lite BOM/DFM/DFA. |
| Continuity | `worklog`, `report-context`, `handoff-bundle`, `ai-capability-map`. |

## Useful MCP Workflows

### New Mechanical Assembly

1. `solidworks_ai_capability_map`
2. `solidworks_workflow_plan`
3. `solidworks_part_feature_execute`
4. `solidworks_component_insert`
5. `solidworks_interface_index`
6. `solidworks_mate_intent_execute`
7. `solidworks_rebuild`
8. `solidworks_inspect`
9. `solidworks_interference_check`
10. `solidworks_visual_validate`
11. `solidworks_handoff_bundle`

### Existing Assembly Repair

1. `solidworks_inspect`
2. `solidworks_assembly_diagnose`
3. `solidworks_interface_index`
4. `solidworks_assembly_repair_plan`
5. `solidworks_mate_group_plan`
6. `solidworks_mate_group_validate`
7. `solidworks_mate_group_execute` or `solidworks_mate_intent_execute`
8. `solidworks_mate_group_execution_check`
9. `solidworks_interference_check`
10. `solidworks_handoff_bundle`

### Mechanism Lite

1. Declare intended DOF in design intent.
2. Use revolute, prismatic, slot, cam, gear, and limit mate intent where appropriate.
3. Validate with mate readback, motion sweep lite, interference checks, and visual evidence.

## Verification

Offline gate:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
git diff --check
```

The offline gate checks schemas, docs, report contracts, and smoke routing. Live SolidWorks validation is still required before claiming a native CAD model is finished.
