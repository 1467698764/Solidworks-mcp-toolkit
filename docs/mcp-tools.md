# MCP Tool Manual

This project currently exposes **56 MCP tools**. This manual groups them by workflow and describes required parameters, optional parameters, practical scope, and limits.

> GitHub display rule: tool names and parameter names are wrapped in backticks, and long lists are rendered as tables or bullets so names do not run together.

## Calling Rules

- MCP inputs are JSON objects.
- Prefer absolute paths for native SolidWorks files. Repository-relative paths are fine for reports and specs.
- Tools with a `start` option may launch SolidWorks. Other live tools normally attach to an existing session.
- Run `solidworks_backup` or a tool-owned guarded pipeline before native file mutation.
- Use `dry_run: true` when available to validate plans without touching SolidWorks.

## Read, Search, And Understand Models

| Tool | Purpose |
| --- | --- |
| `solidworks_probe` | Read-only attach to an already-running SolidWorks instance and summarize active document. |
| `solidworks_start_probe` | Allow COM launch of SolidWorks, then summarize active document. |
| `solidworks_inspect` | Deep read-only inspect of active part/assembly: features, dimensions, components. |
| `solidworks_start_inspect` | Allow COM launch of SolidWorks, then run deep read-only inspect. |
| `solidworks_mass_properties` | Report mass properties for active or specified SolidWorks document. |
| `solidworks_selection_report` | Report current SolidWorks selection set for safe preselected-entity mate workflows. |
| `solidworks_session_snapshot` | Create a work-session package: inspect JSON, summary Markdown, issue report, manifest. |
| `solidworks_report_summary` | Summarize a SolidWorks Codex JSON probe/inspect report into Markdown. |
| `solidworks_report_search` | Search an inspect JSON report for components, dimensions, and features by text/state when names are messy. |
| `solidworks_report_context` | Build a freeform handoff/context pack from an inspect report: inventory, risks, anchors, and next commands. |
| `solidworks_model_understand` | Build a compact task-scoped model understanding pack from an inspect report: baseline facts, relevant CAD objects, relationship hypotheses, risks, and next minimal queries. |

### `solidworks_probe`

**Capability scope**

- Reads a short summary of the active document in an already-running SolidWorks session.

**Limits and notes**

- Does not start SolidWorks and does not perform deep feature or component readback.

**Required parameters**

- None

**Optional parameters**

- `out`: string; Optional output JSON path.

### `solidworks_start_probe`

**Capability scope**

- Starts SolidWorks if needed, then reads a short active-document summary.

**Limits and notes**

- Use only for session discovery; it is not a modeling or validation tool.

**Required parameters**

- None

**Optional parameters**

- `out`: string; Optional output JSON path.

### `solidworks_inspect`

**Capability scope**

- Reads features, dimensions, components, mate-like features, and document handoff metadata from an active or specified model.

**Limits and notes**

- Readback depends on what SolidWorks exposes through COM; hidden, lightweight, or failed documents may have incomplete evidence.

**Required parameters**

- None

**Optional parameters**

- `model`: string; Optional SolidWorks file to open before inspection.
- `out`: string; Optional output JSON path.

### `solidworks_start_inspect`

**Capability scope**

- Starts SolidWorks if needed, then runs deep inspection.

**Limits and notes**

- Startup is slower than attaching to an existing session.

**Required parameters**

- None

**Optional parameters**

- `model`: string; Optional SolidWorks file to open before inspection.
- `out`: string; Optional output JSON path.

### `solidworks_mass_properties`

**Capability scope**

- Reads mass properties for active or specified documents.

**Limits and notes**

- Mass can be meaningless when material or density evidence is missing.

**Required parameters**

- None

**Optional parameters**

- `model`: string
- `out`: string

### `solidworks_selection_report`

**Capability scope**

- Reports the current SolidWorks selection set and native identity evidence.

**Limits and notes**

- It does not select anything by itself.

**Required parameters**

- None

**Optional parameters**

- `out`: string
- `start`: boolean

### `solidworks_session_snapshot`

**Capability scope**

- Creates a work-session package with inspect, summary, issue report, and manifest.

**Limits and notes**

- Good for handoff, not a validation gate.

**Required parameters**

- None

**Optional parameters**

- `name`: string
- `from_report`: string
- `out_dir`: string
- `start`: boolean

