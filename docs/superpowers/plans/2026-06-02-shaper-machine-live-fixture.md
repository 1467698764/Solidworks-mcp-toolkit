# Shaper Machine Live Fixture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Historical note:** This plan is kept as a record of an earlier fixture effort. Its wording is no longer the project stance; the fixture is now treated as a simple mechanism regression case, not as a showcase or proof of general CAD capability.

**Goal:** Build a SolidWorks simple-mechanism regression fixture and use it to live-validate the SolidWorks Codex toolchain beyond the prior two-plate smoke fixture.

**Architecture:** Add a focused fixture generator script that separates deterministic mechanism specification from SolidWorks COM construction. Unit tests cover the pure mechanism spec and expected validation manifest; live SolidWorks runs create ignored fixture artifacts under `tools/solidworks_codex/live_fixture/shaper_machine/` and reports under `tools/solidworks_codex/reports/shaper_machine/`.

**Tech Stack:** Python 3, pywin32/SolidWorks COM for live model generation, existing `swctl.ps1` CLI, unittest, Node MCP smoke.

---

### Task 1: Add deterministic shaper fixture specification tests

**Files:**
- Create: `tests/solidworks_codex/test_shaper_fixture.py`
- Create/Modify later: `tools/solidworks_codex/scripts/sw_create_shaper_fixture.py`

- [ ] Write tests for `build_shaper_spec()` requiring at least 12 named parts, mechanism dimensions, adjustable dimensions, expected component states, and validation targets.
- [ ] Run `python -m unittest tests.solidworks_codex.test_shaper_fixture -v`; expected failure because module does not exist.

### Task 2: Implement fixture generator pure spec

**Files:**
- Create: `tools/solidworks_codex/scripts/sw_create_shaper_fixture.py`

- [ ] Implement dataclasses/functions for deterministic shaper mechanism spec without importing pywin32 at module import time.
- [ ] Include CLI arguments: `--out-dir`, `--reports-dir`, `--force`, `--manifest`.
- [ ] Run targeted tests until green.

### Task 3: Implement SolidWorks COM model construction

**Files:**
- Modify: `tools/solidworks_codex/scripts/sw_create_shaper_fixture.py`

- [ ] Add pywin32 lazy load and clear error messages when unavailable.
- [ ] Create individual `.SLDPRT` parts with named dimensions/features using simple extrudes/cylinders/blocks.
- [ ] Create `.SLDASM` with meaningful component names and transforms: base, column, ram, ram ways, tool head, crank disk, crank pin, slotted rocker, sliding block, rocker pivot bracket, connecting link, pins, spacers, guards, limit stops.
- [ ] Add enough mates/relationships where COM API is reliable; where motion mates are too API-fragile, encode mechanism evidence in custom properties/manifest and geometry placement.
- [ ] Save all files under ignored live fixture dir.

### Task 4: Run live validation on the shaper assembly

**Files:**
- Runtime ignored outputs only unless code bugs are found.

- [ ] Generate the fixture with SolidWorks COM.
- [ ] Run `probe`, `inspect -Model`, `summary`, `model-understand`, `report-context`, `report-search`, `design-review`, `change-plan`.
- [ ] Run `backup`, `backup-status`, `restore-backup` dry-run.
- [ ] Run `safe-set-dimension` on the crank eccentric radius or ram stroke dimension.
- [ ] Run `compare` and `change-verify -RequireAllowedChange`.
- [ ] Run `component-state hide/show/fix/float` on nontrivial components.
- [ ] Run `mass`, `interference`, `export`, `selection-report`, `session-snapshot`, `worklog`, `handoff-bundle`, `template-macro`, `mate-macro`, `offline-demo`, `tool-catalog`, MCP smoke, release gates.

### Task 5: Fix any discovered bugs with TDD

**Files:**
- Modify only affected scripts/tests/docs.

- [ ] For each discovered bug, write a failing unittest first.
- [ ] Implement the smallest fix.
- [ ] Run targeted tests and then full verification.

### Task 6: Documentation and commit

**Files:**
- Modify docs only if behavior/capability statements change.
- Commit tracked fixture generator/tests/plan and any fixes.

- [ ] Run final `python -m unittest discover -s tests -p "test_*.py" -v`.
- [ ] Run `node tools\solidworks_codex\mcp\smoke-test.cjs`.
- [ ] Run `.\scripts\verify-all.ps1` (actual command uses `.\scripts\verify-all.ps1`).
- [ ] Run `git diff --check`, inspect status, stage intended files only, and commit.
