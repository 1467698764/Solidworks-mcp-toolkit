# Project Principles

## Evidence Before Action

The model should understand current SolidWorks state before changing it. Good context includes components, transforms, dimensions, features, semantic mate participation, interface candidates, clearance, mass/geometry evidence, risks, and unknowns.

## Execute The Real Layer

Do not stop at validators when the execution layer is missing. Implement the ability to select entities, create features, insert components, write metadata, add mates, rebuild, and read results back. Validation then proves the real path rather than replacing it.

## Generality Over Fixture Theater

The project is a general SolidWorks MCP. A named fixture can be a regression target, but acceptance must come from generic mechanisms: assembly diagnosis, interface indexing, local repair, mate groups, visual validation, native file readback, and semantic evidence.

`shaper_machine_v5` is a simple-mechanism regression. It is not a showcase and not proof that mechanism assembly is solved.

## Native CAD Evidence

Native `.SLDASM/.SLDPRT` files matter. STEP optional smoke is useful as a compatibility check, not as the primary deliverable. Reopened native readback is the stronger signal.

## Honest Validation

Validation profiles should match intent: `draft_part`, `single_part`, `assembly`, `mechanism_assembly`, and `engineering_release`. `runtime_budget` and `extra_checks` prevent both under-validation and wasteful full gates on drafts.

Findings should say `blocking`, `warning`, or `not_applicable` rather than pretending every task needs the same checks.

## Durable Handoff

Long CAD work spans sessions. Use `worklog`, `report-context`, `model-understand`, `tool-catalog`, and `handoff-bundle` so the next model can continue from decisions and evidence instead of rediscovering the world.
