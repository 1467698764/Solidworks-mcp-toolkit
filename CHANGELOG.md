# Changelog

All notable changes to this project are documented here.

## Unreleased

### Added

- Release gates for offline validation: `preflight`, `audit`, `finalize`, GitHub readiness, repository health, and public copy guard.
- offline demo bundle so evaluators can try report-context, worklog, handoff-bundle, and tool-catalog without a live SolidWorks model.
- 30-tool MCP wrapper around the PowerShell/Python control layer, with guarded writes and handoff-oriented analysis tools.

### Changed

- Public README and usage docs now describe the current 30-tool surface consistently.
- Final readiness JSON is compact and parseable by Windows PowerShell tooling.

### Safety

- Public copy guard blocks rank-boasting language in release-facing docs and source.
- Write workflows remain backup-first and verify-after-change.