### `solidworks_report_summary`

**Capability scope**

- Summarizes a probe or inspect JSON report into Markdown.

**Limits and notes**

- Summary only; no diagnosis.

**Required parameters**

- `report`: string; JSON report path.

**Optional parameters**

- `out`: string; Optional Markdown output path.

### `solidworks_report_search`

**Capability scope**

- Searches a report for components, dimensions, and features by text, type, or state.

**Limits and notes**

- No result means no report evidence, not necessarily no model object.

**Required parameters**

- `report`: string

**Optional parameters**

- `query`: string
- `kind`: string; enum: all, components, dimensions, features
- `state`: string; enum: any, suppressed, unsuppressed, hidden, shown, fixed, floating, lightweight
- `out`: string
- `json_out`: string

### `solidworks_report_context`

**Capability scope**

- Builds a handoff context pack with inventory, risks, anchors, and next commands.

**Limits and notes**

- For reasoning and handoff; not execution.

**Required parameters**

- `report`: string

**Optional parameters**

- `focus`: string
- `out`: string
- `json_out`: string

### `solidworks_model_understand`

**Capability scope**

- Builds task-scoped understanding: relevant objects, relationship hypotheses, risks, and next queries.

**Limits and notes**

- Hypotheses need live evidence before acceptance.

**Required parameters**

- `report`: string

**Optional parameters**

- `task`: string
- `view`: string; enum: auto, general, dimension-edit, assembly-constraints, interference-clearance, manufacturing-holes, spatial-assembly
- `out`: string
- `json_out`: string

## Safety Gates And Change Verification

| Tool | Purpose |
| --- | --- |
| `solidworks_backup` | Create timestamped backups of .SLDPRT/.SLDASM/.SLDDRW files before modification. |
| `solidworks_backup_status` | Inspect a backup report and classify source files as unchanged, changed, missing, or restorable. |
| `solidworks_restore_backup` | Dry-run or apply restoration from a SolidWorks Codex backup report. apply=false only validates and plans. |
| `solidworks_set_dimension` | Set one SolidWorks dimension by full parameter name. Value is SystemValue in meters. Use save only after backup. |
| `solidworks_safe_set_dimension` | Run a guarded one-dimension edit pipeline: backup, inspect, set dimension, rebuild, inspect, compare, and verify only that dimension changed. |
| `solidworks_rebuild` | Rebuild active or specified SolidWorks document; optionally save. |
| `solidworks_compare_reports` | Compare two SolidWorks Codex inspect JSON reports. |
| `solidworks_change_verify` | Verify a compare delta contains only expected dimensions, component changes, additions/removals, or feature type count changes. |
| `solidworks_preflight` | Run deterministic environment/toolchain preflight before touching a real SolidWorks model. |

### `solidworks_backup`

**Capability scope**

- Creates timestamped file backups for native SolidWorks files before mutation.

**Limits and notes**

- File-level only; it does not understand CAD intent.

**Required parameters**

- `files`: array; SolidWorks files to back up.

**Optional parameters**

- `out`: string; Optional report JSON path.

### `solidworks_backup_status`

**Capability scope**

- Checks whether files in a backup report are unchanged, changed, missing, or restorable.

**Limits and notes**

- Requires a previous backup report.

**Required parameters**

- `report`: string; Backup report JSON generated by solidworks_backup.

**Optional parameters**

- `out`: string; Optional status report JSON path.

### `solidworks_restore_backup`

**Capability scope**

- Dry-runs or applies restoration from a backup report.

**Limits and notes**

- With apply=true it can overwrite source files.

**Required parameters**

- `report`: string; Backup report JSON generated by solidworks_backup.

**Optional parameters**

- `apply`: boolean; Actually overwrite source files with backups. Defaults to dry-run.
- `out`: string; Optional restore report JSON path.

### `solidworks_set_dimension`

**Capability scope**

- Writes one fully-qualified SolidWorks dimension value in meters.

**Limits and notes**

- Use after backup; it is not a multi-edit pipeline.

**Required parameters**

- `dimension`: string; Full SolidWorks dimension/parameter name.
- `value_m`: number; New SystemValue in meters.

**Optional parameters**

- `model`: string; Optional model path to open.
- `save`: boolean; Save after changing; backup first.
- `out`: string; Optional report JSON path.

