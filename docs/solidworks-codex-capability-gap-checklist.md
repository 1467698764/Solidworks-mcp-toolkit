# SolidWorks Codex General CAD Capability Checklist

This is the working standard for making the project a general SolidWorks CAD
assistant, not a single-fixture generator. Simple mechanical assemblies should be
routine by this standard: diagnose the current state, create or repair the needed
parts, add the right mate groups, verify, and hand off native files without
drama.

The document is deliberately broad and concrete. It defines the capability
surface, the expected artifacts, the acceptance profiles, and the implementation
order. It should be used before adding more fixture-specific code.

## 1. Product Boundary

The project is a SolidWorks MCP/tooling layer for strong reasoning models. Its
job is not to replace the model's judgment with a rigid workflow; its job is to
give the model reliable CAD actions, reliable readback, and selectable
validation.

The system should support any of these entry points:

| Entry point | User gives | System should do |
| --- | --- | --- |
| Concept to model | Natural-language design goal, rough dimensions, examples, constraints. | Produce design intent, choose validation profile, create parts/assembly, validate, report. |
| Part only | One part description or existing `.SLDPRT`. | Create, inspect, modify, or validate the part without requiring an assembly. |
| Assembly from parts | Existing parts or generated part specs. | Plan component structure, interfaces, standard parts, mate graph, and validation profile. |
| Existing assembly repair | `.SLDASM` path or current SolidWorks window. | Diagnose, produce local repair plan, modify affected subgraph, validate. |
| Feature edit | Existing part plus requested dimension/feature/sketch change. | Locate target, edit only target, rebuild, verify downstream impact. |
| Validation only | Native files and expected intent/profile. | Inspect and report pass/warning/blocking/not-applicable findings. |
| Handoff/resume | Prior report bundle. | Reconstruct context and continue from the last reliable artifact. |

The system should not require a full rebuild unless it records why local repair
is unsafe or more expensive than regeneration.

## 2. Maturity Levels

Use these levels to avoid confusing smoke tests with production usefulness.

| Level | Name | Meaning | Example benchmark |
| --- | --- | --- | --- |
| L0 | Tool smoke | API call works once on a toy file. | Two blocks, one distance mate, file opens. |
| L1 | Reliable primitive | Operation can be repeated, read back, and fails with useful evidence. | Extrude cut consumes the intended sketch after reopen. |
| L2 | Routine mechanical modeling | Common prismatic parts and small assemblies are created or repaired with semantic features and real mates. | L bracket, shaft support, simple gearbox housing, small static mechanism. |
| L3 | Mechanism-aware assembly | Intended degrees of freedom, limits, and path collisions are validated. | Slider-crank, quick-return mechanism, clamp with moving jaw. |
| L4 | Engineering handoff lite | Model carries materials, BOM, standard parts, fit intent, drawing/CAM-friendly origins, and DFM/DFA checks. | Small machine module ready for human engineering review. |

The retained mechanism fixture belongs at L2 for static assembly and at a light
L3 for its motion chain. It should not consume the project's conceptual center.

## 3. Core Design Invariant

Every meaningful CAD operation should be traceable through this chain:

`user intent -> design intent artifact -> target interface/feature -> SolidWorks operation -> native readback -> validation evidence -> resumable report`

If a step is missing, the tool may still be useful for exploration, but it should
not mark a result as complete.

## 4. Required Artifacts

These artifacts make the system resumable and debuggable. They can be JSON,
Markdown, or mixed report files, but their fields must be machine-readable where
later tools depend on them.

