# MCP Tool Manual

SolidWorks Codex MCP currently exposes **59 tools**. The tools are grouped by engineering workflow, not by implementation file, so a human or AI agent can choose the correct operation without scanning source code.

Compatibility anchor for older gates: `56 MCP tools`.

## Calling Rules

- MCP inputs are JSON objects.
- Use absolute paths for native `.SLDPRT`, `.SLDASM`, and `.SLDDRW` files when possible.
- Repository-relative paths are acceptable for specs, reports, screenshots, and handoff artifacts.
- Tools with `start` may launch SolidWorks. Other live tools normally attach to an existing SolidWorks session.
- Use `dry_run: true` where available before live mutation.
- Any native write should be backed by backup, rebuild, inspect/readback, validation, and worklog evidence.
- Direct SolidWorks API calls are allowed when faster or more reliable, but they must preserve the same evidence contract as the MCP tool.

## Capability Scope

The MCP layer strengthens the AI at the points where raw SolidWorks API calls are weakest:

Glossary aliases used by tests and older handoffs: Capability scope, Limits and notes, Required parameters, Optional parameters.

| Stage | What MCP Adds | Typical Tools |
| --- | --- | --- |
| Intent | Design intent, assumptions, validation profile, runtime budget, non-goals. | `solidworks_workflow_plan`, `solidworks_change_plan`, `solidworks_ai_capability_map` |
| Readback | Compact model evidence from native files and inspect reports. | `solidworks_inspect`, `solidworks_report_search`, `solidworks_model_understand` |
| Interface graph | Named faces, axes, slots, datums, proximity, selector confidence, host evidence. | `solidworks_interface_index`, `solidworks_assembly_diagnose` |
| Execution planning | Mate groups, affected subgraphs, standard-part hosts, selector checks. | `solidworks_mate_group_plan`, `solidworks_mate_group_validate`, `solidworks_standard_part_resolve` |
| Native execution | Guarded feature, component, metadata, mate, and motion operations. | `solidworks_part_feature_execute`, `solidworks_component_insert`, `solidworks_mate_intent_execute` |
| Validation | Rebuild health, deltas, geometry contracts, interference, screenshots, engineering-lite review. | `solidworks_rebuild`, `solidworks_change_verify`, `solidworks_part_geometry_validate`, `solidworks_visual_validate` |
| Handoff | Durable worklog and resumable bundles. | `solidworks_worklog`, `solidworks_report_context`, `solidworks_handoff_bundle` |

## Limits And Notes

- Read-only evidence is only as complete as SolidWorks COM readback allows.
- BBox-derived face or axis candidates are weak evidence until native identity or reviewed selector evidence confirms them.
- A mate count is not assembly quality. Intended degrees of freedom, axial locators, contacts, limits, and host interfaces matter.
- `solidworks_mate_intent_execute` is the preferred high-level assembly execution path when engineering intent is known.
- `solidworks_mate_group_execute` is best for reviewed selector-bearing macro manifests and repair groups.
- `solidworks_motion_sweep_lite` is a lightweight mechanism gate, not a full motion simulation.
- `solidworks_engineering_lite` is a handoff review, not manufacturing approval.

## Required Parameters And Optional Parameters