### `solidworks_safe_set_dimension`

**Capability scope**

- Runs backup, inspect, set dimension, rebuild, inspect, compare, and verify for one dimension.

**Limits and notes**

- Best for one controlled dimension edit, not topology surgery.

**Required parameters**

- `model`: string; SolidWorks model file to back up and edit.
- `dimension`: string; Full SolidWorks dimension/parameter name.
- `value_m`: number; New SystemValue in meters.

**Optional parameters**

- `save`: boolean; Save during set/rebuild. Defaults to false.
- `out_dir`: string; Directory for pipeline artifacts.
- `out`: string; Optional pipeline report JSON path.

### `solidworks_rebuild`

**Capability scope**

- Rebuilds an active or specified document and can save it.

**Limits and notes**

- A rebuild is not acceptance; follow with inspect and validation.

**Required parameters**

- None

**Optional parameters**

- `model`: string
- `save`: boolean
- `out`: string

### `solidworks_compare_reports`

**Capability scope**

- Compares two inspect reports.

**Limits and notes**

- Only compares evidence present in reports.

**Required parameters**

- `before`: string
- `after`: string

**Optional parameters**

- `out`: string
- `json_out`: string

### `solidworks_change_verify`

**Capability scope**

- Checks that a compare delta contains only allowed dimensions, components, additions/removals, or feature type changes.

**Limits and notes**

- Allow lists must be precise; design correctness is still separate.

**Required parameters**

- `delta`: string

**Optional parameters**

- `allow_dimension`: array
- `allow_component`: array
- `allow_component_added`: array
- `allow_component_removed`: array
- `allow_feature_type`: array
- `require_allowed_change`: boolean; Fail if allow lists are provided but no allowed change is observed.
- `out`: string

### `solidworks_preflight`

**Capability scope**

- Runs deterministic toolchain and environment checks.

**Limits and notes**

- Passing preflight does not validate a model.

**Required parameters**

- None

**Optional parameters**

- `out`: string

## Execution-Layer Write Tools

| Tool | Purpose |
| --- | --- |
| `solidworks_component_state` | Change assembly component state by Component2.Name2: hide/show/suppress/unsuppress/fix/float. |
| `solidworks_component_insert` | Insert a reviewed .SLDPRT/.SLDASM component into the active or specified assembly with origin/config/fixed-state evidence. |
| `solidworks_standard_part_resolve` | Resolve a reviewed local standard-part catalog request into a component-insert spec with source policy, supplier/license evidence, host attachment intent, and selector handoff. |
| `solidworks_feature_state` | Change part or assembly feature state by feature name: suppress/unsuppress/delete, set a feature-scoped dimension, reorder a feature, or apply reviewed Feature Definition property edits, then rebuild and report before/after evidence. |
| `solidworks_part_feature_execute` | Execute a reviewed part feature spec in SolidWorks: extrude bosses, extrude cuts, revolve bosses, revolved cuts, basic/countersink/counterbore holes, slot cuts, pocket cuts, fillet, chamfer, linear pattern, circular pattern, or mirror with named feature/entity selectors. |
| `solidworks_metadata_execute` | Execute reviewed material and custom-property metadata writes for active or specified SolidWorks models. |
| `solidworks_mate_group_execute` | Execute reviewed mate group selector evidence in the active SolidWorks assembly using SelectByID2, AddMate5, and immediate rebuild. dry_run only plans selector actions. |
| `solidworks_motion_sweep_lite` | Execute or dry-run sampled mechanism driver positions against executable mate evidence, rebuild each sample, and block collisions/dead layouts. |

### `solidworks_component_state`

**Capability scope**

- Changes one assembly component state: hide, show, suppress, unsuppress, fix, or float.

**Limits and notes**

- Component names must uniquely identify the target.

**Required parameters**

- `component`: string
- `action`: string; enum: hide, show, suppress, unsuppress, fix, float

**Optional parameters**

- `save`: boolean
- `out`: string

### `solidworks_component_insert`

**Capability scope**

- Inserts a reviewed part or assembly component with origin, configuration, fixed state, and attachment intent evidence.

**Limits and notes**

- Insertion is not attachment; use mate planning/execution afterward.

**Required parameters**

- `spec`: string; JSON spec with part_path, origin_m, optional configuration and fixed.

