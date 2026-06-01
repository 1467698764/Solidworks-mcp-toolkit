# SolidWorks Codex Control Layer

This directory contains the local control layer used by the MCP server and by direct PowerShell workflows.

## Responsibilities

- `swctl.ps1` is the stable command router for humans, tests, CI, and MCP.
- `mcp/server.cjs` exposes local commands such as `solidworks_tool_catalog`, `solidworks_handoff_bundle`, and `solidworks_worklog` as conservative MCP tools.
- `scripts/*.py` implement focused operations: inspect, compare, model understanding, guarded edits, worklog, handoff, and release gates.
- `sandbox/report_before.json` and `sandbox/report_after.json` are deterministic offline fixtures used by tests and demos.

## Workflow stance

The tools are designed for evidence-first mechanical CAD work:

1. inspect or session-snapshot;
2. model-understand / report-context / report-search;
3. backup before any write;
4. change one dimension or component state at a time;
5. rebuild, inspect, compare, and verify;
6. record worklog and create handoff bundles for later AI turns.

The goal is not to force one CAD template or one output schema. The goal is to give a strong model enough SolidWorks evidence to reason flexibly and safely.

## Useful commands

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_before.json
.\tools\solidworks_codex\swctl.ps1 model-understand -Report tools\solidworks_codex\reports\assembly_before.json -View spatial-assembly -Target "constraints, transforms, clearance, hole patterns, and manufacturing evidence"
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
```

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
- logs and Python caches

`release-tree` and `audit` check this before release.
