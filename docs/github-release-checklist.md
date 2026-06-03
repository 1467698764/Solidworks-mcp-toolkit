# GitHub Release Checklist

Use this before publishing or tagging a release.

## Positioning

- Lead with practical SolidWorks MCP workflows, not raw tool count.
- Mention the 37 conservative tools without making ranking claims.
- Highlight `model-understand`, `report-context`, `worklog`, `handoff-bundle`, and `tool-catalog` as differentiators.
- State clearly that write operations are guarded by backup/rebuild/compare/audit.

## Required checks

```powershell
.\tools\solidworks_codex\install.ps1 -CheckOnly
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
node tools\solidworks_codex\mcp\smoke-test.cjs
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
.\tools\solidworks_codex\swctl.ps1 finalize -Out docs\solidworks-codex-final-readiness.md
```

Or run the combined local gate:

```powershell
.\scripts\verify-all.ps1
```

## Do not commit

- `tools/solidworks_codex/reports/`
- `tools/solidworks_codex/backups/`
- generated `.swp.vba` macros
- local SolidWorks source models unless intentionally added as fixtures
- personal Codex config

## Good first demo

1. Run `tool-catalog`.
2. Run offline `report-context` on `tools/solidworks_codex/sandbox/report_after.json`.
3. Append a `worklog` decision.
4. Generate `handoff-bundle`.
5. Run `audit`.

This demonstrates the non-template workflow even without a live SolidWorks instance.