**Optional parameters**

- `model`: string
- `start`: boolean
- `save`: boolean
- `dry_run`: boolean
- `out`: string

### `solidworks_standard_part_resolve`

**Capability scope**

- Resolves a reviewed local standard-part catalog request into a component-insert spec.

**Limits and notes**

- Does not download parts from the internet.

**Required parameters**

- `catalog`: string; Reviewed local standard-part catalog JSON.
- `request`: string; Standard-part request JSON.

**Optional parameters**

- `out`: string
- `component_spec_out`: string; Optional component-insert spec JSON output path.

### `solidworks_feature_state`

**Capability scope**

- Suppresses, unsuppresses, deletes, edits feature dimensions, reorders features, or applies reviewed definition edits.

**Limits and notes**

- Ambiguous feature names block execution.

**Required parameters**

- `feature`: string
- `action`: string; enum: suppress, unsuppress, delete, set-dimension, reorder, edit-definition

**Optional parameters**

- `dimension`: string
- `value_m`: number
- `target_feature`: string
- `reorder_position`: string; enum: before, after
- `definition_spec`: string; JSON spec file with reviewed definition edits.
- `model`: string
- `save`: boolean
- `out`: string

### `solidworks_part_feature_execute`

**Capability scope**

- Executes reviewed part feature specs: extrude boss/cut, revolve boss/cut, holes, slots, pockets, fillet, chamfer, pattern, and mirror.

**Limits and notes**

- Requires reviewed selectors; it must not guess faces, axes, or sketches.

**Required parameters**

- `spec`: string; JSON spec with operation, selectors, and parameters.

**Optional parameters**

- `model`: string
- `start`: boolean
- `save`: boolean
- `dry_run`: boolean
- `out`: string

### `solidworks_metadata_execute`

**Capability scope**

- Writes reviewed material and custom-property metadata.

**Limits and notes**

- Does not judge whether the material is appropriate.

**Required parameters**

- `spec`: string; JSON spec with material and/or custom properties.

**Optional parameters**

- `model`: string
- `start`: boolean
- `save`: boolean
- `dry_run`: boolean
- `out`: string

### `solidworks_mate_group_execute`

**Capability scope**

- Executes reviewed mate group selector evidence with SelectByID2, AddMate5, and immediate rebuild.

**Limits and notes**

- dry_run only plans; live execution depends on selector resolution.

**Required parameters**

- `macro_manifest`: string

**Optional parameters**

- `dry_run`: boolean
- `out`: string

### `solidworks_motion_sweep_lite`

**Capability scope**

- Samples mechanism driver positions, rebuilds, and checks collision/dead-layout evidence.

**Limits and notes**

- Lightweight sweep; not full motion simulation.

**Required parameters**

- `spec`: string

**Optional parameters**

- `macro_manifest`: string
- `model`: string
- `dry_run`: boolean
- `out`: string

## Assembly Diagnosis And Mate Chain

| Tool | Purpose |
| --- | --- |
| `solidworks_assembly_diagnose` | Diagnose an assembly inspect report: fixed/floating state, mate graph gaps, bad mates, isolated/no-mate components, bbox spacing, standard-part attachment, and lock-file hints. |
| `solidworks_assembly_repair_plan` | Build a read-only local repair plan from an assembly diagnosis JSON: bad mate resolution order, hostless standard-part host suggestions, and isolated-component intent questions. |
| `solidworks_interface_index` | Build a read-only heuristic component/interface index from an inspect report: bbox contact candidates, nearest neighbors, standard-part hints, and root/suppression role hints. |
| `solidworks_mate_group_plan` | Build a read-only mate group plan from an assembly repair plan and interface index: grouped candidate mates, components, evidence, and per-group verification. |
| `solidworks_mate_group_validate` | Validate a read-only mate group plan before macro or live execution: component count, supported mate types, and required rebuild/mate-error verification. |
| `solidworks_mate_selection_check` | Validate current selection-report evidence against a mate macro manifest before running a reviewed mate macro: exactly two supported entity selections on expected components. |
| `solidworks_mate_group_execution_check` | Check after-inspect evidence for mate group macro execution: expected named mates exist, are unsuppressed, and report no solver/API errors. |
| `solidworks_mate_group_live_protocol` | Generate a controlled per-group live SolidWorks work order for reviewed mate group macros: backup, selection evidence, macro run, rebuild, inspect, execution check, interference, and cleanup. |
| `solidworks_assembly_review_pipeline` | Run the read-only assembly review pipeline from one inspect report and write diagnosis, interface index, repair plan, mate group plan, and manifest artifacts. |
| `solidworks_interference_check` | Run conservative SolidWorks assembly interference detection against the active or specified assembly and emit handoff plus collision evidence. |

