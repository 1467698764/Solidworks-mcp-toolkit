# Contributing

Contributions should preserve the core design: safe, inspectable, multi-turn SolidWorks automation.

## Development loop

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
python -m py_compile (Get-ChildItem tools\solidworks_codex\scripts\*.py | ForEach-Object FullName)
node --check tools\solidworks_codex\mcp\server.cjs
node --check tools\solidworks_codex\mcp\smoke-test.cjs
.\tools\solidworks_codex\swctl.ps1 audit
```

## Rules for new tools

1. Prefer read-only analysis unless a write is necessary.
2. Add a deterministic offline test.
3. Add CLI and MCP wiring if the feature should be public.
4. Update usage docs and tool catalog behavior.
5. Add audit coverage.
6. Keep generated outputs out of git.

## Naming

Use stable, explicit names:

- CLI commands: `kebab-case`
- MCP tools: `solidworks_snake_case`
- Python scripts: `sw_<feature>.py`