| Artifact | Produced when | Required contents |
| --- | --- | --- |
| `design_intent` | Before build/repair unless validation-only. | Goal, scope, validation profile, assumptions, parts, subassemblies, interfaces, motion pairs, standard parts, editable parameters, non-goals. |
| `part_feature_index` | After creating or opening a part. | Feature tree, named sketches, dimensions, bodies, bbox, mass, rebuild state, semantic feature roles. |
| `part_interface_index` | Before assembly planning or part handoff. | Named/scored faces, axes, holes, slots, planes, coordinate systems, local frames, confidence, source feature. |
| `assembly_inventory` | After opening or creating assembly. | Components, paths, configs, fixed/floating, suppressed/hidden, transforms, bbox, parent/subassembly grouping. |
| `assembly_mate_plan` | Before mutating mates. | Mate groups, mate types, participants, interface ids, intended DOF, optional/blocking flag, ordering constraints. |
| `assembly_diagnosis` | For any existing assembly or failed build. | Mate graph, isolated nodes, weakly connected nodes, no-mate components, bad/suppressed mates, interference, clearance, stale locks. |
| `repair_plan` | Before changing existing files. | Target subgraph, reused files, edited files, rollback copies, mate edits, feature edits, rebuild reason. |
| `validation_report` | After every accepted run. | Profile, blocking/warning/not-applicable findings, native file paths, inspect evidence, screenshots, cleanup status, next resume point. |
| `worklog` | During multi-step live work. | Stage, command, changed artifacts, failure evidence, memory/lock/process state, next action. |

## 5. Validation Profiles

Profiles are not moral judgments. They are cost controls. A strong reasoning
model may add checks, but it must record them as `extra_checks` and explain
whether they are blocking.

| Profile | Intended use | Blocking evidence |
| --- | --- | --- |
| `draft_part` | Quick approximate part or visual concept. | Native part opens; rebuild has no blocking error; bbox and primary features roughly match intent. |
| `single_part` | Usable non-complex mechanical part. | Named features, editable key dimensions, expected cuts/holes/slots, part geometry readback, mass/bbox, rebuild health. |
| `part_modify` | Change an existing feature/sketch/dimension. | Target located by name/role; only intended feature changes; rebuild succeeds; downstream geometry changes as expected. |
| `assembly_draft` | Rough placement or concept assembly. | Native assembly opens; main components present; no catastrophic overlap; screenshot attached. |
| `assembly_static` | Usable static mechanical assembly. | Mate graph covers functional components; no isolated functional components; no unexpected fixed motion parts; no nonzero interference; critical clearances pass; screenshot coherent. |
| `mechanism_lite` | Simple moving mechanism. | All `assembly_static` checks plus intended revolute/prismatic pairs, remaining DOF summary, limit positions, sampled collision checks. |
| `engineering_lite` | Engineering review candidate. | Materials, mass, center of gravity, BOM metadata, standard part attachment, fit intent, DFM/DFA-lite checks, drawing-friendly origins. |
| `handoff` | Final bundle for user or another agent. | Native files, reports, screenshots, worklog, assumptions, unresolved warnings, resume instructions. |

## 6. Capability Checklist

Status values:

- `present`: implemented and covered by tests or live evidence.
- `partial`: exists but cannot yet be trusted generally.
- `missing`: not implemented or not integrated.
- `defer`: useful, but not required for the current project phase.

### 6.1 Intent And Planning

| Capability | Status | Detail required | Acceptance |
| --- | --- | --- | --- |
| Parse user goal into CAD scope | present | `workflow-plan` supports `auto` intent classification and emits `intent_classification` with source, detected signals, CAD scope, resolved intent, selected profile, and non-goals for part, assembly, mechanism, validation-only, and modification-like requests. | Tool records profile and non-goals before live mutation. |
| Mechanical decomposition | present | `workflow-plan` emits `design_intent` with scope, validation profile, parts, subassemblies, standard parts, interfaces, motion pairs, editable parameters, non-goals, and an assumptions source. | Design intent can be inspected without reading generator code. |
| Assumption ledger | present | `workflow-plan` emits a machine-readable `assumption_ledger` covering dimensions, materials, simplified geometry, validation scope, write safety, assembly interfaces, and mechanism motion evidence where applicable. | Report distinguishes assumption, warning, and blocker; blockers name the stage they stop. |
| Validation profile selection | present | `workflow-plan` emits `validation_profile_selection` with selected profile, source profile, blocking/warning/not-applicable checks, stage profile mapping, runtime budget, and acceptance rule. | Small part tasks are not blocked by mechanism checks; mechanisms are not accepted by smoke checks. |
| Cost/runtime budget | present | `workflow-plan` emits `runtime_budget_plan` with expected SolidWorks sessions, rebuild scope, memory ceiling, timeout, cleanup policy, extra-check policy, and full-rebuild justification requirement. | Live plan says when a full rebuild is justified. |

