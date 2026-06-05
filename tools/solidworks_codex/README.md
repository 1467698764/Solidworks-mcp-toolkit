# SolidWorks Codex Tooling

This directory contains the MCP server, CLI router, Python implementation scripts, runtime reports, and generated SolidWorks artifacts.

## Main Entry Points

- `mcp/server.cjs` exposes the 53 MCP tools, including `solidworks_component_insert`, `solidworks_part_feature_execute`, `solidworks_metadata_execute`, `solidworks_part_geometry_validate`, `solidworks_mate_group_execute`, `solidworks_tool_catalog`, `solidworks_handoff_bundle`, and `solidworks_worklog`.
- `swctl.ps1` is the stable local command router used by tests, CI, and human workflows.
- `scripts/` contains the implementation for inspection, understanding, execution, validation, handoff, and release gates.

## Execution Layer

Current write paths include guarded dimension edits, component state, component insertion, feature state, reviewed part feature specs, metadata writes, and mate group execution. `feature-state` reports operation role, change scope, changed feature, feature-count delta, and feature-scoped parameter deltas so selective repair plans can distinguish suppression, reactivation, deletion, and dimension edits. Execution should be followed by rebuild, inspect, compare, and task-specific validation.

`inspect` records document handoff evidence for active-document, specified native file, and provided-model-object paths. Reports carry the source, resolved path, doc type, and OpenDoc6 error/warning values so downstream diagnosis and repair plans know which model was actually read.

`component-insert` accepts an optional `attachment` object for standard/detail parts. The execution plan carries component role, attachment role, host component, host interface id, mate group id, required mate types, and an attachment status that hands off cleanly to mate group execution.

## Validation Layer

The project uses validation profiles through `workflow-plan`: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release`. `runtime_budget` and `extra_checks` keep validation proportional.

Native `.SLDASM/.SLDPRT` readback is primary. STEP optional smoke is supplemental. Live validation checks native file readback, `part_geometry_readback`, `assembly_component_placements`, semantic mate participation, `mate_error: 1`, `0 interference`, and cleanup.

## Fixture Boundary

`shaper_machine_v5` is a simple-mechanism regression, not a showcase and not proof of general mechanism assembly. It exists to keep pressure on assembly diagnosis, interface indexing, local repair, mate groups, visual validation, native readback, and cleanup.

## Runtime Output

`reports/`, `backups/`, `exports/`, generated macros, and live fixture outputs are normally runtime artifacts. Promote them deliberately if they become tests or demo assets.
