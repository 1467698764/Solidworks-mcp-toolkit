# Architecture

## Layer Map

Contract terms for release gates: Layer map, Data flow, Safety model.

- **MCP server**: `tools/solidworks_codex/mcp/server.cjs` exposes 53 MCP tools and translates JSON arguments into local CLI commands.
- **CLI router**: `tools/solidworks_codex/swctl.ps1` provides stable PowerShell commands for scripts, CI, and human use.
- **Python control scripts**: `tools/solidworks_codex/scripts/` implement inspection, evidence modeling, execution, validation, handoff, and release gates.
- **SolidWorks boundary**: COM automation and generated macros touch the live SolidWorks process; offline tests validate parsing and orchestration without requiring SolidWorks.
- **Reports and artifacts**: `tools/solidworks_codex/reports/`, `backups/`, `exports/`, live fixture folders, and generated macros are runtime output unless promoted intentionally.

## Data Flow

1. `inspect` or `session-snapshot` reads the active model and writes structured JSON plus summaries.
2. Understanding tools build evidence graphs, risks, interface hypotheses, assembly diagnosis, local repair options, and mate groups.
3. Planning tools choose validation profiles and execution paths.
4. Execution tools perform controlled writes: dimensions, component state, component insert, feature state, part feature execute, metadata execute, or mate group execute.
5. Verification tools rebuild, inspect again, compare reports, check contracts, read native files, and produce blocking / warning / not_applicable findings.
6. Handoff tools preserve decisions, failed attempts, evidence, and next actions for the next model turn.

## Safety Model

Writes must be bounded, inspectable, and reversible when practical:

- use backups before file-modifying operations
- clear and verify SolidWorks selections before feature or mate creation
- rebuild before trusting geometry
- compare before/after reports
- require semantic evidence, not only success return codes
- use native `.SLDASM/.SLDPRT` readback for CAD acceptance

Validation profiles keep the gate proportional: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release` can scale with `runtime_budget` and `extra_checks`.

## Assembly Evidence

Assembly work is accepted by generic evidence, not by a single named fixture:

- `assembly_component_placements` from Transform2/origin readback
- semantic mate participation and suppression status
- `0 interference` where static clearance is required
- interface indexing for faces, axes, holes, slots, and expected contact/clearance regions
- local repair plans for missing, bad, or hostless components
- mate groups with selection validation before execution
- visual validation where text evidence is insufficient

`shaper_machine_v5` remains a simple-mechanism regression target. It is useful because it stresses native file readback, semantic mate participation, `mate_error: 1`, CleanupStale, and mechanism-like constraints, but it is not a showcase and not proof of general mechanism assembly competence.

## Release Gates

`verify-all.ps1` combines unit tests, Python compilation, Node syntax checks, MCP smoke, audit, release-tree, repo-health, github-readiness, and finalize. Public release checks also guard against stale docs, forbidden rank claims, unsafe generated artifacts, and missing workflow documentation.