### 6.2 Part Modeling

| Capability | Status | Detail required | Acceptance |
| --- | --- | --- | --- |
| Extrude boss/base | present | Sketch isolation, named feature, bbox readback. | Reopened part shows feature and expected volume/bbox. |
| Extrude cut | present but must remain guarded | Correct sketch selected, no stale selection, target body identified. | Cut consumes intended sketch; no wrong block/face cut. |
| Revolve boss | present | Axis/reference validation, profile closure. | Feature exists after reopen and mass/bbox match. |
| Revolved cut | present | Axis, sketch, target body, cut direction. | Feature readback and geometry evidence match. |
| Hole wizard/basic holes | partial/guarded | `part-feature-execute` / `solidworks_part_feature_execute` creates reviewed basic hole cuts from a selected plane/face with diameter, depth, through-all, and center evidence. Countersink/counterbore/Hole Wizard metadata remain separate tracks. | Hole axes appear in interface index. |
| Slots and pockets | partial/guarded | `part-feature-execute` / `solidworks_part_feature_execute` creates reviewed straight slot cuts and rectangular pocket cuts from a selected plane/face with center, width/length/height, depth, and cut evidence. Rich slot-interface readback remains a validation-layer track. | Slot role and dimensions read back. |
| Fillet/chamfer | partial/guarded | `part-feature-execute` / `solidworks_part_feature_execute` accepts reviewed edge/face selectors plus radius/distance/angle parameters, selects native entities, calls SolidWorks FeatureManager, rebuilds, and reports selection/call evidence. Selector discovery and post-readback hardening remain separate capability tracks. | Feature is named and does not break rebuild. |
| Patterns/mirror | partial/guarded | `part-feature-execute` / `solidworks_part_feature_execute` accepts reviewed seed feature plus direction/axis/plane selectors for linear pattern, circular pattern, and mirror, then calls SolidWorks FeatureManager, rebuilds, and reports execution evidence. Instance-level readback remains a validation-layer track. | Pattern instances read back or represented in feature index. |
| Sketch/dimension edit | present but shallow | Locate by feature/dimension name, edit, rebuild, verify downstream. | Only intended dimension changes. |
| Feature suppression/edit | partial/guarded | `feature-state` / `solidworks_feature_state` executes suppress, unsuppress, delete, and feature-scoped dimension writes by exact or unique feature-name match with live rebuild and before/after state/dimension evidence. Reorder and richer definition-object edits remain separate capability tracks. | Rebuild health, feature count, feature state, and edited parameter values are read back. |
| Part import/read-only inspect | partial | Existing `.SLDPRT` inventory without rewriting. | Feature/interface report works on user-provided part. |

### 6.3 Geometry Interfaces