### `solidworks_assembly_diagnose`

**Capability scope**

- Diagnoses assembly reports: component inventory, mate graph, bad mates, isolated components, bbox spacing, standard-part host gaps, and locks.

**Limits and notes**

- Bounding-box clearance is approximate.

**Required parameters**

- `report`: string

**Optional parameters**

- `out`: string
- `lock_root`: string
- `near_tolerance_m`: number
- `standard_part_regex`: string

### `solidworks_assembly_repair_plan`

**Capability scope**

- Creates a local repair plan with affected subgraphs and rollback preconditions.

**Limits and notes**

- Read-only; it does not repair by itself.

**Required parameters**

- `diagnosis`: string

**Optional parameters**

- `out`: string
- `markdown_out`: string

### `solidworks_interface_index`

**Capability scope**

- Indexes planar, cylindrical, slot/path, coordinate-system, and fallback selectors from inspect evidence.

**Limits and notes**

- Weak bbox-only interfaces need reviewed native evidence before automatic execution.

**Required parameters**

- `report`: string

**Optional parameters**

- `out`: string
- `near_tolerance_m`: number
- `standard_part_regex`: string

### `solidworks_mate_group_plan`

**Capability scope**

- Converts repair plan plus interface index into candidate mate groups.

**Limits and notes**

- Candidates still require validation and selector evidence.

**Required parameters**

- `repair_plan`: string
- `interface_index`: string

**Optional parameters**

- `out`: string
- `markdown_out`: string

### `solidworks_mate_group_validate`

**Capability scope**

- Validates mate group structure, supported mate types, component counts, and required checks.

**Limits and notes**

- Does not prove live selection will succeed.

**Required parameters**

- `mate_group_plan`: string

**Optional parameters**

- `out`: string

### `solidworks_mate_selection_check`

**Capability scope**

- Compares selection-report evidence with a mate macro manifest.

**Limits and notes**

- Does not add mates.

**Required parameters**

- `macro_manifest`: string
- `selection_report`: string

**Optional parameters**

- `expected_mate_name`: string
- `out`: string

### `solidworks_mate_group_execution_check`

**Capability scope**

- Checks after-inspect evidence for expected mates and solver/API health.

**Limits and notes**

- Requires a fresh after-inspect report.

**Required parameters**

- `macro_manifest`: string
- `after_report`: string

**Optional parameters**

- `out`: string

### `solidworks_mate_group_live_protocol`

**Capability scope**

- Creates a live work order for backup, selection, macro, rebuild, inspect, execution check, interference, and cleanup.

**Limits and notes**

- Protocol only; it does not run every step.

**Required parameters**

- `macro_manifest`: string
- `validation_report`: string

**Optional parameters**

- `model`: string
- `out`: string
- `markdown_out`: string

### `solidworks_assembly_review_pipeline`

**Capability scope**

- Runs a read-only assembly review pipeline producing diagnosis, interface index, repair plan, mate group plan, and manifest.

**Limits and notes**

- Does not execute mates.

**Required parameters**

- `report`: string

**Optional parameters**

- `out_dir`: string
- `near_tolerance_m`: number
- `standard_part_regex`: string

### `solidworks_interference_check`

**Capability scope**

- Runs conservative SolidWorks interference detection on an active or specified assembly.

**Limits and notes**

- Requires an assembly; exact contact interpretation may need visual or section review.

**Required parameters**

- None

**Optional parameters**

- `model`: string; Optional .SLDASM model path to open before checking.
- `out`: string

## Validation, Engineering Review, And Export

