# SolidWorks Automation Preparation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prepare and verify a local Codex-to-SolidWorks automation stack for mechanical assembly part and assembly modifications.

**Architecture:** Use a conservative local `swctl` control layer as the reliable path, backed by SolidWorks COM via Python/PowerShell. Keep the installed TypeScript SolidWorks MCP server as an experimental MCP/schema/VBA-generation layer, and keep reference repos separate from verified tools.

**Tech Stack:** Windows PowerShell, Python `pywin32`, SolidWorks COM (`SldWorks.Application`), Node.js MCP server `solidworks-mcp-server`, Codex skill metadata.

---

### Task 1: Verify read-only COM attach with SolidWorks open

**Files:**
- Read: `<repo>\tools\solidworks_codex\scripts\sw_com_probe.py`
- Output: `<repo>\tools\solidworks_codex\reports\com_probe.json`

- [ ] **Step 1: Open SolidWorks manually or allow COM launch**

Open SolidWorks and, if possible, open the target mechanical assembly `.sldasm`.

- [ ] **Step 2: Run read-only probe**

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 probe
```

Expected: JSON with `"connected": true` and either an active document summary or `"No active SolidWorks document detected."`.

- [ ] **Step 3: If SolidWorks is not open, run launch probe**

```powershell
cd <repo>
.\tools\solidworks_codex\swctl.ps1 start-probe
```

Expected: JSON with `"started_by_probe": true` or `false` and no Python traceback.

### Task 2: Extend inspection for assembly editing

**Files:**
- Modify: `<repo>\tools\solidworks_codex\scripts\sw_com_probe.py`
- Create: `<repo>\tools\solidworks_codex\scripts\sw_assembly_inspect.py`

- [ ] **Step 1: Add deeper component/mate/dimension extraction**

Implement read-only extraction for active assembly: full component list, suppression state, transform sample, mate feature names/types, rebuild errors if accessible.

- [ ] **Step 2: Verify on target assembly**

```powershell
py -3.12 tools\solidworks_codex\scripts\sw_assembly_inspect.py --out tools\solidworks_codex\reports\assembly_inspect.json
```

Expected: JSON file includes component paths and enough anchors to plan edits.

### Task 3: Add safe modification primitives

**Files:**
- Create: `<repo>\tools\solidworks_codex\scripts\sw_backup.py`
- Create: `<repo>\tools\solidworks_codex\scripts\sw_set_dimension.py`
- Modify: `<repo>\tools\solidworks_codex\swctl.ps1`

- [ ] **Step 1: Implement backup command**

Create timestamped copy before editing `.sldprt`, `.sldasm`, or `.slddrw`.

- [ ] **Step 2: Implement dimension change by full dimension name**

Use `Parameter(name).SystemValue = meters_value`, then rebuild and write JSON result.

- [ ] **Step 3: Verify on a disposable sample part only**

Do not use the real production assembly for first write test.

### Task 4: Decide MCP integration level after live SolidWorks test

**Files:**
- Read: `<repo>\tools\mcp-solidworks-ts\package.json`
- Read: `<repo>\tools\_packages\package\README.md`
- Potentially modify: `<codex-home>\config.toml` only if user explicitly approves.

- [ ] **Step 1: Keep MCP server unregistered until live smoke test passes**

Do not edit global Codex config without explicit user approval.

- [ ] **Step 2: Run MCP mock list as regression**

```powershell
.\tools\solidworks_codex\swctl.ps1 mcp-tools
```

Expected: 86 tools listed.

- [ ] **Step 3: If live MCP tools work, ask user before adding MCP to Codex config**

Config edits are explicitly user-controlled.

### Task 5: Use prepared stack for first real mechanical CAD change

**Files:**
- Input: target `.sldasm` path from user
- Output: JSON reports under `<repo>\tools\solidworks_codex\reports`
- Output: backups under a timestamped backup directory

- [ ] **Step 1: Capture baseline report**

Run probe/assembly inspect and save baseline JSON.

- [ ] **Step 2: Apply one requested change**

Use either direct COM script or generated macro. Change only one variable/feature/mate at a time.

- [ ] **Step 3: Rebuild and verify**

Capture JSON, screenshot/export/interference result as appropriate.

- [ ] **Step 4: Summarize exact files changed and verification evidence**

Report source file paths, backups, command outputs, and any SolidWorks errors.

