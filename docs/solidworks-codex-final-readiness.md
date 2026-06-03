# SolidWorks Codex Current Readiness Report

- Timestamp: `2026-06-03`
- Branch: `main`
- Current stance: evidence-first SolidWorks MCP/control layer with offline gates, MCP smoke, validation profiles, and opt-in live SolidWorks validation.

## What is considered ready

- 39 MCP tools are documented and routed through the local PowerShell/Python control layer.
- Offline unit tests cover report parsing, context/search/model-understand flows, guarded change verification, release gates, public-copy guard, live-gate validation logic, validation profiles, and fixture-level assembly contracts.
- Native `.SLDASM/.SLDPRT` artifacts are treated as the deliverable for CAD work; STEP optional smoke is only supplemental.
- Intent-scoped validation profiles exist: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release`.
- `runtime_budget` and `extra_checks` let the reasoning model scale validation without forcing full engineering release checks on every draft.

## Latest live SolidWorks evidence

Latest verified live capability suite:

```text
tools/solidworks_codex/live_fixture/live_capability_suite/capability_suite.SLDASM
tools/solidworks_codex/reports/live_capability_suite/live_capability_suite.json
```

Evidence summary:

- `ok: true`
- validation failed list empty
- `part_geometry_readback` present for four reopened native `.SLDPRT` files
- body count, bbox size, volume, and semantic solid-effect evidence checked for boss/cut/revolve/revolved cut operations
- `assembly_component_placements` solved origins match the accepted layout
- `mate_error: 1` on AddMate calls, which is SolidWorks AddMate no-error
- post-cleanup lock files empty

Simple mechanism regression fixture:

```text
tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM
tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json
```

This fixture should be read as a regression target with known limitations, not as a showcase. Current readiness claims should focus on the generic evidence it can exercise: native file creation, part feature readback, component placement/readback, semantic mate participation, fixed/floating policy, interference callback, model-understanding output, and cleanup. A passing JSON report is not enough if the SolidWorks window shows a scattered assembly or the mate graph is only fixture-stabilized.

Old fixture JSON should not be treated as proof after validator changes. The current direction is to replace fixture-specific placement confidence with general assembly diagnosis, interface indexing, mate-group planning, visual screenshot evidence, and local repair. Until those are implemented and live-verified, the project should not claim general mechanism assembly competence.

## Recommended real-model workflow

1. Run `preflight`.
2. Open the target `.SLDASM` or `.SLDPRT` in SolidWorks.
3. Run `inspect` or `session-snapshot`.
4. Run `model-understand` and `report-context` for the current task.
5. Choose a validation profile based on intent rather than applying every engineering gate globally.
6. Back up any file that may be modified.
7. Make one narrow change at a time.
8. Rebuild, inspect, compare, and use `change-verify`.
9. For assemblies, use `assembly-contract` to verify component placement, suppressed/fixed state, mate status/error evidence when reported, and semantic mate network.
10. For mechanisms or release-like work, run the appropriate live checks and profile-specific blocking checks.
11. Record decisions and evidence with `worklog` / `handoff-bundle`.
12. Run tests, public-copy guard, release-tree, and audit before commit.

## Open hardening areas

These are intentionally not claimed as solved globally:

- Full general DOF solver and motion sweep validation are profile-scoped targets, not universal default checks.
- DFM/DFA and strength/stiffness screens are currently lightweight evidence gates unless the task explicitly requests deeper engineering validation.
- The live capability suite proves a useful native feature/mate/geometry path, but broad CAD usefulness still depends on assembly diagnosis, interface indexing, local repair, mate groups, visual validation, and mechanism-lite checks. Named fixtures are regression cases, not the project identity.

## Key files

- usage: `docs/solidworks-codex-usage.md`
- architecture: `docs/architecture.md`
- troubleshooting: `docs/troubleshooting.md`
- control README: `tools/solidworks_codex/README.md`
- swctl: `tools/solidworks_codex/swctl.ps1`
- MCP server: `tools/solidworks_codex/mcp/server.cjs`
- validation profiles: `tools/solidworks_codex/scripts/sw_validation_profiles.py`
- live gate: `tools/solidworks_codex/scripts/sw_live_validation_gate.py`
- shaper fixture: `tools/solidworks_codex/scripts/sw_create_complete_shaper_fixture.py`