| Tool | Purpose |
| --- | --- |
| `solidworks_design_review` | Generate a generic evidence-first mechanical CAD review from an inspect JSON report: findings, open questions, and candidate actions. |
| `solidworks_change_plan` | Generate a flexible evidence-first mechanical CAD change plan from an inspect JSON report and natural-language goal. |
| `solidworks_issue_report` | Generate a practical issue/recommendation report from an inspect JSON report. |
| `solidworks_engineering_lite` | Generate a read-only engineering-lite BOM, drawing-BOM CSV, material, DFM, and DFA review from inspect evidence. |
| `solidworks_part_geometry_validate` | Validate part inspect readback against a geometry contract: body count, bbox, volume, required features, semantic feature counts, and interface evidence. |
| `solidworks_visual_capture` | Capture SolidWorks window visual evidence into a screenshot manifest; dry_run writes a deterministic placeholder PNG for CI/protocol checks. |
| `solidworks_visual_validate` | Validate screenshot evidence and reviewed visual findings against an inspect report; missing screenshots or visual contradictions block acceptance. |
| `solidworks_export` | Export active or specified SolidWorks document to target path. Format follows suffix. |

### `solidworks_design_review`

**Capability scope**

- Creates an evidence-first mechanical CAD review from an inspect report.

**Limits and notes**

- Read-only and report-bound.

**Required parameters**

- `report`: string

**Optional parameters**

- `intent`: string
- `out`: string
- `json_out`: string

### `solidworks_change_plan`

**Capability scope**

- Creates a change plan from an inspect report and natural-language goal.

**Limits and notes**

- Plans only; does not execute.

**Required parameters**

- `report`: string
- `goal`: string

**Optional parameters**

- `session_name`: string
- `out`: string
- `json_out`: string

### `solidworks_issue_report`

**Capability scope**

- Summarizes practical issues and recommendations from an inspect report.

**Limits and notes**

- A report summary is not an acceptance gate.

**Required parameters**

- `report`: string

**Optional parameters**

- `out`: string
- `json_out`: string

### `solidworks_engineering_lite`

**Capability scope**

- Generates BOM, drawing BOM CSV, material, DFM, and DFA review from inspect evidence.

**Limits and notes**

- Engineering guidance, not release sign-off.

**Required parameters**

- `report`: string

**Optional parameters**

- `out`: string
- `json_out`: string
- `out_dir`: string; Optional artifact directory for drawing_bom.csv.

### `solidworks_part_geometry_validate`

**Capability scope**

- Validates part readback against a geometry contract.

**Limits and notes**

- Only validates evidence present in the report.

**Required parameters**

- `report`: string
- `contract`: string

**Optional parameters**

- `out`: string

### `solidworks_visual_capture`

**Capability scope**

- Captures SolidWorks window screenshot evidence or dry-run placeholder evidence.

**Limits and notes**

- Screenshots need validation context.

**Required parameters**

- None

**Optional parameters**

- `out_dir`: string
- `out`: string
- `dry_run`: boolean

### `solidworks_visual_validate`

**Capability scope**

- Blocks missing screenshots or explicit visual contradictions against a report.

**Limits and notes**

- Does not automatically understand every geometry detail.

**Required parameters**

- `report`: string

**Optional parameters**

- `screenshots`: array
- `visual_review`: string
- `out`: string

### `solidworks_export`

**Capability scope**

- Exports a document to a target file; the suffix controls the format.

**Limits and notes**

- Export success does not prove mate, clearance, or geometry correctness.

**Required parameters**

- `target`: string

**Optional parameters**

- `model`: string
- `out`: string

## Macros, Handoff, And Catalog Tools

| Tool | Purpose |
| --- | --- |
| `solidworks_template_macro` | Generate reviewable VBA macro for common mechanical part templates such as sleeve, spacer, flange, endcap, adapter, and retainer. |
| `solidworks_mate_macro` | Generate reviewable VBA macro for adding a mate between two preselected entities. |
| `solidworks_mate_group_macro` | Generate reviewable preselect VBA macro drafts from a mate group plan. Each macro still requires live entity preselection and review before running. |
| `solidworks_worklog` | Append a durable worklog event for multi-turn decisions, assumptions, verification, failures, and next steps. |
| `solidworks_handoff_bundle` | Create a compact handoff bundle with inspect JSON, context pack, worklog summary, README, and manifest. |
| `solidworks_tool_catalog` | Generate a grouped catalog of all SolidWorks Codex MCP tools and when to use them. |
| `solidworks_offline_demo` | Generate a 5-minute offline demo bundle for GitHub readers without requiring SolidWorks to be open. |
| `solidworks_audit` | Run the offline verification gate for this SolidWorks Codex toolchain. |
| `solidworks_finalize` | Generate the final readiness Markdown/JSON report after running audit. |
| `solidworks_existing_mcp_tools` | List tools exposed by installed npm solidworks-mcp-server in mock mode. |

