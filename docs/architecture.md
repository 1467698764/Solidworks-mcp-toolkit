# Architecture

SolidWorks Codex MCP is a conservative control layer for multi-turn CAD work. It favors inspectable state, narrow edits, and reproducible handoff over a large unguarded API surface.

## Layer map

```text
Codex / MCP client
  -> tools/solidworks_codex/mcp/server.cjs
  -> tools/solidworks_codex/swctl.ps1
  -> tools/solidworks_codex/scripts/*.py
  -> SolidWorks COM automation or offline JSON fixtures
  -> reports, handoff bundles, exports, or generated macros
```

## Runtime boundaries

- `server.cjs` exposes MCP tools and translates tool arguments into `swctl.ps1` commands.
- `swctl.ps1` is the stable command router used by humans, tests, CI, and MCP.
- Python scripts implement focused operations: inspect, summary, compare, worklog, handoff, release gates, and guarded write helpers.
- SolidWorks COM is only touched by commands that need live model state or model mutation. Offline gates use fixtures and generated reports.

## Data flow

1. Read-only commands produce JSON or Markdown reports.
2. Analysis commands consume inspect/session reports and generate context, search results, design reviews, change plans, or handoff bundles.
3. Write commands stay narrow: backup first, one dimension or component state at a time, rebuild, inspect, compare.
4. Release commands validate the repository itself: GitHub readiness, repo health, public copy guard, release-tree, audit, and finalize.

## Safety model

- Generated artifacts go under ignored runtime directories unless intentionally promoted as fixtures or demo assets.
- Real CAD edits should be backed up, rebuilt, inspected, and compared before saving or committing.
- Macro generation creates reviewable `.swp.vba` text; it does not run macros automatically.
- `release-tree` checks that reports, backups, exports, generated macros, caches, logs, and personal config paths are not Git-visible.
- Public copy guard prevents rank-boasting language in release-facing files.

## Handoff model

The project is designed for long-running work where a future Codex turn must understand current evidence. `report-context`, `worklog`, `handoff-bundle`, and `tool-catalog` preserve facts, decisions, and next-step options without forcing a fixed template workflow.

## Offline evaluation

The repository includes offline fixtures and a static demo bundle so CI and reviewers can exercise the reasoning, handoff, and release gates without SolidWorks installed. Live SolidWorks remains necessary for real COM inspection, rebuild, export, mass properties, and model mutation.

## Extension points

- Add new operations as focused Python scripts first.
- Route them through `swctl.ps1` with explicit parameters.
- Expose MCP tools only after there is a CLI path and test coverage.
- Add release/audit coverage for new public behavior.
