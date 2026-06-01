# Demo

Generate the offline demo bundle:

```powershell
.\tools\solidworks_codex\swctl.ps1 offline-demo -OutDir docs\demo\offline
```

The demo uses the fixture inspect report in `tools/solidworks_codex/sandbox/report_after.json` and does not require SolidWorks to be open.

It demonstrates:

- `tool-catalog`
- `report-context`
- `worklog`
- `handoff-bundle`

This is the recommended first GitHub demo because it shows the project's non-template differentiator in five minutes.