### `solidworks_template_macro`

**Capability scope**

- Generates reviewable VBA part-template macros for sleeve, spacer, flange, endcap, motor adapter, and bearing retainer.

**Limits and notes**

- Macros are drafts and should not be blindly replayed.

**Required parameters**

- `template`: string; enum: sleeve, spacer, flange, endcap, motor_adapter, bearing_retainer

**Optional parameters**

- `out`: string
- `manifest`: string
- `outer_diameter_mm`: number
- `inner_diameter_mm`: number
- `length_mm`: number
- `thickness_mm`: number
- `center_bore_mm`: number
- `hole_count`: integer
- `hole_pcd_mm`: number
- `hole_diameter_mm`: number
- `plate_width_mm`: number
- `plate_height_mm`: number
- `motor_hole_x_mm`: number
- `motor_hole_y_mm`: number
- `bearing_outer_diameter_mm`: number
- `recess_depth_mm`: number

### `solidworks_mate_macro`

**Capability scope**

- Generates a reviewable macro for one mate between two preselected entities.

**Limits and notes**

- Requires correct preselection; complex attachments should use mate groups.

**Required parameters**

- `mate`: string; enum: coincident, concentric, tangent, distance, limit_distance, angle, limit_angle, parallel, perpendicular, symmetry, cam, cam_follower, gear, path, slot

**Optional parameters**

- `distance_mm`: number
- `distance_min_mm`: number
- `distance_max_mm`: number
- `angle_deg`: number
- `angle_min_deg`: number
- `angle_max_deg`: number
- `gear_ratio_numerator`: number
- `gear_ratio_denominator`: number
- `slot_constraint_type`: integer
- `slot_distance_mm`: number
- `slot_percent`: number
- `flip`: boolean
- `out`: string
- `manifest`: string

### `solidworks_mate_group_macro`

**Capability scope**

- Generates preselect macro drafts from a mate group plan.

**Limits and notes**

- Selectors still need review before live execution.

**Required parameters**

- `mate_group_plan`: string

**Optional parameters**

- `out_dir`: string
- `manifest`: string

### `solidworks_worklog`

**Capability scope**

- Appends durable worklog events.

**Limits and notes**

- Only useful when updated consistently.

**Required parameters**

- `message`: string

**Optional parameters**

- `event`: string; enum: note, decision, assumption, verification, failure, manual_action, next_step
- `session_name`: string
- `artifact`: array
- `next`: string
- `log`: string
- `summary_out`: string

### `solidworks_handoff_bundle`

**Capability scope**

- Creates a compact handoff bundle with inspect JSON, context, worklog summary, README, and manifest.

**Limits and notes**

- Packages existing evidence.

**Required parameters**

- `report`: string

**Optional parameters**

- `worklog`: string
- `focus`: string
- `out_dir`: string

### `solidworks_tool_catalog`

**Capability scope**

- Generates a grouped tool catalog.

**Limits and notes**

- Descriptions come from current MCP schema.

**Required parameters**

- None

**Optional parameters**

- `out`: string
- `json_out`: string

### `solidworks_offline_demo`

**Capability scope**

- Generates an offline demo bundle without SolidWorks.

**Limits and notes**

- Demo output is not live CAD validation.

**Required parameters**

- None

**Optional parameters**

- `out_dir`: string

### `solidworks_audit`

**Capability scope**

- Runs the offline verification gate.

**Limits and notes**

- Offline audit does not replace live SolidWorks validation.

**Required parameters**

- None

**Optional parameters**

- `out`: string

### `solidworks_finalize`

**Capability scope**

- Generates readiness Markdown/JSON after audit.

**Limits and notes**

- Output belongs in reports, not core docs.

**Required parameters**

- None

**Optional parameters**

- `out`: string
- `json_out`: string

### `solidworks_existing_mcp_tools`

**Capability scope**

- Lists external npm solidworks-mcp-server mock tools.

**Limits and notes**

- External reference only.

**Required parameters**

- None

**Optional parameters**

- None

