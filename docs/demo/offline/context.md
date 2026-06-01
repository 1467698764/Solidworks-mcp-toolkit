# SolidWorks Codex Context Pack

- Focus: `current model evidence, constraints, clearance, and manufacturing gaps`
- Document: `sample_machine.SLDASM`
- Path: `C:/cad/projects/sample_machine/sample_machine.SLDASM`
- Type: `assembly`

## Handoff principle
Do not blindly replay templates or force a fixed output shape: use live evidence, targeted queries, reversible edits, and verification so the model can reason flexibly from the actual CAD state.

## Inventory
- Components: `3`
- Dimensions: `2`
- Features: `3`
- Suppressed components: `support_bushing-1`
- Hidden components: `<none>`
- Floating components: `drive_unit-1, reference_sensor-1`

## Risks / things to verify
- `floating_component` `drive_unit-1` — floating components may indicate unconstrained assembly intent.
- `suppressed_component` `support_bushing-1` — suppressed components can hide missing geometry, mates, or interference.
- `floating_component` `reference_sensor-1` — floating components may indicate unconstrained assembly intent.
- `mate_chain_present` `MateGroup` — mate state is often decisive for assembly intent, spatial freedom, and downstream edits.

## Evidence gaps
- `spatial_evidence` - No component bounding boxes are present; spatial adjacency, stack order, and clearance reasoning will be weak.
- `manufacturing_evidence` - No obvious hole/manufacturing features were reported; hole series, access, and process assumptions need targeted inspection.
- `constraint_evidence` - Floating components exist; confirm whether this is intended motion, incomplete mating, or stale assembly state.

## Useful anchors
- component `drive_unit-1` path=`C:/cad/projects/sample_machine/drive_unit.SLDPRT` suppressed=`False` hidden=`False` fixed=`False`
- component `support_bushing-1` path=`C:/cad/projects/sample_machine/support_bushing.SLDPRT` suppressed=`True` hidden=`False` fixed=`False`
- component `reference_sensor-1` path=`C:/cad/projects/sample_machine/reference_sensor.SLDPRT` suppressed=`False` hidden=`False` fixed=`False`
- dimension `D1@Sketch1@plate.SLDPRT` value_m=`0.012` feature=`Sketch1`
- dimension `D2@Sketch1@plate.SLDPRT` value_m=`0.02` feature=`Sketch1`
- feature `MateGroup` type=`MateGroup` suppressed=`None`
- feature `Cut-Extrude1` type=`Cut` suppressed=`None`
- feature `Fillet1` type=`Fillet` suppressed=`None`

## Flexible next queries
- `spatial_understanding`: `swctl.ps1 model-understand -Report <inspect.json> -View spatial-assembly -Target "<current concern>"` - Build a task-aware spatial evidence model before deciding what to edit.
- `object_search`: `swctl.ps1 report-search -Report <inspect.json> -Target "<component feature dimension concern>"` - Pull only the objects relevant to the current question instead of flooding the model with unrelated report data.
- `evidence_review`: `swctl.ps1 design-review -Report <inspect.json> -Target "<current mechanical concern>"` - Summarize verifiable risks, open questions, and candidate actions without forcing a fixed workflow.
- `change_planning`: `swctl.ps1 change-plan -Report <inspect.json> -Target "<specific modification goal>"` - Plan a reversible one-variable-at-a-time edit only after the evidence is sufficient.

## Suggested next commands
- `swctl.ps1 model-understand -Report <inspect.json> -View spatial-assembly -Target "<current concern>"`
- `swctl.ps1 report-search -Report <inspect.json> -Target "<component feature dimension concern>"`
- `swctl.ps1 design-review -Report <inspect.json> -Target "<current mechanical concern>"`
- `swctl.ps1 change-plan -Report <inspect.json> -Target "<specific modification goal>"`
- `swctl.ps1 backup -Files <assembly-and-parts-before-write>`
- `swctl.ps1 rebuild; swctl.ps1 interference; swctl.ps1 compare after each narrow change`