| Tool | Required parameters | Optional parameters |
| --- | --- | --- |
| `solidworks_ai_capability_map` | - | `out`, `json_out` |
| `solidworks_assembly_diagnose` | `report` | `out`, `lock_root`, `near_tolerance_m`, `standard_part_regex` |
| `solidworks_assembly_repair_plan` | `diagnosis` | `out`, `markdown_out` |
| `solidworks_assembly_review_pipeline` | `report` | `out_dir`, `near_tolerance_m`, `standard_part_regex` |
| `solidworks_audit` | - | `out` |
| `solidworks_backup` | `files` | `out` |
| `solidworks_backup_status` | `report` | `out` |
| `solidworks_change_plan` | `report`, `goal` | `session_name`, `out`, `json_out` |
| `solidworks_change_verify` | `delta` | `allow_dimension`, `allow_component`, `allow_component_added`, `allow_component_removed`, `allow_feature_type`, `require_allowed_change`, `out` |
| `solidworks_compare_reports` | `before`, `after` | `out`, `json_out` |
| `solidworks_component_insert` | `spec` | `model`, `start`, `save`, `dry_run`, `out` |
| `solidworks_component_state` | `component`, `action` | `save`, `out` |
| `solidworks_design_review` | `report` | `intent`, `out`, `json_out` |
| `solidworks_engineering_lite` | `report` | `out`, `json_out`, `out_dir` |
| `solidworks_existing_mcp_tools` | - | - |
| `solidworks_export` | `target` | `model`, `out` |
| `solidworks_feature_state` | `feature`, `action` | `dimension`, `value_m`, `target_feature`, `reorder_position`, `definition_spec`, `model`, `save`, `out` |
| `solidworks_finalize` | - | `out`, `json_out` |
| `solidworks_handoff_bundle` | `report` | `worklog`, `focus`, `out_dir` |
| `solidworks_inspect` | - | `model`, `out` |
| `solidworks_interference_check` | - | `model`, `out` |
| `solidworks_interface_index` | `report` | `out`, `near_tolerance_m`, `standard_part_regex` |
| `solidworks_issue_report` | `report` | `out`, `json_out` |
| `solidworks_mass_properties` | - | `model`, `out` |
| `solidworks_mate_group_execute` | `macro_manifest` | `dry_run`, `out` |
| `solidworks_mate_group_execution_check` | `macro_manifest`, `after_report` | `out` |
| `solidworks_mate_group_live_protocol` | `macro_manifest`, `validation_report` | `model`, `out`, `markdown_out` |
| `solidworks_mate_group_macro` | `mate_group_plan` | `out_dir`, `manifest` |
| `solidworks_mate_group_plan` | `repair_plan`, `interface_index` | `out`, `markdown_out` |
| `solidworks_mate_group_validate` | `mate_group_plan` | `out` |
| `solidworks_mate_intent_execute` | `intent_spec` | `dry_run`, `out` |
| `solidworks_mate_macro` | `mate` | `distance_mm`, `distance_min_mm`, `distance_max_mm`, `angle_deg`, `angle_min_deg`, `angle_max_deg`, `gear_ratio_numerator`, `gear_ratio_denominator`, `slot_constraint_type`, `slot_distance_mm`, `slot_percent`, `flip`, `out`, `manifest` |
| `solidworks_mate_selection_check` | `macro_manifest`, `selection_report` | `expected_mate_name`, `out` |
| `solidworks_metadata_execute` | `spec` | `model`, `start`, `save`, `dry_run`, `out` |
| `solidworks_model_understand` | `report` | `task`, `view`, `out`, `json_out` |
| `solidworks_motion_sweep_lite` | `spec` | `macro_manifest`, `model`, `dry_run`, `out` |
| `solidworks_offline_demo` | - | `out_dir` |
| `solidworks_part_feature_execute` | `spec` | `model`, `start`, `save`, `dry_run`, `out` |
| `solidworks_part_geometry_validate` | `report`, `contract` | `out` |
| `solidworks_preflight` | - | `out` |
| `solidworks_probe` | - | `out` |
| `solidworks_rebuild` | - | `model`, `save`, `out` |
| `solidworks_report_context` | `report` | `focus`, `out`, `json_out` |
| `solidworks_report_search` | `report` | `query`, `kind`, `state`, `out`, `json_out` |
| `solidworks_report_summary` | `report` | `out` |
| `solidworks_restore_backup` | `report` | `apply`, `out` |
| `solidworks_safe_set_dimension` | `model`, `dimension`, `value_m` | `save`, `out_dir`, `out` |
| `solidworks_selection_report` | - | `out`, `start` |
| `solidworks_session_snapshot` | - | `name`, `from_report`, `out_dir`, `start` |
| `solidworks_set_dimension` | `dimension`, `value_m` | `model`, `save`, `out` |
| `solidworks_standard_part_resolve` | `catalog`, `request` | `out`, `component_spec_out` |
| `solidworks_start_inspect` | - | `model`, `out` |
| `solidworks_start_probe` | - | `out` |
| `solidworks_template_macro` | `template` | `out`, `manifest`, `outer_diameter_mm`, `inner_diameter_mm`, `length_mm`, `thickness_mm`, `center_bore_mm`, `hole_count`, `hole_pcd_mm`, `hole_diameter_mm`, `plate_width_mm`, `plate_height_mm`, `motor_hole_x_mm`, `motor_hole_y_mm`, `bearing_outer_diameter_mm`, `recess_depth_mm` |
| `solidworks_tool_catalog` | - | `out`, `json_out` |
| `solidworks_visual_capture` | - | `out_dir`, `out`, `dry_run` |
| `solidworks_visual_validate` | `report` | `screenshots`, `visual_review`, `out` |
| `solidworks_worklog` | `message` | `event`, `session_name`, `artifact`, `next`, `log`, `summary_out` |
| `solidworks_workflow_plan` | `goal` | `intent`, `runtime_budget`, `out`, `json_out` |

