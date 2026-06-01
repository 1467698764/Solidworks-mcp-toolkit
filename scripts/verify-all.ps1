param(
    [switch]$SkipMcpSmoke
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSCommandPath)
Set-Location $Root

$python = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

& $python -m unittest discover -s tests -p "test_*.py" -v
$files = Get-ChildItem tools\solidworks_codex\scripts\*.py | ForEach-Object { $_.FullName }
& $python -m py_compile @files
node --check tools\solidworks_codex\mcp\server.cjs
node --check tools\solidworks_codex\mcp\smoke-test.cjs
if (-not $SkipMcpSmoke) {
    node tools\solidworks_codex\mcp\smoke-test.cjs
}
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\solidworks_codex\swctl.ps1 github-readiness -Out tools\solidworks_codex\reports\github_readiness.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\solidworks_codex\swctl.ps1 public-copy-guard -Out tools\solidworks_codex\reports\public_copy_guard.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\solidworks_codex\swctl.ps1 release-tree -Out tools\solidworks_codex\reports\release_tree.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\solidworks_codex\swctl.ps1 audit -Out tools\solidworks_codex\reports\audit_latest.json
powershell.exe -NoProfile -ExecutionPolicy Bypass -File tools\solidworks_codex\swctl.ps1 finalize -Out docs\solidworks-codex-final-readiness.md -JsonOut tools\solidworks_codex\reports\final_readiness.json
$final = Get-Content -Raw tools\solidworks_codex\reports\final_readiness.json | ConvertFrom-Json
if (-not $final.audit_ok) { throw 'final readiness audit_ok was false' }

Write-Host "verify-all completed"


