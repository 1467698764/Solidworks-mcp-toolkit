# SolidWorks Codex Handoff Bundle

- Created: `2026-06-05T09:08:19`
- Focus: `current model evidence, constraints, clearance, and manufacturing gaps`
- Document: `sample_machine.SLDASM`
- Source report: `tools/solidworks_codex/sandbox/report_after.json`

## Principle
Do not blindly replay templates: read `context.md`, `worklog.md`, and the source inspect JSON before choosing the next step for the current model.

## Files
- README.md: `handoff instructions`
- inspect.json: `copied source inspect report`
- context.md: `human-readable context pack`
- context.json: `machine-readable context pack`
- worklog.jsonl: `copied durable event log`
- worklog.md: `human-readable worklog summary`

## Suggested first actions
1. Read `context.md` for inventory, risks, anchors, and suggested commands.
2. Read `worklog.md` for prior decisions, assumptions, verification, failures, and next steps.
3. If making any write, run backup first and change one variable at a time.
4. Rebuild, inspect, compare, and append worklog events after meaningful decisions.

## Recent worklog excerpt
# SolidWorks Codex Worklog

- Log: `docs/demo/offline/handoff/worklog.jsonl`
- Events: `7`

## Session `offline-demo`

### 2026-06-01T16:12:34 `decision`

Use report-context and tool-catalog before any template or write operation

Artifacts:
- `context.md`

Next: Generate handoff bundle

### 2026-06-01T18:15:21 `decision`

Use report-context and tool-catalog before any template or write operation

Artifacts:
- `context.md`

Next: Generate handoff bundle

### 2026-06-01T20:08:49 `decision`

Use report-context and tool-catalog before any template or write operation

Artifacts:
- `context.md`

Next: Generate handoff bundle

### 2026-06-01T20:30:04 `decision`

Use report-context and tool-catalog before any template or write operation

Artifacts:
- `context.md`

Next: Generate handoff bundle

### 2026-06-01T21:04:50 `decision`

Use report-context and tool-catalog before any template or write operation

Artifacts:
- `context.md`

Next: Generate handoff bundle

### 2026-06-01T21:45:52 `decision`

Use report-context and tool-catalog before any template or write operation

Artifacts:
- `context.md`

Next: Generate handoff bundle

### 2026-06-05T09:08:19 `decision`

Use report-context and tool-catalog before any template or write operation

Artifacts:
- `context.md`

Next: Generate handoff bundle