## Tool Groups

### AI Reasoning And Tool Choice

| Tool | Purpose | Capability range | Upper limit |
| --- | --- | --- | --- |
| `solidworks_ai_capability_map` | Produces an AI-facing map of reasoning stages, MCP value, direct API policy, required parameters, optional parameters, and limits. | Best first call for long or ambiguous CAD work. | It guides tool choice; it does not inspect or mutate CAD files. |
| `solidworks_tool_catalog` | Generates a grouped catalog from current MCP schemas. | Useful for schema discovery and handoff. | It does not explain engineering workflow as deeply as the AI capability map. |
| `solidworks_existing_mcp_tools` | Lists tools from an external npm SolidWorks MCP server in mock mode. | Reference only. | Not part of the verified local toolchain. |

### Read, Search, And Understand Models

| Tool | Purpose | Capability range | Upper limit |
| --- | --- | --- | --- |
| `solidworks_probe` | Attach read-only to a running SolidWorks instance and summarize the active document. | Fast session check. | No deep feature, mate, or component readback. |
| `solidworks_start_probe` | Launch SolidWorks if needed, then probe. | Startup discovery. | Startup cost and no deep readback. |
| `solidworks_inspect` | Deep read-only inspect of active or specified parts, assemblies, and drawings. | Features, dimensions, components, mates, transforms, handoff metadata. | Hidden, lightweight, failed, or unsupported COM state may be incomplete. |
| `solidworks_start_inspect` | Launch SolidWorks if needed, then inspect. | Live readback from cold session. | Slower than attaching to an existing session. |
| `solidworks_mass_properties` | Read mass properties for active or specified documents. | Mass, center of mass, inertia where available. | Material/density gaps make mass evidence weak. |
| `solidworks_selection_report` | Capture current SolidWorks selection identity evidence. | Preselected face/axis/edge/point workflows and selector patches. | It reports selections; it does not select or mate by itself. |
| `solidworks_session_snapshot` | Package inspect, summary, issue report, and manifest. | Quick session capture. | Snapshot is context, not acceptance. |
| `solidworks_report_summary` | Summarize probe or inspect JSON into Markdown. | Human-readable digest. | Summary only; no diagnosis. |
| `solidworks_report_search` | Search report evidence by text, kind, and state. | Finds messy component, dimension, and feature names. | No result means no report evidence, not no CAD object. |
| `solidworks_report_context` | Build task handoff context from an inspect report. | Inventory, risks, anchors, next commands. | It is reasoning support, not execution. |
| `solidworks_model_understand` | Build task-scoped understanding from report evidence. | Baseline facts, relevant objects, relationship hypotheses, risks, next queries. | Hypotheses must be validated before mutation. |

### Safety Gates And Change Verification

| Tool | Purpose | Capability range | Upper limit |
| --- | --- | --- | --- |
| `solidworks_backup` | Create timestamped backups of native files. | File-level rollback before mutation. | Does not understand CAD intent. |
| `solidworks_backup_status` | Classify backup sources as unchanged, changed, missing, or restorable. | Rollback readiness. | Requires a previous backup report. |
| `solidworks_restore_backup` | Dry-run or apply restoration from a backup report. | Recovery after failed mutation. | `apply: true` overwrites source files. |
| `solidworks_set_dimension` | Set one fully-qualified dimension value in meters. | Precise parameter edit. | Use after backup; not a multi-edit pipeline. |
| `solidworks_safe_set_dimension` | Backup, inspect, set dimension, rebuild, inspect, compare, and verify one dimension. | Guarded single-dimension edit. | Not for topology surgery. |
| `solidworks_rebuild` | Rebuild active or specified document and optionally save. | Rebuild health and save evidence. | Rebuild success is not design acceptance. |
| `solidworks_compare_reports` | Compare two inspect reports. | Delta evidence. | Only compares fields present in reports. |
| `solidworks_change_verify` | Verify report deltas against allow lists. | Blocks unintended dimensions, components, feature-type changes. | Allow lists must be precise. |
| `solidworks_preflight` | Check runtime, process, generated roots, locks, and environment. | Offline gate before live work. | Does not validate a specific model. |

### Execution-Layer Write Tools

