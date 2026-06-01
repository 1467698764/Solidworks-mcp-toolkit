# Workflows

These recipes are meant to be copied into a local shell or Codex turn. They focus on evidence, reversible changes, and handoff quality rather than raw API coverage.

## 1. Five-minute offline demo evaluation

Use this when reviewing the repository without SolidWorks installed or open. It proves the context, worklog, and handoff path from a fixed inspect report.

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 offline-demo -OutDir docs\demo\offline
.\tools\solidworks_codex\swctl.ps1 report-context `
  -Report tools\solidworks_codex\sandbox\report_after.json `
  -Target "current constraints clearance editable dimensions manufacturing evidence" `
  -Out tools\solidworks_codex\reports\offline_context.md `
  -JsonOut tools\solidworks_codex\reports\offline_context.json
.\tools\solidworks_codex\swctl.ps1 handoff-bundle `
  -Report tools\solidworks_codex\sandbox\report_after.json `
  -Target "offline evaluator handoff" `
  -OutDir tools\solidworks_codex\reports\handoff-offline
```

Check:

- `docs\demo\offline\README.md` explains the static demo output.
- `tools\solidworks_codex\reports\offline_context.md` gives ranked context anchors.
- `tools\solidworks_codex\reports\handoff-offline\README.md` gives the next-turn handoff.

## 2. Live SolidWorks inspect and handoff

Use this when SolidWorks is open with the assembly or part you want Codex to reason about. This is read-only until you deliberately choose a guarded edit.

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 probe -Out tools\solidworks_codex\reports\probe.json
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 report-context `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -Target "locating interfaces clearance editable dimensions manufacturing evidence" `
  -Out tools\solidworks_codex\reports\assembly_context.md `
  -JsonOut tools\solidworks_codex\reports\assembly_context.json
.\tools\solidworks_codex\swctl.ps1 worklog `
  -Action observation `
  -Message "Captured baseline session-snapshot and report-context before any model change" `
  -Artifact tools\solidworks_codex\reports\assembly_context.md `
  -Next "Review candidate dimensions, then decide whether a backup and single edit are justified"
.\tools\solidworks_codex\swctl.ps1 handoff-bundle `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-assembly-baseline\inspect.json `
  -FromReport tools\solidworks_codex\reports\worklog.jsonl `
  -Target "assembly-baseline handoff" `
  -OutDir tools\solidworks_codex\reports\handoff-assembly-baseline
```

Check:

- `session-snapshot` captures `inspect.json`, `summary.md`, and issue-oriented notes.
- `report-context` narrows messy model names into useful anchors without changing CAD state.
- `handoff-bundle` preserves enough context for a later Codex turn to continue safely.

## 3. Guarded one-variable edit

Use this only after the target dimension or component state is known from an inspect/session report. Keep the edit reversible and verify before continuing.

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\before_edit.json
.\tools\solidworks_codex\swctl.ps1 backup `
  -Files 'C:\path\to\assembly.SLDASM','C:\path\to\part.SLDPRT' `
  -Out tools\solidworks_codex\reports\backup_before_edit.json
.\tools\solidworks_codex\swctl.ps1 set-dimension `
  -Dimension 'D1@Sketch1@part.SLDPRT' `
  -ValueM 0.012 `
  -Out tools\solidworks_codex\reports\set_dimension.json
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild_after_edit.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\after_edit.json
.\tools\solidworks_codex\swctl.ps1 compare `
  -Before tools\solidworks_codex\reports\before_edit.json `
  -After tools\solidworks_codex\reports\after_edit.json `
  -Out tools\solidworks_codex\reports\edit_delta.md `
  -JsonOut tools\solidworks_codex\reports\edit_delta.json
.\tools\solidworks_codex\swctl.ps1 worklog `
  -Action verification `
  -Message "Changed one dimension, rebuilt, inspected, and compared before/after reports" `
  -Artifact tools\solidworks_codex\reports\edit_delta.md `
  -Next "Review delta; export or save only after human confirmation"
```

Check:

- `backup` finished before any write command.
- `rebuild` completed and the after report exists.
- `compare` shows only the intended geometry/state change.
- Do not use `-Save` until the delta has been reviewed.

## Release hygiene

Before opening a pull request or publishing, run:

```powershell
.\scripts\verify-all.ps1
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree_latest.json
.\tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard_latest.json
```

`release-tree` keeps generated reports, backups, exports, logs, VBA dumps, caches, and personal Codex paths out of the Git-visible tree. `public-copy-guard` keeps public copy evidence-based and avoids unsupported ranking claims.

