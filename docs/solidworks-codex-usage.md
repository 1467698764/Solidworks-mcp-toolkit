# SolidWorks Codex Usage Guide

The MCP wrapper currently exposes **45 MCP tools** across read-only inspection, analysis, handoff, guarded writes, export/verify, release gates, and the optional live SolidWorks gate.

This project is a general SolidWorks MCP/control layer. It does not try to replace engineering judgment with one rigid CAD template. It collects reviewable evidence from native `.SLDASM/.SLDPRT` models: components, features, dimensions, mates, transforms, spatial relationships, interference, mass, file locks, and runtime callbacks. A reasoning model can then choose an acceptance depth that matches the user intent.

The project should be judged as a general SolidWorks MCP/control layer, not by a single named fixture. The existing shaper fixture is a small mechanism regression case: useful for exposing cuts, revolves, sketch selection, reopen/modify/rebuild persistence, mate creation/readback, component transforms, interference callbacks, and cleanup behavior, but not impressive enough to define the project. Lighter part work should not be blocked by full mechanism-release checks, and mechanism work should not pass on fixture-specific placement alone.

## Core rules

- Inspect model evidence before planning edits.
- Before feature creation, verify the active document, clear selection state, target sketch/entity, and expected feature consumer.
- Back up before writes; rebuild, inspect, compare, and verify after writes.
- Native `.SLDASM/.SLDPRT` artifacts are the main deliverables. STEP optional smoke can supplement export coverage but cannot replace native SolidWorks assembly validation.
- Do not globally force every heavy engineering check. Use validation profiles and task-specific extra checks.

## validation profiles

`tools/solidworks_codex/scripts/sw_validation_profiles.py` provides intent-scoped validation profiles. Every check has a layer, severity, reason, and evidence scope.

- layers: `geometry`, `assembly`, `engineering`, `mcp_quality`
- severities: `blocking`, `warning`, `not_applicable`
- runtime_budget: `fast`, `standard`, `strict`
- extra_checks: a reasoning model may add task-specific checks, but each extra check must include name/layer/severity/reason/evidence_scope.

Built-in profiles:

| Profile | Use case | Default blocking focus |
| --- | --- | --- |
| `draft_part` | quick draft or local experiment | native artifacts, rebuild health, requested part shape semantics |
| `single_part` | one part deliverable | part geometry/rebuild/semantic features; assembly checks are not_applicable |
| `assembly` | static assembly | mate semantics, component placements, static interference, functional adjacency |
| `mechanism_assembly` | sliding/rotating mechanism | assembly checks plus constraint/DOF intent, motion sweep collision, clearance tolerance screen |
| `engineering_release` | near-release engineering package | mechanism checks plus BOM, DFM/DFA, strength/stiffness, drawing/BOM readiness warnings |

This keeps validation proportional: simple work remains usable, while complex work can upgrade the profile or add extra_checks instead of making every draft fail release-grade gates.

## Read-only workflow

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_before.json
.\tools\solidworks_codex\swctl.ps1 summary -Report tools\solidworks_codex\reports\assembly_before.json -Out tools\solidworks_codex\reports\assembly_before.md
.\tools\solidworks_codex\swctl.ps1 model-understand -Report tools\solidworks_codex\reports\assembly_before.json -View spatial-assembly -Target "locating interfaces, editable dimensions, floating components, clearance, mate semantics, and manufacturing evidence" -Out tools\solidworks_codex\reports\understanding.md -JsonOut tools\solidworks_codex\reports\understanding.json
```

Allowing the command to launch SolidWorks is explicit:

```powershell
.\tools\solidworks_codex\swctl.ps1 start-inspect -Out tools\solidworks_codex\reports\assembly_before.json
```

## Guarded edit workflow

```powershell
.\tools\solidworks_codex\swctl.ps1 backup -Files 'C:\path\to\your\sample_machine.SLDASM','C:\path\to\changed_part.SLDPRT' -Out tools\solidworks_codex\reports\backup_before_change.json
.\tools\solidworks_codex\swctl.ps1 safe-set-dimension -Model 'C:\path\to\changed_part.SLDPRT' -Dimension 'D1@Sketch1@plate.SLDPRT' -ValueM 0.012 -Out tools\solidworks_codex\reports\safe_set_dimension.json
.\tools\solidworks_codex\swctl.ps1 rebuild -Out tools\solidworks_codex\reports\rebuild.json
.\tools\solidworks_codex\swctl.ps1 inspect -Out tools\solidworks_codex\reports\assembly_after.json
.\tools\solidworks_codex\swctl.ps1 compare -Before tools\solidworks_codex\reports\assembly_before.json -After tools\solidworks_codex\reports\assembly_after.json -Out tools\solidworks_codex\reports\assembly_delta.md -JsonOut tools\solidworks_codex\reports\assembly_delta.json
.\tools\solidworks_codex\swctl.ps1 change-verify -Report tools\solidworks_codex\reports\assembly_delta.json -AllowDimension 'D1@Sketch1@plate.SLDPRT'
```

## Mate group repair protocol

For an existing assembly, use the read-only review pipeline before any mate
mutation. It produces diagnosis, interface candidates, repair actions, and a
mate group plan:

```powershell
.\tools\solidworks_codex\swctl.ps1 assembly-review-pipeline `
  -Report tools\solidworks_codex\reports\assembly_before.json `
  -OutDir tools\solidworks_codex\reports\assembly_review