| Capability | Status | Detail required | Acceptance |
| --- | --- | --- | --- |
| Named planar interfaces | present | `interface-index` emits bbox-derived planar interface candidates for datum, mounting, and contact faces, including stable interface ids, normals, local frames, confidence, and source evidence; live face identity remains a later refinement. | Interface id maps to face evidence and local frame. |
| Named cylindrical interfaces | present | `interface-index` emits feature/dimension-derived `cylindrical_interfaces` for shaft axes, hole axes, pin bores, and bearing bores with radius, role, location, direction, source feature, confidence policy, and selector fallback. | Axis candidates scored by radius, role, location, direction, source feature. |
| Slot/path interfaces | present | `interface-index` emits feature/dimension/bbox-derived `slot_path_interfaces` with stable ids, path axis/vector, centerline endpoints, width, length, role, confidence policy, source feature, and selector fallback. | Path can drive slot/path/cam mate or validation. |
| Coordinate systems/datums | present | `interface-index` emits per-component `coordinate_systems` from bbox evidence with stable ids, origin role, axes, size, confidence, and source; live/native coordinate systems remain a refinement layer. | Downstream drawing/CAM/assembly checks know orientation. |
| Interface confidence scoring | present | `interface-index` assigns confidence levels and selection policies to bbox-derived planar interfaces and coordinate systems; weak bbox-only candidates block automatic selection until live/native evidence is supplied. | Low confidence blocks or asks for alternative, not silent mate creation. |
| Interface persistence | present/guarded | `interface-index` emits per-interface and coordinate-system selectors with stable ids, component path, native identity envelopes, resolution order, tracking/persist/select-name placeholders, geometry signatures, fallback data, strategy, and review tags. `selection-report` captures persist/tracking/select-name evidence from live preselection; `mate-selection-check` exports selector patches; `mate-group-execute` tries native identity before geometry fallback. | Reopen/repair can find the same interface, and reviewed native ids win over bbox proximity. |

### 6.4 Assembly Planning And Mates

| Capability | Status | Detail required | Acceptance |
| --- | --- | --- | --- |
| Component inventory | present | `assembly-diagnose` emits comparable per-component inventory rows with path, configuration, fixed/suppressed/hidden state, bbox, size, transform origin, local axes, and transform availability, alongside aggregate fixed/floating/hidden/suppressed lists. | Existing and generated assemblies produce comparable inventory. |
| Mate graph extraction | present | `assembly-diagnose` emits mate details with type, participants, suppressed/status/error/bad flags, graph edges, type distribution, no-mate components, connected components, isolated components, and weak components. | Report identifies isolated and weakly connected components. |
| Coincident mate | present/guarded | Face contact selectors propagate from interface index to mate group macro manifest and `mate-group-execute` can select reviewed planar face evidence before `AddMate5`. | Readback type and participants match interface ids. |
| Concentric mate | present/guarded | Hole/shaft axis selectors propagate from interface index to mate group macro manifest and validation requires axial locator evidence unless axial freedom is explicit mechanism intent. | Revolute joint is not accepted with concentric alone unless axial freedom is intended. |
| Parallel/perpendicular | present/guarded | `mate-group-execute` / `solidworks_mate_group_execute` executes reviewed parallel and perpendicular selectors through `AddMate5`, rebuilds immediately, and reports them as supporting orientation constraints rather than primary attachment evidence. | They do not stand alone for physical attachment, and execution evidence records `constraint_role=supporting_orientation`. |
| Distance/angle | partial/guarded | Clearance, offset, or design angle; mate group manifests carry distance/angle/flip parameters into `mate-group-execute`, which passes them to the correct `AddMate5` distance and angle parameter slots after reviewed entity selection. | Dimension value and intent are read back. |
| Tangent | partial/guarded | `mate-macro`, `mate-group-macro`, and `mate-group-execute` support tangent mates through reviewed selectors and native planar/cylindrical face selection before `AddMate5`. | Only used with correct surface types and validation. |
| Width/symmetry | partial/guarded | `width` mate groups carry four reviewed planar face selectors and execute through `CreateMateData(11)` / `CreateMate`; `symmetry` mate groups carry three reviewed selectors, generate review macros, and execute through native selection plus `AddMate5`. | Remaining DOF matches intent. |
| Limit distance/angle | partial/guarded | `limit_distance` and `limit_angle` mate aliases preserve min/max distance or angle bounds through macro manifests and execute them through the corresponding `AddMate5` upper/lower parameter slots. | Mechanism samples endpoints and midpoints. |
| Slot/path/cam/gear mates | partial/guarded | `slot` mate groups carry two reviewed slot/pin selectors plus free/center/distance/percent constraint fields and execute through native selection plus `CreateMateData(21)` / `CreateMate`; `path` mate groups carry a reviewed moving vertex/point selector plus a reviewed path edge/curve selector and execute through native selection plus `AddMate5(15)`; `gear` mate groups carry two reviewed cylindrical/axis selectors plus positive numerator/denominator ratio; `cam` / `cam_follower` mate groups carry two reviewed face/edge selectors. Gear and cam execute through native selection plus `AddMate5`. | Optional until standard mechanism_lite is stable. |
| Mate groups | present/guarded | Read-only mate group plans, selector propagation, validation gates, DOF expectations, concentric axial-locator checks, reviewable preselect macro drafts, `mate-group-execute` SelectByID2/AddMate5 execution, expected mate names, face/edge/axis/plane/point selection-report prechecks, after-inspect execution checks, and per-group live work protocols exist. | Every functional connection has group id, DOF expectation, reviewed live steps, pre-macro selection evidence, execution report, and readback check. |
| Standard part attachment | partial/guarded | Hostless standard parts are detected and grouped into candidate concentric/coincident attachment plans; `component-insert` / `solidworks_component_insert` can place reviewed `.SLDPRT`/`.SLDASM` standard/detail components by origin/config/fixed-state spec, then mate-group execution attaches reviewed interfaces. Stronger hardware library selection and native entity ids remain separate tracks. | No accepted standard/detail component is isolated or hostless. |

