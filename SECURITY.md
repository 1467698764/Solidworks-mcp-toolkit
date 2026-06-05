# Security

This project controls local SolidWorks through PowerShell, Python, COM automation, generated macros, and MCP calls. Treat every write path as capable of changing CAD files.

## Supported Usage

- Run in a local workspace you control.
- Review generated macros before manual execution.
- Use backup tools before modifying dimensions, features, mates, component state, metadata, or file outputs.
- Keep generated reports, backups, exports, and logs out of public releases unless intentionally sanitized.

## Write Safety

Read-only tools inspect and summarize the active model. Write tools should be paired with:

1. backup
2. execution
3. rebuild
4. inspect
5. compare / change-verify
6. task-specific validation such as `assembly-contract`, `interference`, or live validation

Generated macros are local artifacts and should not be treated as trusted input from strangers.

## Reporting Issues

For private security concerns, include:

- command or MCP tool used
- affected file paths
- whether generated macros were involved
- whether backups existed
- reproduction steps with sensitive CAD data removed

Do not publish proprietary CAD files, license keys, customer names, or private path contents in public issues.
