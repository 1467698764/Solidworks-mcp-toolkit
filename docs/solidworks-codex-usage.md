# SolidWorks Codex Usage

The MCP wrapper currently exposes **53 MCP tools** across inspection, understanding, guarded execution, validation, handoff, and release gates.

This is a general SolidWorks MCP. It should be judged by how well it understands and safely changes arbitrary CAD state, not by a single named fixture. `shaper_machine_v5` is a useful simple-mechanism regression case, but it is not impressive enough to define the project and not enough to prove general mechanism assembly.

## First Contact With a Model

```powershell
.\tools\solidworks_codex\swctl.ps1 preflight -Out tools\solidworks_codex\reports\preflight_latest.json
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName baseline
```

Use `report-context` for compact handoff context and `tool-catalog` when choosing the next MCP command instead of relying on memory.

Then use the generated inspect report:

```powershell
.\tools\solidworks_codex\swctl.ps1 model-understand `
  -Report tools\solidworks_codex\reports\sessions\<timestamp>-baseline\inspect.json `
  -View spatial-assembly `
  -Target "interfaces, placements, mates, dimensions, clearance, manufacturing evidence" `
  -Out tools\solidworks_codex\reports\understanding.md `
  -JsonOut tools\solidworks_codex\reports\understanding.json
```

## Planning Validation

Use `workflow-plan` before multi-step work. It records validation profiles and keeps acceptance proportional to the task:

- `draft_part`
- `single_part`
- `assembly`
- `mechanism_assembly`
- `engineering_release`

`runtime_budget` and `extra_checks` let the model request deeper verification only where it matters.

## Executing Changes

Use execution tools only after the relevant objects are understood:

- `safe-set-dimension` for guarded dimension changes
- `component-state` and `feature-state` for suppression, visibility, fixed/floating, and feature toggles
- `component-insert` for placing components by path, transform/origin, and intended state
- `part-feature-execute` for reviewed part specs such as bosses, cuts, holes, slots, pockets, revolves, and pattern-like feature batches
- `metadata-execute` for custom properties and model metadata
- `mate-group-execute` after mate group planning, selection validation, and execution checks

For mate workflows, do not jump straight to verification. First build the selection path: interface indexing, mate group plan, selection check, AddMate-compatible macro/execution data, then execution check and inspect readback.

## Verification After Execution

The normal loop is:

```powershell
.\tools\solidworks_codex\swctl.ps1 rebuild
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\after.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\before.json -After tools\solidworks_codex\reports\after.json -JsonOut tools\solidworks_codex\reports\delta.json
.\tools\solidworks_codex\swctl.ps1 change-verify -Delta tools\solidworks_codex\reports\delta.json -Out tools\solidworks_codex\reports\change_verify.json
```

Assembly acceptance can add:

- `assembly-contract` for required components, placements, feature names, semantic mate participation, fixed/floating policy, and `allow_fixed_fixed`
- `interference` for static clearance and `0 interference`
- native file readback from reopened `.SLDASM/.SLDPRT`
- `part_geometry_readback` for bbox/body/volume/feature-effect evidence
- `assembly_component_placements` for Transform2/origin evidence

Findings should be classified as `blocking`, `warning`, or `not_applicable`.

## Live SolidWorks Gate

Offline tests prove code paths and report logic. Real CAD behavior needs:

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
python tools\solidworks_codex\scripts\sw_live_validation_gate.py --cleanup-stale --out tools\solidworks_codex\reports\live_validation_gate.json
```

The gate validates native file readback, `part_geometry_readback`, `assembly_component_placements`, semantic mate participation, `mate_error: 1`, `0 interference`, lock cleanup, and bounded `CleanupStale` behavior. `.SLDASM/.SLDPRT` deliverables are primary; STEP optional smoke is secondary.

## Handoff

Before pausing:

```powershell
.\tools\solidworks_codex\swctl.ps1 worklog -Action decision -Message "Accepted feature execution after compare/change-verify" -Next "Run assembly diagnosis on remaining mate groups"
.\tools\solidworks_codex\swctl.ps1 handoff-bundle -Report tools\solidworks_codex\reports\after.json -Out tools\solidworks_codex\reports\handoff
```

The next turn should read the handoff bundle, not replay templates blindly.
