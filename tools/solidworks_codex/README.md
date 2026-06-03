# SolidWorks Codex Control Layer

This directory contains the local control layer used by the MCP server and by direct PowerShell workflows.

## Responsibilities

- `swctl.ps1` is the stable command router for humans, tests, CI, and MCP.
- `mcp/server.cjs` exposes the 36 MCP tools and delegates to `swctl.ps1`, including MCP entries such as `solidworks_tool_catalog`, `solidworks_handoff_bundle`, and `solidworks_worklog`.
- `scripts/*.py` implement focused operations: inspect, compare, model understanding, validation profiles, guarded edits, worklog, handoff, live gates, and release gates.
- `sandbox/report_before.json` and `sandbox/report_after.json` are deterministic offline fixtures used by tests and demos.

## Workflow stance

The tools are designed for evidence-first mechanical CAD work:

1. inspect or session-snapshot;
2. model-understand / report-context / report-search;
3. choose validation profiles by intent (`draft_part`, `single_part`, `assembly`, `mechanism_assembly`, `engineering_release`);
4. backup before any write;
5. change one dimension, component state, or feature flow at a time;
6. rebuild, inspect, compare, and verify;
7. for assemblies, validate placement, part shape/feature semantics, suppressed/fixed state, mate error/status evidence when reported, and semantic mate network through `assembly-contract`;
8. record worklog and create handoff bundles for later AI turns.

The goal is not to force one CAD template or one output schema. The goal is to give a strong model enough SolidWorks evidence to reason flexibly and safely.

## Useful commands

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_before.json
.\tools\solidworks_codex\swctl.ps1 model-understand -Report tools\solidworks_codex\reports\assembly_before.json -View spatial-assembly -Target "constraints, transforms, clearance, hole patterns, and manufacturing evidence"
.\tools\solidworks_codex\swctl.ps1 assembly-contract -Report tools\solidworks_codex\reports\assembly_before.json -Manifest tools\solidworks_codex\reports\assembly_contract_manifest.json -Out tools\solidworks_codex\reports\assembly_contract.json
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
```

## Live SolidWorks validation

Offline tests prove syntax and report logic. Real CAD behavior is checked by the opt-in live gate:

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
```

Live deliverables are native `.SLDASM/.SLDPRT`; STEP optional smoke is not the primary acceptance criterion. The live capability suite checks `assembly_component_placements` component Transform2/origin placement readback and `part_geometry_readback` bbox/body/volume evidence from reopened native `.SLDPRT` files. SolidWorks AddMate `mate_error: 1` is treated as AddMate no-error, then verified with mate readback, component participation, and placement evidence. `assembly-contract` can also require part feature names and semantic counts so a model is not accepted as a plain block stack. The retained `shaper_machine_v5` fixture is a simple-mechanism regression case for native readback, mate participation, interference, model-understanding, and cleanup; it is not a showcase or proof that general mechanism assembly is solved. Current fixture reports must be regenerated after validator changes; a stale `ok: true` report is not proof.

Required mates between two fixed components fail `assembly-contract` by default unless the manifest explicitly sets `allow_fixed_fixed: true` for a reference/documentation mate.

`CleanupStale` is bounded to old generated fixture directories. The gate runs serially, scans `~$` lock files, and avoids unnecessary SolidWorks windows where possible.

## MCP entry point

```text
tools/solidworks_codex/mcp/server.cjs
```

Copy `examples/codex-mcp-config.example.toml` if you want to register it. Do not edit global Codex config automatically.

## Runtime artifacts

The following are generated and should normally stay out of Git:

- `reports/`
- `backups/`
- `exports/`
- generated `.swp.vba` macros
- live fixture output unless explicitly promoted
- logs and Python caches

`release-tree`, `public-copy-guard`, and `audit` check this before release.
