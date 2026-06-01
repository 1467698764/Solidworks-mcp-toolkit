# SolidWorks Codex MCP

A practical SolidWorks MCP/control layer for general AI-assisted mechanical CAD work.

The project focuses on helping a strong model understand the current SolidWorks state before acting: components, dimensions, mates, transforms, spatial relationships, hole/manufacturing evidence, risks, and evidence gaps. It intentionally avoids a rigid "one prompt, one template" workflow.

## What this is

- A local MCP server plus PowerShell/Python control layer for SolidWorks.
- A report-first workflow for messy real assemblies where names, mates, and design intent are often incomplete.
- A guarded edit path: backup, one-variable change, rebuild, inspect, compare, and verify.
- A handoff system so future AI turns can continue from evidence instead of re-guessing the project.

## What makes it useful

- **35 conservative MCP tools** backed by a tested CLI path.
- **Model understanding, not just automation:** `model-understand` builds task-aware CAD evidence graphs with components, dimensions, mate evidence, transforms, spatial relationships, manufacturing hole groups, readiness, and evidence gaps.
- **Flexible reasoning:** `report-context`, `report-search`, `worklog`, `handoff-bundle`, and `tool-catalog` give the model enough context without forcing one fixed output schema or domain-specific workflow.
- **Mechanical CAD generality:** examples and fixtures target general assemblies: plates, housings, locating interfaces, hole patterns, fasteners, clearances, transforms, and manufacturability evidence.
- **Safety gates:** `preflight`, `audit`, `release-tree`, `public-copy-guard`, `repo-health`, `github-readiness`, and MCP smoke tests catch common release and runtime mistakes.

## Quick start

```powershell
cd <repo>
.\tools\solidworks_codex\install.ps1 -CheckOnly
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

Open a `.SLDASM` or `.SLDPRT` in SolidWorks, then capture evidence:

```powershell
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 model-understand `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -View spatial-assembly `
  -Target "current constraints, transforms, clearance, editable dimensions, hole patterns, and manufacturing evidence" `
  -Out tools\solidworks_codex\reports\understanding.md `
  -JsonOut tools\solidworks_codex\reports\understanding.json
.\tools\solidworks_codex\swctl.ps1 report-context `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -Target "current model evidence and open questions" `
  -Out tools\solidworks_codex\reports\context.md
```

## Typical workflow

1. `inspect` or `session-snapshot` to capture current state.
2. `model-understand` to build a compact evidence graph.
3. `report-search` to find uncertain dimensions, features, mates, or components.
4. `change-plan` if a modification is needed.
5. `safe-set-dimension` or another guarded write tool for one narrow change.
6. `rebuild`, `inspect`, `compare`, `change-verify`, and optionally `interference` / `export`.
7. `worklog` and `handoff-bundle` before pausing or switching AI sessions.

## MCP tool groups

### Read-only

- `solidworks_probe`
- `solidworks_inspect`
- `solidworks_report_summary`
- `solidworks_selection_report`

### Understanding and analysis

- `solidworks_model_understand`
- `solidworks_design_review`
- `solidworks_change_plan`
- `solidworks_report_search`
- `solidworks_report_context`

### Guarded writes

- `solidworks_backup`
- `solidworks_backup_status`
- `solidworks_restore_backup`
- `solidworks_set_dimension`
- `solidworks_safe_set_dimension`
- `solidworks_component_state`
- `solidworks_rebuild`

### Verification and export

- `solidworks_compare_reports`
- `solidworks_change_verify`
- `solidworks_interference_check`
- `solidworks_mass_properties`
- `solidworks_export`

### Handoff

- `solidworks_worklog`
- `solidworks_handoff_bundle`
- `solidworks_tool_catalog`
- `solidworks_offline_demo`

### Release gates

- `solidworks_preflight`
- `solidworks_audit`
- `solidworks_finalize`
- `solidworks_existing_mcp_tools`

Generate the exact current catalog with:

```powershell
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

## MCP configuration

Copy and adapt:

```text
examples/codex-mcp-config.example.toml
```

The MCP server entry point is:

```text
tools/solidworks_codex/mcp/server.cjs
```

This repository does not edit your global Codex config automatically.

## License

This project uses a custom non-commercial license. Personal learning, research,
evaluation, and non-commercial modification are allowed. Resale, paid hosting,
commercial bundling, and commercial CAD automation / MCP / AI-agent services
require separate written permission from the copyright holder. See `LICENSE`.

## Documentation

- Usage guide: `docs/solidworks-codex-usage.md`
- Architecture: `docs/architecture.md`
- Project principles for future AI sessions: `docs/project-principles.md`
- Troubleshooting: `docs/troubleshooting.md`
- Offline demo: `docs/demo/README.md`
- Copyable workflows: `docs/workflows/README.md`
- Capability matrix: `docs/capability-matrix.md`
- Prompt library: `docs/prompts.md`
- Release checklist: `docs/github-release-checklist.md`
- Changelog: `CHANGELOG.md`
- Roadmap: `ROADMAP.md`

## Verification before commit or release

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
```

Or run:

```powershell
.\scripts\verify-all.ps1
```

Generated reports, backups, exports, macros, caches, and logs are runtime artifacts and should not be staged unless intentionally promoted as fixtures or demo assets.

## Design stance

The goal is not to constrain AI into a narrow CAD macro template. The goal is to give a strong model enough accurate SolidWorks evidence to reason independently, ask for missing evidence when needed, and make small verified changes when appropriate.

Engineering review still matters. These tools improve evidence capture, reasoning, repeatability, and handoff; they do not replace final mechanical validation, simulation, tolerance analysis, or manufacturing review.

