# SolidWorks Codex Tooling

This directory contains the MCP server, CLI router, Python implementation scripts, runtime reports, and generated SolidWorks artifacts.

## Main Entry Points

- `mcp/server.cjs` exposes the 53 MCP tools, including `solidworks_component_insert`, `solidworks_part_feature_execute`, `solidworks_metadata_execute`, `solidworks_part_geometry_validate`, `solidworks_mate_group_execute`, `solidworks_tool_catalog`, `solidworks_handoff_bundle`, and `solidworks_worklog`.
- `swctl.ps1` is the stable local command router used by tests, CI, and human workflows.
- `scripts/` contains the implementation for inspection, understanding, execution, validation, handoff, and release gates.

## Execution Layer

Current write paths include guarded dimension edits, component state, component insertion, feature state, reviewed part feature specs, metadata writes, and mate group execution. `feature-state` reports operation role, change scope, changed feature, feature-count delta, feature-scoped parameter deltas, feature tree order deltas, and reviewed Feature Definition property before/after values from `-Manifest` definition specs so selective repair plans can distinguish suppression, reactivation, deletion, dimension edits, reviewed feature reorder actions, and definition edits. Execution should be followed by rebuild, inspect, compare, and task-specific validation.

`part-feature-execute` supports reviewed extrude cuts, basic holes, countersink holes, counterbore holes, slot cuts, pocket cuts, fillets, chamfers, linear/circular patterns, and mirrors. Hole variants report operation role, reviewed center/depth/diameter metadata, and HoleWizard call evidence; each operation reports selection/call evidence from named feature/entity selectors.

`set-dimension` reports dimension edit scope directly: dimension token, owner feature, owner document, before/after/requested values, delta, target reached, operation role, and change scope. `safe-set-dimension` keeps the full backup/inspect/compare/change-verify envelope around it.

`inspect` records document handoff evidence for active-document, specified native file, and provided-model-object paths. Reports carry the source, resolved path, doc type, and OpenDoc6 error/warning values so downstream diagnosis and repair plans know which model was actually read.

`component-insert` accepts an optional `attachment` object for standard/detail parts. The execution plan carries component role, attachment role, host component, host interface id, optional host/inserted selectors with native identity envelopes, mate group id, required mate types, selector handoff status, and an attachment status that hands off cleanly to mate group execution.

`interface-index` emits planar, cylindrical, slot/path, and coordinate-system selectors with stable ids, native identity envelopes, geometry fallbacks, and live identity capture protocols. Those protocols name the SolidWorks selection/readback calls, capture fields, patch target, and blocking policy used before mate execution trusts a selector.

`engineering-lite` converts inspect evidence into BOM rows, normalized drawing BOM rows, and optional `drawing_bom.csv` artifacts through `-OutDir` / MCP `out_dir`. The output carries item numbers, part numbers, configurations, quantities, materials, descriptions, and instances so material gaps and drawing handoff state are visible before release.

`assembly-repair-plan` emits an `affected_subgraph` for each action. The subgraph lists local components, affected mates, native file paths, and the diagnosis evidence used to choose the boundary, keeping mate repair focused on the damaged area.

`preflight` emits runtime hygiene evidence: memory budget, generated lock files, generated/report roots, screenshot roots, file counts, and cleanup scope. It treats memory-budget excess and generated lock files as blockers before live work continues.

## Validation Layer

The project uses validation profiles through `workflow-plan`: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release`. `runtime_budget` and `extra_checks` keep validation proportional.

Native `.SLDASM/.SLDPRT` readback is primary. STEP optional smoke is supplemental. Live validation checks native file readback, `part_geometry_readback`, `assembly_component_placements`, semantic mate participation, `mate_error: 1`, `0 interference`, and cleanup.

## Fixture Boundary

`shaper_machine_v5` is a simple-mechanism regression, not a showcase and not proof of general mechanism assembly. It exists to keep pressure on assembly diagnosis, interface indexing, local repair, mate groups, visual validation, native readback, and cleanup.

## Runtime Output

`reports/`, `backups/`, `exports/`, generated macros, and live fixture outputs are normally runtime artifacts. Promote them deliberately if they become tests or demo assets.
