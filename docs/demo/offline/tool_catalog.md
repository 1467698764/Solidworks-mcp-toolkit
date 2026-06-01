# SolidWorks MCP Tool Catalog

- Timestamp: `2026-06-01T21:45:52`
- Tool count: `35`

## Operator notes
- Do not blindly replay templates: inspect the current report, context, worklog, and handoff artifacts before choosing a tool.
- Before write operations, create a backup; change one variable at a time; then rebuild, inspect, and compare.
- Use handoff-bundle for pauses, session changes, and review handoff; use audit/finalize as release gates.

## Groups
- `analysis`: `solidworks_change_plan`, `solidworks_design_review`, `solidworks_issue_report`, `solidworks_report_context`, `solidworks_report_search`
- `export_verify`: `solidworks_audit`, `solidworks_compare_reports`, `solidworks_export`, `solidworks_finalize`, `solidworks_interference_check`, `solidworks_preflight`
- `external_reference`: `solidworks_existing_mcp_tools`
- `handoff`: `solidworks_handoff_bundle`, `solidworks_worklog`
- `macro_generation`: `solidworks_mate_macro`, `solidworks_template_macro`
- `other`: `solidworks_change_verify`, `solidworks_model_understand`, `solidworks_offline_demo`, `solidworks_session_snapshot`, `solidworks_tool_catalog`
- `read_only`: `solidworks_inspect`, `solidworks_mass_properties`, `solidworks_probe`, `solidworks_report_summary`, `solidworks_selection_report`, `solidworks_start_inspect`, `solidworks_start_probe`
- `write_guarded`: `solidworks_backup`, `solidworks_backup_status`, `solidworks_component_state`, `solidworks_rebuild`, `solidworks_restore_backup`, `solidworks_safe_set_dimension`, `solidworks_set_dimension`

## Tools
### `solidworks_audit`

- Group: `export_verify`
- Description: Run the offline verification gate for this SolidWorks Codex toolchain.
- Required: `<none>`
- Properties: `out`

### `solidworks_backup`

- Group: `write_guarded`
- Description: Create timestamped backups of .SLDPRT/.SLDASM/.SLDDRW files before modification.
- Required: `files`
- Properties: `files, out`

### `solidworks_backup_status`

- Group: `write_guarded`
- Description: Inspect a backup report and classify source files as unchanged, changed, missing, or restorable.
- Required: `report`
- Properties: `out, report`

### `solidworks_change_plan`

- Group: `analysis`
- Description: Generate a flexible evidence-first mechanical CAD change plan from an inspect JSON report and natural-language goal.
- Required: `report, goal`
- Properties: `goal, json_out, out, report, session_name`

### `solidworks_change_verify`

- Group: `other`
- Description: Verify a compare delta contains only expected dimensions, component changes, additions/removals, or feature type count changes.
- Required: `delta`
- Properties: `allow_component, allow_component_added, allow_component_removed, allow_dimension, allow_feature_type, delta, out`

### `solidworks_compare_reports`

- Group: `export_verify`
- Description: Compare two SolidWorks Codex inspect JSON reports.
- Required: `before, after`
- Properties: `after, before, json_out, out`

### `solidworks_component_state`

- Group: `write_guarded`
- Description: Change assembly component state by Component2.Name2: hide/show/suppress/unsuppress/fix/float.
- Required: `component, action`
- Properties: `action, component, out, save`

### `solidworks_design_review`

- Group: `analysis`
- Description: Generate a generic evidence-first mechanical CAD review from an inspect JSON report: findings, open questions, and candidate actions.
- Required: `report`
- Properties: `intent, json_out, out, report`

### `solidworks_existing_mcp_tools`

- Group: `external_reference`
- Description: List tools exposed by installed npm solidworks-mcp-server in mock mode.
- Required: `<none>`
- Properties: `<none>`

### `solidworks_export`

- Group: `export_verify`
- Description: Export active or specified SolidWorks document to target path. Format follows suffix.
- Required: `target`
- Properties: `model, out, target`

### `solidworks_finalize`

- Group: `export_verify`
- Description: Generate the final readiness Markdown/JSON report after running audit.
- Required: `<none>`
- Properties: `json_out, out`

### `solidworks_handoff_bundle`

- Group: `handoff`
- Description: Create a compact handoff bundle with inspect JSON, context pack, worklog summary, README, and manifest.
- Required: `report`
- Properties: `focus, out_dir, report, worklog`

### `solidworks_inspect`

- Group: `read_only`
- Description: Deep read-only inspect of active part/assembly: features, dimensions, components.
- Required: `<none>`
- Properties: `out`

### `solidworks_interference_check`

- Group: `export_verify`
- Description: Run conservative SolidWorks assembly interference detection and emit JSON.
- Required: `<none>`
- Properties: `out`

### `solidworks_issue_report`

