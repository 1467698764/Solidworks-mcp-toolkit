# Workflows

## Offline Documentation Demo

```powershell
.\tools\solidworks_codex\swctl.ps1 offline-demo -OutDir docs\demo\offline
```

The offline demo shows report-context, worklog, handoff-bundle, and tool-catalog without requiring SolidWorks.

## First Real Assembly Pass

```powershell
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName first-pass
.\tools\solidworks_codex\swctl.ps1 model-understand -Report <inspect.json> -View spatial-assembly -Target "placement, mates, interfaces, clearance, manufacturing evidence"
.\tools\solidworks_codex\swctl.ps1 assembly-diagnose -Report <inspect.json> -Out tools\solidworks_codex\reports\assembly_diagnosis.json
.\tools\solidworks_codex\swctl.ps1 interface-index -Report <inspect.json> -Out tools\solidworks_codex\reports\interfaces.json
```

## Guarded Edit

```powershell
.\tools\solidworks_codex\swctl.ps1 backup -Out tools\solidworks_codex\reports\backup.json
.\tools\solidworks_codex\swctl.ps1 safe-set-dimension -DimensionName <name> -Value <meters> -Out tools\solidworks_codex\reports\safe_set_dimension.json
.\tools\solidworks_codex\swctl.ps1 rebuild
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\after.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\before.json -After tools\solidworks_codex\reports\after.json -JsonOut tools\solidworks_codex\reports\delta.json
```

## Mate Group Work

```powershell
.\tools\solidworks_codex\swctl.ps1 mate-group-plan -Report <inspect.json> -Out tools\solidworks_codex\reports\mate_plan.json
.\tools\solidworks_codex\swctl.ps1 mate-group-validate -Manifest tools\solidworks_codex\reports\mate_plan.json -Out tools\solidworks_codex\reports\mate_validate.json
.\tools\solidworks_codex\swctl.ps1 mate-selection-check -Manifest tools\solidworks_codex\reports\mate_plan.json -Out tools\solidworks_codex\reports\mate_selection.json
.\tools\solidworks_codex\swctl.ps1 mate-group-execute -Manifest tools\solidworks_codex\reports\mate_plan.json -Out tools\solidworks_codex\reports\mate_execute.json
.\tools\solidworks_codex\swctl.ps1 mate-group-execution-check -Manifest tools\solidworks_codex\reports\mate_plan.json -Report <after-inspect.json> -Out tools\solidworks_codex\reports\mate_execution_check.json
```

## Handoff

```powershell
.\tools\solidworks_codex\swctl.ps1 worklog -Action next_step -Message "Accepted current edit" -Next "Run local repair on remaining warnings"
.\tools\solidworks_codex\swctl.ps1 handoff-bundle -Report <after-inspect.json> -Out tools\solidworks_codex\reports\handoff
```

## Public Release

```powershell
.\scripts\verify-all.ps1
.\tools\solidworks_codex\swctl.ps1 public-copy-guard
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
```

Do not commit runtime reports, backups, exports, generated macros, caches, or unsanitized CAD artifacts.