.\tools\solidworks_codex\swctl.ps1 mate-group-validate `
  -Report tools\solidworks_codex\reports\assembly_review\mate_group_plan.json `
  -Out tools\solidworks_codex\reports\assembly_review\mate_group_validation.json
.\tools\solidworks_codex\swctl.ps1 mate-group-macro `
  -Report tools\solidworks_codex\reports\assembly_review\mate_group_plan.json `
  -OutDir tools\solidworks_codex\macros\mate_groups `
  -Out tools\solidworks_codex\reports\assembly_review\mate_group_macro_manifest.json
.\tools\solidworks_codex\swctl.ps1 mate-group-live-protocol `
  -Report tools\solidworks_codex\reports\assembly_review\mate_group_macro_manifest.json `
  -FromReport tools\solidworks_codex\reports\assembly_review\mate_group_validation.json `
  -Model 'C:\path\to\assembly.SLDASM' `
  -Out tools\solidworks_codex\reports\assembly_review\mate_group_live_protocol.json `
  -JsonOut tools\solidworks_codex\reports\assembly_review\mate_group_live_protocol.md
.\tools\solidworks_codex\swctl.ps1 selection-report `
  -Out tools\solidworks_codex\reports\assembly_review\selection_before_mate.json
.\tools\solidworks_codex\swctl.ps1 mate-selection-check `
  -Report tools\solidworks_codex\reports\assembly_review\mate_group_macro_manifest.json `
  -FromReport tools\solidworks_codex\reports\assembly_review\selection_before_mate.json `
  -Mate MG_crank_shaft_01_concentric `
  -Out tools\solidworks_codex\reports\assembly_review\mate_selection_check.json
```

`mate-group-live-protocol` is not a blind executor. It is a controlled work
order for live SolidWorks sessions: one group at a time, backup first, capture
selection evidence, run only reviewed macros, rebuild, inspect, run
`mate-group-execution-check`, check interference, and clean up locks/windows
before moving to the next group. If upstream validation has blocking findings,
the protocol output is blocked and contains no executable group steps.
`mate-selection-check` is the pre-macro guard: it compares the current
`selection-report` against the expected mate macro, requires exactly two
supported face/edge/axis/plane-style entities, and blocks component-level or
wrong-component selections before a macro can be treated as reviewed.

## Assembly contract and model understanding

`assembly-contract` is a reusable offline gate for inspect reports. It checks document type, minimum component count, required component prefixes, required component suppression, Transform/origin tolerance, required part feature names/semantic counts, semantic mate type, mate suppression state, mate error/status when reported, fixed-fixed mate risk, and expected participating components. Contract entries may set severity to `blocking`, `warning`, or `not_applicable`; warnings are reported without failing the command, while unknown severities fail so contracts stay reviewable. Component matching removes only SolidWorks instance suffixes such as `-1`, so hyphenated part names remain precise and substring pair matches are rejected. A required mate between two fixed components is blocking by default because it cannot prove an active constraint; use `allow_fixed_fixed: true` only for explicit reference/documentation mates.

Shape checks stay proportional. A quick draft can omit `part_features`, a normal part/assembly can require only the user-visible semantic features, and a strict mechanism/release profile can add more checks later. Example manifest fragment:

```json
{
  "part_features": {
    "base_plate": {
      "required_names": ["Base_Boss", "Mounting_Holes"],
      "required_semantics": {
        "through_hole": { "min_count": 4 }
      }
    },
    "optional_guard": {
      "required": true,
      "required_names": ["Guard_Rib"],
      "severity": "warning"
    }
  }
}
```

SolidWorks AddMate error values follow the SolidWorks API enum; `mate_error: 1` means the AddMate call reported no error. It is not enough by itself: solved placement, mate feature readback, suppressed/fixed state, and component participation still need separate evidence.

```powershell
.\tools\solidworks_codex\swctl.ps1 assembly-contract `
  -Report tools\solidworks_codex\reports\assembly_before.json `
  -Manifest tools\solidworks_codex\reports\assembly_contract_manifest.json `
  -Out tools\solidworks_codex\reports\assembly_contract.json
