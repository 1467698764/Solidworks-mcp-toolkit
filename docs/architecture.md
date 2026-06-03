# Architecture

SolidWorks Codex MCP is a conservative, evidence-first control layer for multi-turn CAD work. It favors inspectable state, narrow edits, live readback, and reproducible handoff over a large unguarded API surface.

## Layer map

```text
Codex / MCP client
  -> tools/solidworks_codex/mcp/server.cjs
  -> tools/solidworks_codex/swctl.ps1
  -> tools/solidworks_codex/scripts/*.py
  -> SolidWorks COM automation or offline JSON fixtures
  -> reports, handoff bundles, exports, generated macros, or native .SLDASM/.SLDPRT artifacts
```

## Runtime boundaries

- `server.cjs` exposes 37 MCP tools and translates tool arguments into `swctl.ps1` commands.
- `swctl.ps1` is the stable command router used by humans, tests, CI, and MCP.
- Python scripts implement focused operations: inspect, summary, compare, model-understand, worklog, handoff, release gates, validation profiles, and guarded write helpers.
- SolidWorks COM is only touched by commands that need live model state or model mutation. Offline gates use fixtures and generated reports.
- Live validation is opt-in and serial. It avoids parallel SolidWorks sessions because COM automation, hidden windows, file locks, and memory pressure are part of the system boundary.

## Data flow

1. Read-only commands produce JSON or Markdown evidence reports.
2. Analysis commands consume inspect/session reports and generate context, search results, design reviews, change plans, model understanding, or handoff bundles.
3. Write commands stay narrow: backup first, one dimension/component/feature workflow at a time, rebuild, inspect, compare, verify.
4. Assembly contract commands convert user intent into reusable evidence gates: component existence, Transform/origin placement, part shape/feature semantics, semantic mate network, suppressed/fixed state, mate error/status when reported, and participation evidence. They support blocking/warning/not_applicable severities so contract evidence can stay profile-aware.
5. Release commands validate the repository itself: GitHub readiness, repo health, public copy guard, release-tree, audit, capability matrix, and finalize.

## Validation architecture

The project separates validation into four practical layers:

- Geometry: native artifacts, part shape semantics, required feature-name/semantic readback, part_geometry_readback bbox/body/volume evidence, rebuild health, static interference, clearance tolerance.
- Assembly: mate semantics, component placements, fixed/suppressed state, functional adjacency, constraint/DOF intent, motion sweep collision.
- Engineering: mass properties, DFM/DFA screens, BOM metadata, strength/stiffness screen, drawing/BOM readiness.
- MCP quality: evidence completeness, traceability, model-understand usefulness, public-copy hygiene, release-tree cleanliness.

`validation profiles` keep this proportional to intent: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release`. `runtime_budget` can downgrade expensive checks for fast feedback, and `extra_checks` lets a reasoning model add task-specific gates without making every heavy check globally mandatory.

## Live gate architecture

Live gate is where runtime truth outranks source assumptions. It validates SolidWorks-native behavior through three gates:

- `live_session_smoke` proves the minimal COM/session/mate/interference/cleanup path.
- `live_capability_suite` proves feature creation and edit primitives: extrude, cut, revolve, revolved cut, sketch dimension read/modify/rebuild/save, assembly insert, concentric mate, distance mate, interference, mass, component placement readback, part_geometry_readback from reopened native parts, close/cleanup.
- `complete_shaper_v5` is retained as a simple-mechanism regression fixture. It is useful only when it exposes generic assembly-control gaps: component inventory, native placement/readback, part feature evidence, semantic mate participation, fixed/floating policy, interference, visual coherence, and cleanup. It is not architectural proof that general mechanism assembly is solved.

No single named fixture is the product boundary. The architecture should make ordinary mechanical parts and assemblies routine through design intent, interface indexing, local repair, profile-scoped validation, and native readback.

## Safety model

- Generated artifacts go under ignored runtime directories unless intentionally promoted as fixtures or demo assets.
- Real CAD edits should be backed up, rebuilt, inspected, and compared before saving or committing.
- Macro generation creates reviewable `.swp.vba` text; it does not run macros automatically.
- `release-tree` checks that reports, backups, exports, generated macros, caches, logs, and personal config paths are not Git-visible.
- `CleanupStale` is bounded to known generated stale fixture directories and must not delete unrelated workspace files.
- Public copy guard prevents rank-boasting language, personal scenario leakage, and mojibake in release-facing files.

## Handoff model

Long-running CAD work needs durable context. `report-context`, `model-understand`, `worklog`, `handoff-bundle`, and `tool-catalog` preserve facts, decisions, failed attempts, verification evidence, and next-step options without forcing one fixed template workflow.

## Offline and live evaluation

Offline tests and fixtures keep CI fast and deterministic. Live SolidWorks remains necessary for COM inspection, rebuild, export, mass properties, model mutation, actual mate creation, interference callbacks, and file-lock cleanup. STEP optional smoke can supplement native validation, but `.SLDASM/.SLDPRT` remains the deliverable for assembly work.

## Extension points

- Add new operations as focused Python scripts first.
- Route them through `swctl.ps1` with explicit parameters.
- Expose MCP tools only after there is a CLI path and test coverage.
- Add validation-profile coverage when a feature changes acceptance semantics.
- Add release/audit coverage for new public behavior.
