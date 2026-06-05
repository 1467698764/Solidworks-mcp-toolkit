# Contributing

This repository is a SolidWorks MCP/control layer. Contributions should improve the full evidence -> execution -> verification chain instead of adding isolated wrappers.

## Development Rules

- Keep public behavior aligned with the current `50 MCP tools` catalog.
- Prefer generic CAD mechanisms over fixture-specific assumptions.
- Treat `.SLDASM/.SLDPRT` native file readback as primary CAD evidence; STEP optional smoke is supplemental.
- Preserve safety around writes: backup, execute, rebuild, inspect, compare, and verify.
- Update docs and tests when a tool changes the user-visible workflow.

## Local Checks

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
.\scripts\verify-all.ps1
```

Use narrower offline test commands while developing, then run the full gate before commit. `audit` and `verify-all.ps1` are the release baseline.

## Generated Artifacts

Do not commit normal runtime output from:

- `tools/solidworks_codex/reports/`
- `tools/solidworks_codex/backups/`
- `tools/solidworks_codex/exports/`
- generated `.swp.vba` macros
- live fixture output unless explicitly promoted

## Pull Requests

Include:

- workflow problem solved
- changed commands or MCP tools
- safety and validation evidence
- tests run
- any remaining limits or live SolidWorks checks still needed
