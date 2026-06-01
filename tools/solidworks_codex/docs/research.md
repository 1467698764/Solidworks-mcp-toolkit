# SolidWorks automation research notes

Date: 2026-05-31
Workspace: `C:\Users\Alphahui\Documents\Solidworks`

## Goal

Maximize Codex ability to help with SolidWorks-only general mechanical CAD part/assembly modification.

## Findings

### 1. Official SolidWorks API / COM is the reliable foundation

SolidWorks exposes a COM automation API usable from VBA, C#, VB.NET, C++/CLI and Python via `pywin32`. For complex modeling/editing, the most reliable pattern is:

1. inspect current document through COM;
2. generate focused macro/API script;
3. execute one change;
4. rebuild;
5. export JSON/log/screenshot/neutral file as evidence.

This is better than GUI automation because it is replayable and debuggable.

### 2. Existing MCP: `solidworks-mcp-server` / SolidworksMCP-TS

Installed locally through npm under:

- `tools/mcp-solidworks-ts`
- npm package cache copy: `tools/_packages/package`

Observed version: `solidworks-mcp-server@3.1.3`.

Verified in mock mode: lists 86 MCP tools, including open/close/rebuild/export, sketch tools, dimensions, analysis, interference, screenshots, VBA generation, assembly VBA helpers.

Caveat from README: Alpha / Experimental; many tools untested against real SolidWorks. Use it as a reference and opportunistic tool layer, not the only production path.

### 3. Existing MCP/reference: `eyfel/mcp-server-solidworks` / SolidPilot

Cloned to:

- `tools/_external/mcp-server-solidworks`

It appears to be a design/reference repo for a richer architecture: Claude UI + prompt/context + C# adapter + PythonNET/COM bridge. Useful for architecture ideas, less immediately runnable than direct COM scripts.

### 4. Self-built local MCP wrapper

Created under:

- `tools/solidworks_codex/mcp/server.cjs`

It wraps the verified `swctl.ps1` layer and exposes a deliberately small MCP tool surface:

- `solidworks_probe`
- `solidworks_start_probe`
- `solidworks_inspect`
- `solidworks_start_inspect`
- `solidworks_backup`
- `solidworks_set_dimension`
- `solidworks_existing_mcp_tools`

Offline smoke test succeeded via `tools/solidworks_codex/mcp/smoke-test.cjs`: initialize, list tools, backup sample `.SLDPRT`, and call existing MCP tool enumeration.

### 5. Other candidate repos

`SolidworksMCP-python` clone stalled in this environment. `SolidworksMCP-TS` is cloned under `tools/_external/SolidworksMCP-TS`. The npm package remains the runnable installed copy used for smoke tests.

### 6. Local machine state

- `SldWorks.Application` ProgID exists: COM registration is present.
- `python`, `py`, `node`, `npm`, `git`, `codex` are installed.
- SolidWorks was not running during probe. Read-only attach failed as expected.

## Recommended stack

1. Keep `tools/solidworks_codex` as the stable local control layer.
2. Use the self-built `tools/solidworks_codex/mcp/server.cjs` as the MCP bridge after user approves Codex config registration.
3. Keep `tools/mcp-solidworks-ts` installed for MCP tool schemas and alpha tool experiments.
4. Keep `tools/_external/mcp-server-solidworks` as reference only.
5. Keep Codex skill `solidworks-codex` so future tasks trigger the right workflow.
6. Next verification requires opening SolidWorks or allowing COM launch, then running `swctl.ps1 start-inspect`.

## Decision for general mechanical CAD work

Do not require perfect feature naming. For existing mechanical assemblies, use:

- component file paths,
- active document/component tree,
- mate errors,
- cylinder axes and circular faces,
- reference planes/origins,
- bounding boxes/interference checks,
- user screenshots/selected entities when needed.
