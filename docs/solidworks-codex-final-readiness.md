# SolidWorks Codex Current Readiness Report

- Timestamp: `2026-06-04T17:29:25`
- Branch: `main`
- Current stance: evidence-first SolidWorks MCP/control layer with offline gates, MCP smoke, validation profiles, and opt-in live SolidWorks validation.
- Audit OK: `True`
- Preflight OK: `True`

## What is considered ready

- 45 MCP tools are documented and routed through the local PowerShell/Python control layer.
- Offline unit tests cover report parsing, context/search/model-understand flows, guarded change verification, release gates, public-copy guard, live-gate validation logic, validation profiles, and fixture-level assembly contracts.
- Native `.SLDASM/.SLDPRT` artifacts are treated as the deliverable for CAD work; STEP optional smoke is only supplemental.
- Intent-scoped validation profiles exist: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release`.
- `runtime_budget` and `extra_checks` let the reasoning model scale validation without forcing full engineering release checks on every draft.
- `model-understand` fuses feature-tree evidence with explicit `mate_like_features` readback, so sparse feature rows do not hide semantic mate participation or underconnected constraint networks.

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
- native file readback covers body count, bbox size, volume, and semantic solid-effect evidence for boss/cut/revolve/revolved cut operations
- `assembly_component_placements` solved origins match the accepted layout
- `mate_error: 1` on AddMate calls, which is SolidWorks AddMate no-error
- interference callback should report `0 interference` for static acceptance
- post-cleanup lock files empty

Simple-mechanism regression fixture:

```text
tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM
tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json
```

This fixture should be read as a regression target with known limitations, not as a showcase. Current readiness claims should focus on the generic evidence it can exercise: native file creation, part feature readback, component placement/readback, semantic mate participation, fixed/floating policy, interference callback, model-understanding output, and cleanup. A passing JSON report is not enough if the SolidWorks window shows a scattered assembly or the mate graph is only fixture-stabilized.

Old fixture JSON should not be treated as proof after validator changes. The current direction is to replace fixture-specific placement confidence with general assembly diagnosis, interface indexing, mate groups, visual validation, and local repair. Until those are implemented and live-verified, the project should not claim general mechanism assembly competence.

## Capabilities
- preflight environment check
- session snapshot: inspect + summary + issue report
- read-only assembly/part inspection
- Markdown summary generation
- issue/risk report generation
- timestamped backup
- single-dimension modification
- rebuild
- export by target suffix
- mass properties
- before/after report comparison
- component hide/show/suppress/unsuppress/fix/float
- interference-check entry point
- selection report for preselected entities
- preselected-entity mate macro generation
- common part template macro generation
- local MCP wrapper
- report search for messy component/dimension/feature names
- freeform report context packs for handoff and non-template reasoning
- durable multi-turn worklog for decisions, verification, failures, and next steps
- handoff bundles with inspect report, context, worklog, README, and manifest
- MCP tool catalog for discoverability and workflow selection
- GitHub release readiness gate with README, license, installer, CI, and config example
- offline demo bundle for five-minute public evaluation
- public copy guard to prevent rank-boasting and overclaiming in release docs
- repository health checks for issue templates, PR template, demo bundle, and verify-all
- offline audit gate

## Recommended real-model workflow
1. Run preflight.
2. Open the target assembly or part in SolidWorks.
3. Run session-snapshot with a descriptive name.
4. Record important assumptions and decisions with worklog.
5. Generate a handoff-bundle before pausing, switching tasks, or committing.
6. Use tool-catalog when choosing the next MCP tool instead of relying on memory.
7. Run github-readiness before publishing to GitHub.
8. Read summary.md and issue_report.md.
9. Back up the assembly and any parts that may be modified.
10. Make one narrow change at a time: dimension, component state, generated macro, or template part.
11. Rebuild and inspect again.
12. Compare before/after reports.
13. Export deliverables if needed.
14. Run audit before commit or handoff.

## Open hardening areas

These are intentionally not claimed as solved globally:

- Full general DOF solver and motion sweep validation are profile-scoped targets, not universal default checks.
- DFM/DFA and strength/stiffness screens are currently lightweight evidence gates unless the task explicitly requests deeper engineering validation.
- The live capability suite proves a useful native feature/mate/geometry path, but broad CAD usefulness still depends on assembly diagnosis, interface indexing, local repair, mate groups, visual validation, and mechanism-lite checks. Named fixtures are regression cases, not the project identity.

## Key files
- usage: `docs/solidworks-codex-usage.md`
- readme: `tools/solidworks_codex/README.md`
- swctl: `tools/solidworks_codex/swctl.ps1`
- mcp_server: `tools/solidworks_codex/mcp/server.cjs`
- audit: `tools/solidworks_codex/reports/audit_latest.json`

## Verification summary
- `required`: `True`
- `py_compile`: `True`
- `guide_commands`: `True`
- `compare_fixture`: `True`
- `mcp_smoke`: `True`
- `session_snapshot`: `True`
- `design_tools`: `True`
- `report_search`: `True`
- `report_context`: `True`
- `worklog`: `True`
- `handoff_bundle`: `True`
- `tool_catalog`: `True`
- `github_readiness`: `True`
- `public_copy_guard`: `True`
- `repo_health`: `True`
- `release_tree`: `True`
- `preflight`: `True`