| Tool | Purpose | Capability range | Upper limit |
| --- | --- | --- | --- |
| `solidworks_component_state` | Hide, show, suppress, unsuppress, fix, or float one component. | Exact `Component2.Name2` state changes. | Ambiguous component names block reliable execution. |
| `solidworks_component_insert` | Insert reviewed part or assembly specs. | Origin, configuration, fixed state, dry-run evidence. | Insertion is not attachment; mate intent must follow. |
| `solidworks_standard_part_resolve` | Resolve a local standard-part request into insertion and host intent. | Local catalog, source policy, supplier/license evidence, host attachment intent. | Does not download from the internet. |
| `solidworks_feature_state` | Suppress, unsuppress, delete, dimension edit, reorder, or definition edit a feature. | Feature tree operations with before/after evidence. | Complex sketch surgery belongs in reviewed part feature specs. |
| `solidworks_part_feature_execute` | Execute reviewed part feature specs. | Extrude boss/cut, revolve boss/cut, holes, slots, pockets, fillet, chamfer, patterns, mirror. | Requires reviewed selectors; must not guess faces or axes. |
| `solidworks_metadata_execute` | Write reviewed material and custom properties. | BOM and handoff metadata. | Does not judge material suitability. |
| `solidworks_mate_group_execute` | Execute reviewed mate group selector manifests. | SelectByID2, AddMate5, suppress/delete repair actions, rebuild evidence, dry-run selector planning. | Live execution depends on selector resolution and solver health. |
| `solidworks_mate_intent_execute` | Execute engineering-level mate intents. | Rigid mount, revolute, prismatic, slot-pin, gear pair, axial locators, limit evidence. | Needs explicit interfaces and intended DOF; decorative mates are rejected by validation. |
| `solidworks_motion_sweep_lite` | Sample mechanism driver positions and check rebuild/interference evidence. | Light slider-crank, quick-return, slot-pin, and driver-dimension sweeps. | Not full dynamic simulation. |

### Assembly Diagnosis And Mate Chain

| Tool | Purpose | Capability range | Upper limit |
| --- | --- | --- | --- |
| `solidworks_assembly_diagnose` | Diagnose assembly evidence. | Inventory, fixed/floating, mate graph, bad mates, isolated components, bbox gaps, standard-part host gaps, locks. | BBox clearance is approximate. |
| `solidworks_assembly_repair_plan` | Create local repair plan from diagnosis. | Affected subgraphs, rollback preconditions, repair ordering. | Plans only. |
| `solidworks_interface_index` | Build component/interface index. | Planar, cylindrical, slot/path, coordinate-system, proximity, native identity handoff. | Weak candidates need review or live identity capture. |
| `solidworks_mate_group_plan` | Convert repair and interface evidence into mate group candidates. | Grouped mates, components, evidence, verification gates. | Still requires validation before live execution. |
| `solidworks_mate_group_validate` | Validate mate group structure. | Component count, supported mate types, DOF expectation, axial locator evidence, selector availability. | Does not prove live selection will succeed. |
| `solidworks_mate_selection_check` | Compare selection report with mate macro manifest. | Preselected entity safety gate. | Does not add mates. |
| `solidworks_mate_group_execution_check` | Check after-inspect evidence for expected mate execution. | Expected mate names, suppression state, solver/API errors. | Requires fresh after-inspect report. |
| `solidworks_mate_group_live_protocol` | Generate live work order for a reviewed mate group. | Backup, selection, macro, rebuild, inspect, execution check, interference, cleanup. | Protocol only; does not run every step. |
| `solidworks_assembly_review_pipeline` | Run diagnosis, interface indexing, repair plan, mate plan, and manifest artifacts from one report. | Read-only assembly review bundle. | Does not execute repairs. |
| `solidworks_interference_check` | Run conservative assembly interference detection. | Active or specified assembly, source metadata, collision pair evidence where available. | Contact interpretation may need section or visual review. |

### Validation, Engineering Review, And Export

