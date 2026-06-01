# Project Principles for Future AI Sessions

This document captures project-level preferences so a new AI session can continue without the user repeating them.

## Product direction

Build a general-purpose SolidWorks MCP/control layer for mechanical CAD work. Avoid making the project feel like a school project, thesis, or a single narrowly scoped demo. Public examples should use generic mechanical assemblies: plates, housings, locating interfaces, fasteners, shafts, bushings, covers, hole patterns, clearances, and manufacturing evidence.

## Reasoning stance

Do not over-constrain strong models with rigid output templates. Prefer evidence-rich context packs, graphs, search tools, and suggested next queries that leave room for flexible reasoning. The model should understand the existing CAD project before changing it.

Important evidence includes:

- active document, configuration, component state, paths, suppression/hidden/fixed/lightweight state;
- dimensions with full names and owning features;
- mate-like evidence and explicit component references;
- transforms, origins, local axes, axis parallel/orthogonal relationships;
- bounding boxes, centers, pairwise gaps/overlaps, containment, coaxial candidates;
- manufacturing hole groups, feature/dimension links, nearby fasteners/locators;
- evidence gaps: thread/fit, tolerance, manufacturing process, tool access, edge distance, live interference results.

## Safety stance

Prefer reversible, narrow, verifiable actions:

1. inspect/session snapshot;
2. model-understand/report-context/report-search;
3. backup;
4. one focused modification;
5. rebuild;
6. inspect after;
7. compare/change-verify;
8. worklog/handoff.

Do not promise unattended bulk CAD redesign. Do not imply automated checks replace engineering review, simulation, tolerance analysis, or manufacturing review.

## Public positioning rules

- Do not claim public placement against other projects in README/docs.
- Do not present the project as tied to a single domain-specific demo, graduation design, or personal thesis.
- Lead with practical capability, evidence-first workflow, guarded edits, and handoff.
- Keep examples mechanically generic and reusable.

## Implementation preferences

- Use TDD for behavior changes.
- Keep CLI/MCP behavior backed by tests and audit gates.
- Add new functionality as focused Python scripts or focused functions first, route through `swctl.ps1`, then expose via MCP only when covered.
- Keep generated reports/backups/exports/macros/caches/logs out of Git unless intentionally promoted as fixtures or docs demo assets.
- Do not edit `<codex-home>\config.toml` unless the user explicitly asks.

## Current strategic priority

Prioritize real CAD understanding over presentation polish:

- deeper mate/entity extraction;
- stronger transform/spatial reasoning;
- richer hole/manufacturing evidence;
- better readiness checks for dimensions, constraints, interference, and manufacturability;
- clean handoff artifacts for multi-turn AI work.
