# Security Policy

This project controls local SolidWorks through a conservative wrapper. Treat all CAD files as valuable source data.

## License boundary

This repository is not MIT-licensed. It uses a custom non-commercial license.
Commercial resale, paid hosting, commercial bundling, and paid CAD automation /
MCP / AI-agent services require separate written permission from the copyright
holder. See `LICENSE`.

## Safety model

- Read-only inspection is preferred before writes.
- Write operations should be preceded by `backup`.
- Real model changes should be narrow: one dimension/state/action at a time.
- Generated macros are review-first artifacts; do not run them blindly.
- `install.ps1` does not modify Codex config automatically.

## Reporting issues

For public GitHub use, report security or data-loss issues privately first if possible. Include:

- command used;
- file type involved;
- whether `-Save` was used;
- generated report/log paths;
- SolidWorks version if relevant.

## Out of scope

This project does not claim to replace engineering validation for strength, thermal, fatigue, tolerance stack-up, manufacturing, or safety-critical review.
