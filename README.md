# SolidWorks Codex MCP

SolidWorks Codex MCP is a local MCP and CLI layer for AI-assisted SolidWorks work. Its job is to make the model understand the design first, then pick the right CAD action, then prove the result with evidence.

Compatibility anchors: `56 tools`, `model-understand`, `report-context`, `solidworks_handoff_bundle`, `solidworks_tool_catalog`, `solidworks_worklog`, and `docs/mcp-tools.md`.

Core loop:

```text
intent -> design intent -> interface graph -> execution spec -> SolidWorks action -> readback -> validation -> handoff
```

If you only read one file first, read `tools/solidworks_codex/reports/ai_capability_map.md` after generating it. That map tells the model what to understand, what to infer, what to execute, and when to use direct SolidWorks API calls instead of MCP wrappers.

## What This Project Is

- A local MCP server for SolidWorks inspection, planning, execution, validation, and handoff.
- A PowerShell CLI router, `tools/solidworks_codex/swctl.ps1`, for MCP and manual workflows.
- A Python layer for COM automation, report processing, mate planning, feature execution, and validation.
- A reasoning scaffold for AI: capability maps, workflow plans, interface indexes, mate intent specs, validation profiles, and worklogs.

## What This Project Is Not

- Not a screenshot-only demo.
- Not a raw API wrapper with no engineering semantics.
- Not allowed to accept scattered parts or decorative mates as finished assemblies.
- Not a substitute for final engineering sign-off or manufacturing release.

## Quick Anchor List

- `workflow-plan`
- `runtime budget`
- `backup`
- `rebuild`
- `compare`
- `change-verify`
- `assembly diagnosis`
- `interface indexing`
- `mate group`
- `visual evidence`
- `present/guarded`
- `.SLDASM/.SLDPRT`

The `solidworks_tool_catalog` entry is still useful when the model needs a quick schema inventory.
The `solidworks_handoff_bundle` entry is still useful when the model needs a resumable package.

## Repository Map

| Path | Purpose |
| --- | --- |
| `tools/solidworks_codex/mcp/server.cjs` | Local MCP stdio server and tool schemas. |
| `tools/solidworks_codex/swctl.ps1` | CLI router for MCP, tests, and manual CAD runs. |
| `tools/solidworks_codex/scripts/` | Python implementation for planning, inspection, execution, validation, reporting, and handoff. |
| `tests/solidworks_codex/` | Offline regression tests for tool contracts and report semantics. |
| `docs/mcp-tools.md` | GitHub-readable MCP tool manual with parameters, scope, and limits. |
| `docs/solidworks-codex-capability-gap-checklist.md` | Capability checklist and acceptance standard. |
| `docs/solidworks-automation-plan.md` | Historical implementation plan and remaining track notes. |

## Quick Start

1. Generate the AI capability map.
2. Inspect the current model or assembly.
3. Build a workflow plan.
4. Index interfaces and mate evidence.
5. Execute reviewed changes.
6. Rebuild, validate, and hand off.

### Generate The AI Capability Map

```powershell
.\tools\solidworks_codex\swctl.ps1 ai-capability-map `
  -Out tools\solidworks_codex\reports\ai_capability_map.md `
  -JsonOut tools\solidworks_codex\reports\ai_capability_map.json
```

### Inspect a Model

```powershell
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\inspect.json
```

### Validate the Result

```powershell
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\after.json
```

## Safety Model

| Layer | Guard |
| --- | --- |
| Intent | `workflow-plan`, `change-plan`, validation profiles, runtime budget, assumptions, non-goals. |
| Readback | `probe`, `inspect`, `model-understand`, `report-search`, `report-context`. |
| Interface graph | `interface-index`, `assembly-diagnose`, `assembly-review-pipeline`. |
| Execution | Reviewed specs, dry-run modes, named interfaces, immediate evidence reports. |
| Assembly | Mate planning, mate execution, interference checks, motion sweep lite. |
| Validation | Rebuild health, compare/change-verify, geometry contracts, visual evidence, engineering-lite. |
| Continuity | `worklog`, `handoff-bundle`, `ai-capability-map`. |
