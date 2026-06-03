# SolidWorks Codex Capability Matrix

- Timestamp: `2026-06-03T19:15:11`
- Capability count: `50`

## Coverage

- CLI commands: `50`
- MCP tools: `36`
- MCP tools mapped to CLI: `36`
- CLI for every local MCP tool: `True`
- Safety label for every capability: `True`
- Workflow label for every capability: `True`

## Operator notes

- Prefer read-only discovery before guarded edits.
- Use backup before write commands and compare after rebuild/inspect.
- Use handoff artifacts when a task spans multiple Codex turns.

## Matrix

| CLI | MCP | Workflow | Safety | SolidWorks required | Required args |
| --- | --- | --- | --- | --- | --- |
| `assembly-contract` | `-` | `verify_export` | `verification_or_export` | `False` | `-` |
| `assembly-diagnose` | `solidworks_assembly_diagnose` | `analysis` | `read_only` | `False` | `report` |
| `audit` | `solidworks_audit` | `release_gate` | `offline_gate` | `False` | `-` |
| `backup` | `solidworks_backup` | `guarded_edit` | `guarded_write` | `False` | `files` |
| `backup-status` | `solidworks_backup_status` | `guarded_edit` | `guarded_write` | `False` | `report` |
| `capability-matrix` | `-` | `release_gate` | `offline_gate` | `False` | `-` |
| `change-plan` | `solidworks_change_plan` | `analysis` | `read_only` | `False` | `report, goal` |
| `change-verify` | `solidworks_change_verify` | `verify_export` | `verification_or_export` | `False` | `delta` |
| `compare` | `solidworks_compare_reports` | `verify_export` | `verification_or_export` | `False` | `before, after` |
| `component-state` | `solidworks_component_state` | `guarded_edit` | `guarded_write` | `True` | `component, action` |
| `design-review` | `solidworks_design_review` | `analysis` | `read_only` | `False` | `report` |
| `export` | `solidworks_export` | `verify_export` | `verification_or_export` | `True` | `target` |
| `finalize` | `solidworks_finalize` | `release_gate` | `offline_gate` | `False` | `-` |
| `github-readiness` | `-` | `release_gate` | `offline_gate` | `False` | `-` |
| `handoff-bundle` | `solidworks_handoff_bundle` | `handoff` | `offline_or_read_only` | `False` | `report` |
| `inspect` | `solidworks_inspect` | `discover` | `read_only` | `True` | `-` |
| `interference` | `solidworks_interference_check` | `verify_export` | `verification_or_export` | `True` | `-` |
| `issue-report` | `solidworks_issue_report` | `analysis` | `read_only` | `False` | `report` |
| `live-gate` | `-` | `release_gate` | `offline_gate` | `True` | `-` |
| `mass` | `solidworks_mass_properties` | `discover` | `read_only` | `True` | `-` |
| `mate-macro` | `solidworks_mate_macro` | `macro_generation` | `generated_reviewable_artifact` | `False` | `mate` |
| `mcp-tools` | `solidworks_existing_mcp_tools` | `external_reference` | `offline_reference` | `False` | `-` |
| `model-understand` | `solidworks_model_understand` | `analysis` | `read_only` | `False` | `report` |
| `offline-demo` | `solidworks_offline_demo` | `handoff` | `offline_or_read_only` | `False` | `-` |
| `preflight` | `solidworks_preflight` | `release_gate` | `offline_gate` | `False` | `-` |
| `probe` | `solidworks_probe` | `discover` | `read_only` | `True` | `-` |
| `public-copy-guard` | `-` | `release_gate` | `offline_gate` | `False` | `-` |
| `rebuild` | `solidworks_rebuild` | `guarded_edit` | `guarded_write` | `True` | `-` |
| `release-tree` | `-` | `release_gate` | `offline_gate` | `False` | `-` |
| `repo-health` | `-` | `release_gate` | `offline_gate` | `False` | `-` |
| `report-context` | `solidworks_report_context` | `analysis` | `read_only` | `False` | `report` |
| `report-search` | `solidworks_report_search` | `analysis` | `read_only` | `False` | `report` |
| `restore-backup` | `solidworks_restore_backup` | `guarded_edit` | `guarded_write` | `False` | `report` |
| `safe-set-dimension` | `solidworks_safe_set_dimension` | `guarded_edit` | `guarded_write` | `True` | `model, dimension, value_m` |
| `selection-report` | `solidworks_selection_report` | `discover` | `read_only` | `True` | `-` |
| `session-snapshot` | `solidworks_session_snapshot` | `handoff` | `offline_or_read_only` | `False` | `-` |
| `set-dimension` | `solidworks_set_dimension` | `guarded_edit` | `guarded_write` | `True` | `dimension, value_m` |
| `start-component-state` | `-` | `guarded_edit` | `guarded_write` | `True` | `-` |
| `start-inspect` | `solidworks_start_inspect` | `discover` | `read_only` | `True` | `-` |
| `start-interference` | `-` | `verify_export` | `verification_or_export` | `True` | `-` |
| `start-mass` | `-` | `discover` | `read_only` | `True` | `-` |
| `start-probe` | `solidworks_start_probe` | `discover` | `read_only` | `True` | `-` |
| `start-rebuild` | `-` | `guarded_edit` | `guarded_write` | `True` | `-` |
| `start-selection-report` | `-` | `discover` | `read_only` | `True` | `-` |
| `start-session-snapshot` | `-` | `handoff` | `offline_or_read_only` | `True` | `-` |
| `summary` | `solidworks_report_summary` | `discover` | `read_only` | `False` | `report` |
| `template-macro` | `solidworks_template_macro` | `macro_generation` | `generated_reviewable_artifact` | `False` | `template` |
| `tool-catalog` | `solidworks_tool_catalog` | `handoff` | `offline_or_read_only` | `False` | `-` |
| `workflow-plan` | `-` | `analysis` | `read_only` | `False` | `Target` |
| `worklog` | `solidworks_worklog` | `handoff` | `offline_or_read_only` | `False` | `message` |
