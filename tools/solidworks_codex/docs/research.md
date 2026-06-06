# Research Notes

This project has absorbed ideas from existing SolidWorks MCP wrappers, but its direction is different: build an evidence-first CAD control layer rather than a thin API catalog.

## Useful Patterns

- Local MCP tools should route through commands that can also be run directly.
- Strong model reasoning improves when reports include compact evidence, search handles, risks, and open questions.
- Generated macros are useful at the COM boundary, but they need explicit selection evidence and post-run readback.
- Native file readback is more meaningful than export-only success.

## Current Differentiators

- 56 MCP tools with CLI-backed routing.
- Assembly diagnosis and interface indexing before mate execution.
- Execution tools for component insert, part features, metadata, dimensions, component state, and mate groups.
- Validation profiles instead of one global acceptance checklist.
- Handoff bundles and worklogs for multi-turn CAD work.

## Open Research Areas

- stronger persistent native entity identity across sessions
- visual validation integrated with textual inspect evidence
- broader mechanism-lite motion checks
- richer local repair execution for underconstrained assemblies
- deeper DFM/DFA and tolerance-aware validation
