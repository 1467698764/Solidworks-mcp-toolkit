# SolidWorks Codex MCP

A practical SolidWorks MCP/control layer for real mechanical CAD work. The project is not a single fixture generator and not a rigid modeling template. It helps a strong model understand current SolidWorks evidence, act through guarded execution paths, and verify native CAD results.

## Current Scope

- **53 MCP tools** exposed by `tools/solidworks_codex/mcp/server.cjs` and routed through `swctl.ps1` plus Python scripts.
- General SolidWorks MCP coverage for parts, assemblies, dimensions, features, mates, Transform2/origin placement, interference, mass properties, and native `.SLDASM/.SLDPRT` readback.
- Execution-layer support for component insertion, part feature execution, metadata writes, component state changes, dimension edits, and mate group planning/selection/validation/execution checks.
- Evidence-first handoff through `inspect`, `model-understand`, `assembly-diagnose`, `interface-index`, `report-context`, `worklog`, and `handoff-bundle`.

## Quick Start

```powershell
cd <repo>
.\tools\solidworks_codex\install.ps1 -CheckOnly
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

After opening a `.SLDASM` or `.SLDPRT` in SolidWorks:

```powershell
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 model-understand `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -View spatial-assembly `
  -Target "constraints, transforms, clearance, editable dimensions, hole patterns, manufacturing evidence" `
  -Out tools\solidworks_codex\reports\understanding.md `
  -JsonOut tools\solidworks_codex\reports\understanding.json
```

## Workflow

1. Capture state with `inspect` or `session-snapshot`.
2. Build evidence with `model-understand`, `assembly-diagnose`, and `interface-index`.
3. Choose validation profiles through `workflow-plan`: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, or `engineering_release`, with task-specific `runtime_budget` and `extra_checks`.
4. Execute through guarded tools such as `safe-set-dimension`, `component-insert`, `part-feature-execute`, `metadata-execute`, or `mate-group-execute`.
5. Verify with `rebuild`, `inspect`, `compare`, `change-verify`, `assembly-contract`, `interference`, and opt-in `live-gate` when real SolidWorks evidence is required.
6. Preserve multi-turn context with `worklog` and `handoff-bundle`.

## Boundaries

- `shaper_machine_v5` is a simple-mechanism regression fixture. It is not a showcase and not proof that general mechanism assembly is solved.
- Native `.SLDASM/.SLDPRT` files are the CAD deliverables. STEP optional smoke is supplemental.
- `mate_error: 1` is treated as SolidWorks AddMate no-error only when followed by mate readback, component participation, placement, suppression, and interference evidence.
- Required mates between two fixed components fail by default unless `assembly-contract` receives `allow_fixed_fixed: true`.

## Documentation

- Usage guide: `docs/solidworks-codex-usage.md`
- Architecture: `docs/architecture.md`
- Principles: `docs/project-principles.md`
- Troubleshooting: `docs/troubleshooting.md`
- Workflows: `docs/workflows/README.md`
- Offline demo: `docs/demo/README.md`
- Capability matrix: `docs/capability-matrix.md`
- Prompt library: `docs/prompts.md`
- Roadmap: `ROADMAP.md`
- Execution checklist: `docs/solidworks-codex-capability-gap-checklist.md`

## Verification

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
.\scripts\verify-all.ps1
```

Generated reports, backups, exports, macros, caches, and logs normally stay out of Git unless promoted as fixtures or demo assets.