### 6.5 Incremental Repair

| Capability | Status | Detail required | Acceptance |
| --- | --- | --- | --- |
| Open/current-document handoff | partial | Continue from active SolidWorks window or specified native file. | Diagnosis does not require regeneration. |
| Local fault localization | partial/offline-ready | Assembly diagnosis, repair plan, interface index, and mate group plan localize bad mates, hostless standard parts, and isolated components. | Repair plan names the affected subgraph. |
| Rollback copies | present | `assembly-diagnose` preserves component paths and `assembly-repair-plan` emits a `rollback_plan` with affected components/files, backup report path, backup/status/restore commands, missing path blockers, and mutation blocking until backup exists. | Report lists rollback paths. |
| Selective mate repair | partial/guarded | Reviewable mate group macro drafts, selector-bearing execution manifests, `mate-group-execute`, and live protocols can be generated per actionable group; bad-mate suppress/delete actions now propagate from repair plans into execution manifests and run before replacement mates. Stronger native entity ids still need live hardening. | Untouched components keep file timestamps/transforms unless affected, and each changed group has rebuild/inspect/execution-check evidence. |
| Selective part repair | partial/guarded | `feature-state` can edit an affected feature state or feature-scoped dimension while preserving before/after evidence; broader sketch/topology surgery remains a separate capability track. | Report lists changed feature, changed parameter, rebuild result, and downstream checks. |
| Full rebuild justification | present | `workflow-plan` emits `full_rebuild_justification_policy` with local-repair-first default, allowed reasons (`stale_base`, `invalid_topology`, `missing_interface`, `cheaper_regeneration`), required evidence fields, and a blocking rule when no reason is recorded. | Full rebuild is a deliberate decision, not default behavior. |

### 6.6 Validation And Understanding