- Group: `analysis`
- Description: Generate a practical issue/recommendation report from an inspect JSON report.
- Required: `report`
- Properties: `json_out, out, report`

### `solidworks_mass_properties`

- Group: `read_only`
- Description: Report mass properties for active or specified SolidWorks document.
- Required: `<none>`
- Properties: `model, out`

### `solidworks_mate_macro`

- Group: `macro_generation`
- Description: Generate reviewable VBA macro for adding a mate between two preselected entities.
- Required: `mate`
- Properties: `angle_deg, distance_mm, flip, manifest, mate, out`

### `solidworks_model_understand`

- Group: `other`
- Description: Build a compact task-scoped model understanding pack from an inspect report: baseline facts, relevant CAD objects, relationship hypotheses, risks, and next minimal queries.
- Required: `report`
- Properties: `json_out, out, report, task, view`

### `solidworks_offline_demo`

- Group: `other`
- Description: Generate a 5-minute offline demo bundle for GitHub readers without requiring SolidWorks to be open.
- Required: `<none>`
- Properties: `out_dir`

### `solidworks_preflight`

- Group: `export_verify`
- Description: Run deterministic environment/toolchain preflight before touching a real SolidWorks model.
- Required: `<none>`
- Properties: `out`

### `solidworks_probe`

- Group: `read_only`
- Description: Read-only attach to an already-running SolidWorks instance and summarize active document.
- Required: `<none>`
- Properties: `out`

### `solidworks_rebuild`

- Group: `write_guarded`
- Description: Rebuild active or specified SolidWorks document; optionally save.
- Required: `<none>`
- Properties: `model, out, save`

### `solidworks_report_context`

- Group: `analysis`
- Description: Build a freeform handoff/context pack from an inspect report: inventory, risks, anchors, and next commands.
- Required: `report`
- Properties: `focus, json_out, out, report`

### `solidworks_report_search`

- Group: `analysis`
- Description: Search an inspect JSON report for components, dimensions, and features by text/state when names are messy.
- Required: `report`
- Properties: `json_out, kind, out, query, report, state`

### `solidworks_report_summary`

- Group: `read_only`
- Description: Summarize a SolidWorks Codex JSON probe/inspect report into Markdown.
- Required: `report`
- Properties: `out, report`

### `solidworks_restore_backup`

- Group: `write_guarded`
- Description: Dry-run or apply restoration from a SolidWorks Codex backup report. apply=false only validates and plans.
- Required: `report`
- Properties: `apply, out, report`

### `solidworks_safe_set_dimension`

- Group: `write_guarded`
- Description: Run a guarded one-dimension edit pipeline: backup, inspect, set dimension, rebuild, inspect, compare, and verify only that dimension changed.
- Required: `model, dimension, value_m`
- Properties: `dimension, model, out, out_dir, save, value_m`

### `solidworks_selection_report`

- Group: `read_only`
- Description: Report current SolidWorks selection set for safe preselected-entity mate workflows.
- Required: `<none>`
- Properties: `out, start`

### `solidworks_session_snapshot`

- Group: `other`
- Description: Create a work-session package: inspect JSON, summary Markdown, issue report, manifest.
- Required: `<none>`
- Properties: `from_report, name, out_dir, start`

### `solidworks_set_dimension`

- Group: `write_guarded`
- Description: Set one SolidWorks dimension by full parameter name. Value is SystemValue in meters. Use save only after backup.
- Required: `dimension, value_m`
- Properties: `dimension, model, out, save, value_m`

### `solidworks_start_inspect`

- Group: `read_only`
- Description: Allow COM launch of SolidWorks, then run deep read-only inspect.
- Required: `<none>`
- Properties: `out`

### `solidworks_start_probe`

- Group: `read_only`
- Description: Allow COM launch of SolidWorks, then summarize active document.
- Required: `<none>`
- Properties: `out`

### `solidworks_template_macro`

- Group: `macro_generation`
- Description: Generate reviewable VBA macro for common mechanical part templates such as sleeve, spacer, flange, endcap, adapter, and retainer.
- Required: `template`
- Properties: `bearing_outer_diameter_mm, center_bore_mm, hole_count, hole_diameter_mm, hole_pcd_mm, inner_diameter_mm, length_mm, manifest, motor_hole_x_mm, motor_hole_y_mm, out, outer_diameter_mm, plate_height_mm, plate_width_mm, recess_depth_mm, template, thickness_mm`

### `solidworks_tool_catalog`

- Group: `other`
- Description: Generate a grouped catalog of all SolidWorks Codex MCP tools and when to use them.
- Required: `<none>`
- Properties: `json_out, out`

### `solidworks_worklog`

- Group: `handoff`
- Description: Append a durable worklog event for multi-turn decisions, assumptions, verification, failures, and next steps.
- Required: `message`
- Properties: `artifact, event, log, message, next, session_name, summary_out`