```

`model-understand` must not be a placeholder. It cannot pass with only a component inventory or bounding-box proximity. A verified mate network may count as functional connection evidence only when mate semantics, selected entities, participating components, component index, and spatial model evidence are present.

## Live SolidWorks gate

Run the live gate only on a machine with SolidWorks and pywin32:

```powershell
.\tools\solidworks_codex\swctl.ps1 live-gate -CleanupStale -Out tools\solidworks_codex\reports\live_validation_gate.json
```

The underlying script flag is `--cleanup-stale`; `CleanupStale` is the PowerShell switch name. The gate is opt-in, serial, and attempts to keep SolidWorks hidden. It scans `tools/solidworks_codex/live_fixture/**/~$*` before startup and between checks.

Live gate layers:

- `live_session_smoke`: minimal COM/session/mate/interference/cleanup path.
- `live_capability_suite`: extrude, cut, revolve, revolved cut, sketch dimension read/modify/rebuild/save, assembly insertion, concentric mate, distance mate, interference callback, mass callback, close/cleanup, selection-isolation evidence, `assembly_component_placements` component Transform2/origin placement readback, and `part_geometry_readback` bbox/body/volume evidence from reopened native `.SLDPRT` files.
- `complete_shaper_v5`: retained simple-mechanism regression fixture at `tools/solidworks_codex/live_fixture/shaper_machine_v5/bullhead_shaper_complete.SLDASM` with report `tools/solidworks_codex/reports/shaper_machine_v5/complete_shaper_build.json`. It is a gap detector for assembly diagnosis, interface selection, mate-network evidence, interference, and cleanup; it is not a capability showcase.

Current live capability suite evidence:

- validation `ok: true`
- `part_geometry_readback` present for `extrude_cut_plate`, `revolve_boss_part`, `revolve_cut_part`, and `editable_dimension_plate`
- mate API readback reports `mate_error: 1`, which is SolidWorks AddMate no-error
- `assembly_component_placements` solved origins match the accepted native assembly layout
- post cleanup has no `~$` lock files

Simple mechanism regression evidence should stay modest and current:

- native `.SLDASM/.SLDPRT` files are required;
- part feature readback should cover holes, windows, slots, dovetails, lightening cuts, tool bevels, and standard/detail features when those details are accepted;
- primary component placement evidence should come from native Transform/readback, not unchecked display placement;
- structural references may be fixed, but moving functional parts must not be accepted as fixed-layout evidence;
- standard/detail components must have host/attachment evidence or be omitted from the accepted assembly with a recorded reason;
- mate evidence must be semantic, varied enough for the intended joint, read back from SolidWorks, and connected to participating components;
- interference callback should be available and report `0 interference` for static acceptance;
- post cleanup must have no generated `~$` lock files.

Do not treat an old `complete_shaper_build.json` with `ok: true` as current truth. The gate checks report freshness and recomputes strict evidence from the current scripts. If the screenshot, mate graph, placement evidence, or model-understanding output says the assembly is scattered or only fixture-stabilized, treat it as a failing regression, not as a cosmetic display issue.

`-CleanupStale` is bounded to old generated directories: `shaper_machine`, `shaper_machine_v2`, `shaper_machine_v3`, and `shaper_machine_v4`. It must not touch `shaper_machine_v5`, `live_capability_suite`, user models, or unrelated workspace files.

## Handoff workflow

`workflow-plan` maps `-Target` to the overall CAD goal, `-Action` to intent (`single_part`, `part_to_assembly`, `assembly`, or `mechanism_assembly`), and `-View` to runtime budget (`fast`, `standard`, `strict`; `auto` uses `standard`).

```powershell
.\tools\solidworks_codex\swctl.ps1 workflow-plan -Target "design a checked bracket part and insert it into an assembly for placement and interference validation" -Action part_to_assembly -View fast -Out tools\solidworks_codex\reports\workflow_plan.md -JsonOut tools\solidworks_codex\reports\workflow_plan.json
.\tools\solidworks_codex\swctl.ps1 session-snapshot -SessionName assembly-baseline
.\tools\solidworks_codex\swctl.ps1 worklog -SessionName mechanical-interface-update -Action decision -Message "Use report-context and report-search before any write operation" -Artifact tools\solidworks_codex\reports\context.md -Next "backup target files before safe-set-dimension"
.\tools\solidworks_codex\swctl.ps1 handoff-bundle -Report tools\solidworks_codex\reports\assembly_before.json -FromReport tools\solidworks_codex\reports\worklog.jsonl -Target "current model evidence, constraints, clearance, and manufacturing gaps" -OutDir tools\solidworks_codex\reports\handoff\assembly-baseline
.\tools\solidworks_codex\swctl.ps1 tool-catalog -Out tools\solidworks_codex\reports\tool_catalog.md -JsonOut tools\solidworks_codex\reports\tool_catalog.json
```

## Pre-commit checks

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
node tools\solidworks_codex\mcp\smoke-test.cjs
.\tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
.\tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard.json
.\tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
```
