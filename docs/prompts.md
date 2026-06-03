# Codex Prompt Library

Copy these prompts into a Codex turn after installing the MCP wrapper. They are written to keep SolidWorks work evidence-based: inspect first, use backups before writes, change one variable at a time, and preserve handoff artifacts.

Replace paths, session names, and design goals before running. Do not save CAD files until the before/after evidence has been reviewed.

## 1. Offline repository evaluation

Use when reviewing the project without SolidWorks open.

```text
Use the SolidWorks Codex repository in the current workspace.
First run preflight and generate the offline demo. Then read docs/capability-matrix.md, docs/workflows/README.md, and docs/demo/offline/README.md.
Summarize what the wrapper can do, which actions are read-only, which are guarded writes, and which artifacts prove a clean release tree.
Do not modify CAD files. If you generate reports, keep them under tools/solidworks_codex/reports/.
```

Expected tool flow:

```powershell
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 offline-demo -OutDir docs\demo\offline
.\tools\solidworks_codex\swctl.ps1 capability-matrix -Out docs\capability-matrix.md -JsonOut docs\capability-matrix.json
```

## 2. Live model first look

Use when a part or assembly is already open in SolidWorks and you want Codex to understand it before making suggestions.

```text
A SolidWorks model is open. Treat this as a read-only first look.
Run probe, session-snapshot, report-context, and tool-catalog. Focus on: <design goal or subsystem>.
Do not change dimensions, component states, mates, or files. Report likely anchors, risks, missing names, and the safest next command sequence.
Record the reasoning in worklog with the next action clearly stated.
```

Expected tool flow:

```powershell
.\tools\solidworks_codex\swctl.ps1 probe -Out tools\solidworks_codex\reports\probe.json
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName first-look
.\tools\solidworks_codex\swctl.ps1 report-context -Report tools\solidworks_codex\reports\sessions\<timestamp>-first-look\inspect.json -Target "<focus>" -Out tools\solidworks_codex\reports\first_look_context.md -JsonOut tools\solidworks_codex\reports\first_look_context.json
.\tools\solidworks_codex\swctl.ps1 worklog -SessionName first-look -Action observation -Message "Captured read-only first look and context before any CAD change" -Artifact tools\solidworks_codex\reports\first_look_context.md -Next "Review anchors and decide whether a guarded edit is justified"
```

## 3. Find a messy dimension or component name

Use when names are inconsistent and the user describes the part informally.

```text
Use the latest inspect/session report. Search for candidate components, dimensions, and features related to: <plain-language target>.
Return a short ranked list with exact full names, why each candidate is plausible, and what evidence would confirm the right one.
Do not modify the model. If no candidate is strong enough, ask for one more constraint instead of guessing.
```

Expected tool flow:

```powershell
.\tools\solidworks_codex\swctl.ps1 report-search -Report tools\solidworks_codex\reports\sessions\<timestamp>-first-look\inspect.json -Target "<plain-language target>" -Out tools\solidworks_codex\reports\target_search.md -JsonOut tools\solidworks_codex\reports\target_search.json
.\tools\solidworks_codex\swctl.ps1 report-context -Report tools\solidworks_codex\reports\sessions\<timestamp>-first-look\inspect.json -Target "<plain-language target>" -Out tools\solidworks_codex\reports\target_context.md -JsonOut tools\solidworks_codex\reports\target_context.json
```

## 4. Guarded one-variable CAD edit

Use only after the target dimension or component action has been identified from an inspect report.

```text
We are considering exactly one guarded CAD edit: <dimension/component/action/value>.
Before any write command, identify the files that need backup and run backup. Then change only that one variable, rebuild, inspect again, compare before/after, and summarize the delta.
Do not use -Save unless I explicitly approve after reviewing the compare output. If rebuild or compare shows unexpected changes, stop and give rollback steps.
```

Expected tool flow:

```powershell
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\before_edit.json
.\tools\solidworks_codex\swctl.ps1 backup -Files 'C:\path\to\assembly.SLDASM','C:\path\to\part.SLDPRT' -Out tools\solidworks_codex\reports\backup_before_edit.json
.\tools\solidworks_codex\swctl.ps1 set-dimension -Dimension '<full-dimension-name>' -ValueM <meters> -Out tools\solidworks_codex\reports\set_dimension.json
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild_after_edit.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\after_edit.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\before_edit.json -After tools\solidworks_codex\reports\after_edit.json -Out tools\solidworks_codex\reports\edit_delta.md -JsonOut tools\solidworks_codex\reports\edit_delta.json
```

## 5. General mechanical CAD design review

Use when the user wants design reasoning rather than a single command.

```text
Use the latest session-snapshot report for a mechanical CAD design review. Focus on the current assembly constraints, spatial relationships, editable dimensions, clearance risks, hole/manufacturing evidence, and unresolved information gaps.
Generate workflow-plan, model-understand, design-review, and change-plan outputs. Separate observations from proposed edits. For each proposed edit, state the evidence, risk, required backup files, verification command, and rollback path.
Do not modify the model in this turn.
```

Expected tool flow:

`workflow-plan` uses `-Target` for the overall CAD goal, `-Action` for intent (`single_part`, `part_to_assembly`, `assembly`, `mechanism_assembly`), and `-View` for runtime budget (`fast`, `standard`, `strict`, or `auto`).

```powershell
.\tools\solidworks_codex\swctl.ps1 workflow-plan -Target "<overall CAD goal>" -Action part_to_assembly -View fast -Out tools\solidworks_codex\reports\workflow_plan.md -JsonOut tools\solidworks_codex\reports\workflow_plan.json
.\tools\solidworks_codex\swctl.ps1 model-understand -Report tools\solidworks_codex\reports\sessions\<timestamp>-first-look\inspect.json -View spatial-assembly -Target "current constraints, clearance, editable dimensions, and manufacturing evidence" -Out tools\solidworks_codex\reports\model_understanding.md -JsonOut tools\solidworks_codex\reports\model_understanding.json
.\tools\solidworks_codex\swctl.ps1 design-review -Report tools\solidworks_codex\reports\sessions\<timestamp>-first-look\inspect.json -Target "locating interfaces, floating components, editable dimensions, and manufacturability evidence" -Out tools\solidworks_codex\reports\design_review.md -JsonOut tools\solidworks_codex\reports\design_review.json
.\tools\solidworks_codex\swctl.ps1 change-plan -Report tools\solidworks_codex\reports\sessions\<timestamp>-first-look\inspect.json -Target "<desired design change>" -SessionName mechanical-change-plan -Out tools\solidworks_codex\reports\change_plan.md -JsonOut tools\solidworks_codex\reports\change_plan.json
```

## 6. Pause or hand off a session

Use before switching conversations, pausing work, or preparing a review.

```text
Package the current SolidWorks Codex work so another Codex turn or human reviewer can continue safely.
Use the latest inspect report and worklog. Generate a handoff-bundle focused on: <current goal>.
The README should explain current state, decisions made, files changed or not changed, verification evidence, and the next safest command.
```

Expected tool flow:

```powershell
.\tools\solidworks_codex\swctl.ps1 handoff-bundle -Report tools\solidworks_codex\reports\sessions\<timestamp>-first-look\inspect.json -FromReport tools\solidworks_codex\reports\worklog.jsonl -Target "<current goal>" -OutDir tools\solidworks_codex\reports\handoff\<session-name>
```

## 7. Pre-release local gate

Use before `git add`, a release tag, or a pull request.

```text
Run the local release gates for this repository. Verify tests, Python compilation, Node syntax checks, MCP smoke, repo-health, public-copy-guard, release-tree, audit, and finalize.
If any gate fails, explain the failing artifact and fix only the smallest root cause. Do not stage generated reports, backups, exports, logs, VBA dumps, caches, or personal Codex config paths.
```

Expected tool flow:

```powershell
.\scripts\verify-all.ps1
.\tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard_latest.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree_latest.json
.\tools\solidworks_codex\swctl.ps1 finalize -Out docs\solidworks-codex-final-readiness.md -JsonOut tools\solidworks_codex\reports\final_readiness.json
```
