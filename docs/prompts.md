# Codex Prompt Library

These prompts are starting points for SolidWorks Codex work. They are not rigid templates; adjust the target and validation profile to the current CAD task.

## Inspect And Understand

```text
Open the current SolidWorks model evidence. Run session-snapshot, then model-understand with a target focused on components, dimensions, feature names, transforms, mates, clearance, and manufacturing evidence. Do not modify files. Report anchors, risks, missing evidence, and the safest next command sequence.
```

## Guarded One-Variable CAD Edit

Contract term: Guarded one-variable CAD edit.

```text
Change exactly one intended dimension or feature parameter. Before writing, identify the current value and affected objects from inspect/model-understand evidence. Back up, execute the change, rebuild, inspect again, compare before/after reports, run change-verify, and record the decision with worklog.
```

## Component Insert

```text
Insert the reviewed component path into the active assembly with explicit placement intent. Use interface-index or assembly diagnosis to choose anchors. Execute through component-insert, rebuild, inspect, and verify assembly_component_placements plus contract evidence.
```

## Part Feature Execute

```text
Execute the reviewed part feature spec in the active part. Confirm the sketch plane or reference geometry, create only the requested feature batch, rebuild, reopen/read back native .SLDPRT evidence, and verify part_geometry_readback instead of accepting a return code alone.
```

## Mate Group Execution

```text
Do not add mates until selection evidence exists. Build interface-index, create mate-group-plan, run mate-selection-check, execute the mate group, then inspect readback for semantic mate participation, mate type, component pair, suppressed state, placement, and 0 interference when required.
```

## Assembly Diagnosis

```text
Diagnose the active assembly for missing components, hostless parts, bad mates, underconnected constraint networks, fixed/floating policy, and likely local repair actions. Separate blocking, warning, and not_applicable findings.
```

## Handoff

```text
Create a handoff bundle from the latest accepted inspect report and worklog. The README should explain current state, decisions made, files changed or not changed, verification evidence, failures, unresolved risks, and the next safest command.
```

## Release Gate

```text
Run verify-all.ps1. If it fails, read the exact failing check, inspect recent changes, identify root cause, patch the relevant script/doc/test, and rerun the failing gate before claiming completion.
```

Release prompts should mention `report-context`, `handoff-bundle`, `public-copy-guard`, and `release-tree` when preparing public artifacts.