| Tool | Purpose | Capability range | Upper limit |
| --- | --- | --- | --- |
| `solidworks_design_review` | Evidence-first mechanical CAD review. | Findings, questions, candidate actions. | Read-only and report-bound. |
| `solidworks_change_plan` | Generate change plan from report and goal. | Scope, risk, commands, validation sequence. | Does not execute. |
| `solidworks_workflow_plan` | Generate intent-scoped CAD workflow from a natural-language goal. | Design intent, validation profile, runtime budget, assumptions, non-goals, execution gates, next tool sequence. | It plans; execution still requires reviewed specs and live validation. |
| `solidworks_issue_report` | Produce practical issues and recommendations. | Quick review of inspect evidence. | Not an acceptance gate. |
| `solidworks_engineering_lite` | BOM, drawing BOM CSV, material, DFM, and DFA review. | Engineering handoff lite. | Not manufacturing release. |
| `solidworks_part_geometry_validate` | Validate part report against geometry contract. | Body count, bbox, volume, required features, semantic counts, interfaces. | Only validates present report evidence. |
| `solidworks_visual_capture` | Capture SolidWorks window screenshots or dry-run placeholder. | Screenshot manifest for visual evidence. | Screenshots need review context. |
| `solidworks_visual_validate` | Validate screenshot evidence and reviewed findings against report. | Blocks missing screenshots or visual contradictions. | Does not automatically understand every geometry detail. |
| `solidworks_export` | Export active or specified document by target suffix. | STEP/PDF/image-like export where SolidWorks supports it. | Export success does not prove CAD correctness. |

### Macros, Handoff, And Generated Artifacts

| Tool | Purpose | Capability range | Upper limit |
| --- | --- | --- | --- |
| `solidworks_template_macro` | Generate reviewable VBA part-template macros. | Sleeve, spacer, flange, endcap, motor adapter, bearing retainer. | Draft macro only. |
| `solidworks_mate_macro` | Generate reviewable VBA for one preselected mate. | Coincident, concentric, tangent, distance, limit distance, angle, limit angle, parallel, perpendicular, symmetry, cam, cam follower, gear, path, slot. | Requires correct preselection. |
| `solidworks_mate_group_macro` | Generate preselect macro drafts from mate group plan. | Repair or grouped mate manifest drafting. | Selectors still need review. |
| `solidworks_worklog` | Append durable multi-turn work events. | Decisions, assumptions, verification, failures, manual actions, next steps. | Only useful if kept current. |
| `solidworks_handoff_bundle` | Package inspect, context, worklog summary, README, and manifest. | Resume and review bundles. | Packages existing evidence. |
| `solidworks_offline_demo` | Generate offline demo bundle. | GitHub demo without SolidWorks. | Demo output is not live CAD validation. |
| `solidworks_audit` | Run offline verification gate. | Tests and repository readiness checks. | Does not replace live validation. |
| `solidworks_finalize` | Generate final readiness report after audit. | Release/handoff summary. | Report belongs in generated artifacts, not source docs. |

## Recommended Workflows

### Concept To Model

1. `solidworks_ai_capability_map`
2. `solidworks_workflow_plan`
3. `solidworks_part_feature_execute`
4. `solidworks_component_insert`
5. `solidworks_interface_index`
6. `solidworks_mate_intent_execute`
7. `solidworks_rebuild`
8. `solidworks_inspect`
9. `solidworks_part_geometry_validate` or `solidworks_interference_check`
10. `solidworks_visual_validate`
11. `solidworks_handoff_bundle`

### Existing Assembly Repair

1. `solidworks_inspect`
2. `solidworks_assembly_diagnose`
3. `solidworks_interface_index`
4. `solidworks_assembly_repair_plan`
5. `solidworks_mate_group_plan`
6. `solidworks_mate_group_validate`
7. `solidworks_mate_group_execute` or `solidworks_mate_intent_execute`
8. `solidworks_mate_group_execution_check`
9. `solidworks_interference_check`
10. `solidworks_handoff_bundle`

### Mechanism Lite

1. Declare revolute, prismatic, slot, cam, gear, limit, and axial-locator intent.
2. Use `solidworks_mate_intent_execute` for human-engineer-style joint semantics.
3. Use `solidworks_motion_sweep_lite` for sampled positions.
4. Use `solidworks_interference_check` and visual validation before handoff.

## Parameter Notes

- `model`: optional native SolidWorks file to open before a live operation.
- `out`: JSON report path unless the tool explicitly documents Markdown output.
- `json_out`: paired JSON path for tools that also write Markdown.
- `report`: existing JSON evidence file; meaning depends on the tool.
- `manifest`: CLI name for many reviewed specs; MCP schemas use clearer names such as `macro_manifest`, `contract`, or `intent_spec`.
- `dry_run`: validate schema/selectors and write planned evidence without live mutation where supported.
- `save`: write native file changes. Use only after backup and when validation plan allows saving.