| Capability | Status | Detail required | Acceptance |
| --- | --- | --- | --- |
| Rebuild health | present/guarded | `rebuild` / `solidworks_rebuild` now records `rebuild_health` with ForceRebuild3 success, document extension error/warning counts, feature-level nonzero error codes, blocking/warning/accepted findings, and nonzero process exit for blocking rebuild health. | Blocking findings include rebuild failure, error counts, and feature name/type/error-code evidence. |
| Part geometry validation | present/guarded | `part-geometry-validate` / `solidworks_part_geometry_validate` validates inspect readback against a geometry contract for body count, bbox size, volume, required feature names, semantic feature counts, and interface count. | Plain block stack cannot pass a feature-rich intent, and missing semantic/interface evidence exits nonzero. |
| Assembly mate validation | present/guarded | Mate group validation checks mate type, participants, state-bearing groups, verification gates, DOF expectation, concentric axial-locator evidence, and selector availability before macro/live execution. | Decorative mate count cannot pass; concentric-only attachment is blocked unless axial freedom is explicit mechanism intent. |
| Interference | present | Callback available and count/pairs reported. | Nonzero unexpected interference blocks static/mechanism profiles. |
| Clearance/near evidence | present | `assembly-diagnose` emits bbox pairwise near/contact pairs, largest separated pairs, missing-bbox components, and `clearance_summary` with minimum gap relation, near/separated counts, scattered components, tolerance, and evidence source. | Scattered components and floating details are detected. |
| Motion sweep lite | present/guarded | `motion-sweep-lite` / `solidworks_motion_sweep_lite` consumes a reviewed motion spec plus mate-group execution evidence, applies dimension-driven sample positions in the live assembly, rebuilds every sample, and records per-position interference evidence. Dry-run still checks revolute/prismatic pair coverage and declared collision samples. | Mechanism_lite can reject missing revolute/prismatic evidence, path collisions, failed driver writes, and dead rebuild layouts. |
| Visual screenshot review | present/guarded | `visual-validate` records screenshot evidence, accepts reviewed warning/not-applicable/accepted findings, and turns missing screenshots or reviewed visual contradictions into blocking findings. Live screenshot capture remains operator/browser-assisted evidence. | Screenshot contradicting report blocks acceptance. |
| BOM/metadata | present/guarded | `metadata-execute` / `solidworks_metadata_execute` writes reviewed material and custom-property specs to active or specified models with rebuild/save evidence; `engineering-lite` / `solidworks_engineering_lite` groups BOM rows by part path and configuration, rolls quantities, and blocks missing material evidence. Drawing BOM generation remains a separate export track. | Engineering_lite report can produce a useful BOM with material gaps surfaced before release. |
| DFM/DFA-lite | present/guarded | `engineering-lite` emits read-only DFM/DFA findings from inspect evidence: low hole-edge clearance, deep narrow pockets, hostless standard/detail components, and floating components without accepted mate evidence. Broader wall-thickness/tool-access geometry sampling remains a hardening track. | Optional warnings are available for draft profiles; engineering release can treat material and attachment gaps as blockers. |

### 6.7 Runtime And Cleanup

| Capability | Status | Detail required | Acceptance |
| --- | --- | --- | --- |
| Serial SolidWorks sessions | present/partial | Avoid parallel COM sessions and window storms. | Live gate records one controlled session unless intentionally inspecting. |
| Memory budget | partial | Check process memory before heavy stages and after cleanup. | Repeated low-memory crashes become blockers with evidence. |
| Lock-file scan | present/partial | Scan `~$*` generated locks before/after live work. | No accepted run leaves generated lock files after close/cleanup. |
| Generated artifact hygiene | partial | Separate source, generated native files, reports, screenshots, failed attempts. | Cleanup never touches user models or unrelated directories. |
| Window/screenshot discipline | partial | Capture target app/window only; avoid unnecessary windows. | Visual evidence is attached without leaving clutter. |

## 7. What The Retained Mechanism Fixture Should Test

The retained mechanism fixture should stay an L2/L3 regression case. It is useful
only if it proves generic capabilities.

| Shaper element | Generic capability tested | Required evidence |
| --- | --- | --- |
| Bed/column/base stack | Mounting faces, fixed reference policy, coincident/locator constraints. | Base/frame grounded intentionally; no motion part fixed to hide errors. |
| Ram and dovetail ways | Prismatic guide planning, width/parallel/contact/limit intent. | Ram connected to guide interfaces with expected sliding DOF. |
| Tool head and tool bit | Face mounting, slot/tool retention, local repair of attachments. | Tool head and bit are hosted, not floating display parts. |
| Work table and vise | Stacked static assembly, standard part attachment, clearances. | Table/slide/vise connected by mate groups and no interference. |
| Crank disk/shaft/pin | Revolute joint plus axial locator. | Concentric alone is insufficient unless axial freedom is intended and recorded. |
| Rocker/sliding die/link | Simple mechanism chain and sampled motion. | Revolute/prismatic pairs, expected DOF, sampled no-collision positions. |
| Bolts/washers/oil cups | Standard/detail attachment contracts. | Every accepted detail has a host interface or is omitted with reason. |

