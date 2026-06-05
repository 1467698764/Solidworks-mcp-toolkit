# Demo

The demo area contains reproducible offline material for people who do not have SolidWorks open.

## Regenerate

```powershell
.\tools\solidworks_codex\swctl.ps1 offline-demo -OutDir docs\demo\offline
```

The generated bundle includes:

- `docs/demo/offline/README.md`
- `docs/demo/offline/tool_catalog.md`
- `docs/demo/offline/context.md`
- `docs/demo/offline/worklog.md`
- `docs/demo/offline/handoff/README.md`

## Purpose

The offline demo proves the handoff and reasoning layer: `report-context`, `worklog`, `handoff-bundle`, and `tool-catalog`. It does not prove live CAD execution. Use `live-gate` for native SolidWorks behavior.