Good enough for this benchmark:

- It is instantly recognizable as the requested small mechanism in the SolidWorks window.
- It has native `.SLDASM/.SLDPRT` deliverables.
- Functional subassemblies are connected by mate groups, not just transforms.
- No functional component is isolated, unexpectedly fixed, or visually scattered.
- The quick-return chain has at least light mechanism evidence.
- The report can be used to resume or locally repair the model.

## 8. Implementation Roadmap

This order matters because later work depends on earlier evidence.

| Phase | Build | Why first | Exit criteria |
| --- | --- | --- | --- |
| 1 | Existing assembly diagnosis | Implemented offline. | Given an inspect report, report inventory, mate graph, isolated nodes, fixed/floating, bad mates, bbox gaps, standard-part host gaps, and locks. |
| 2 | Interface index extraction | Implemented offline heuristic. | Component bbox, nearest-neighbor, contact candidates, fixed-root hints, and standard-part hints are indexed; live face/axis identity is pending. |
| 3 | Repair planning | Implemented offline. | Diagnosis turns into ordered repair actions and read-only assembly review pipeline artifacts. |
| 4 | Mate group executor | Present/guarded. | Mate group plans, validation gates, reviewable macro drafts, live execution protocols, native identity envelopes, native face/axis/edge/point selection, AddMate5 group execution, bad-mate suppress/delete actions, and after-inspect execution checks exist; richer live capture of SolidWorks persist-reference bytes remains a hardening track. |
| 5 | Visual validation gate | Present/guarded. | SolidWorks window screenshots and reviewed visual findings feed `visual-validate`; missing screenshots or visual contradiction findings block assembly acceptance. |
| 6 | Mechanism_lite | Present/guarded. | `motion-sweep-lite` executes slider-crank/quick-return sample positions from reviewed driver dimensions, checks required revolute/prismatic mate evidence, rebuilds each sample, and blocks collision/dead layouts. |
| 7 | Engineering_lite | Present/guarded. | `engineering-lite` reports BOM quantity rollups, material blockers, hostless standard-part blockers, and DFM/DFA warnings from inspect evidence. |

## 9. Immediate Next Work

Before touching fixture geometry again, implement a small but real diagnosis
slice:

1. Input: current SolidWorks assembly or explicit `.SLDASM` path.
2. Output: `assembly_diagnosis.json`.
3. Include: component inventory, mate graph, isolated/no-mate components,
   fixed/floating state, suppressed/bad mates, mate type distribution, bbox
   near/gap evidence, interference callback if available, process/memory/lock
   status.
4. Test offline with synthetic inspect reports.
5. Test live on the current retained mechanism assembly.
6. Only then create a fixture `repair_plan`.

This keeps the next code change generic while still using an existing failing
fixture as the first real proving ground.

## 10. Stop Conditions

Stop and report a blocker instead of forcing success when:

- SolidWorks repeatedly crashes or crosses the configured memory budget at the
  same stage.
- A required face/axis/interface cannot be identified with enough confidence.
- The part geometry is semantically wrong enough that assembly repair would hide
  the real issue.
- A screenshot contradicts the structured report after one repair attempt.
- A local repair would overwrite native files without rollback copies.
- A validation profile is too heavy or too light for the user's stated task and
  no explicit override was recorded.

## 11. Documentation Rules

Future docs should not claim broad SolidWorks competence from a single fixture.
They should state:

- the validation profile used;
- the native file/report path;
- whether the evidence is offline, live, visual, or mechanism-level;
- what remains unproven;
- whether the result was created from scratch or repaired incrementally.

The desired end state is simple: when a user asks for a normal mechanical part or
assembly, the project should know where it is in the CAD lifecycle, do the local
work needed, validate at the right weight, and leave native SolidWorks artifacts
that a human can open without needing excuses.
