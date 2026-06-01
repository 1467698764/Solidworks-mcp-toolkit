param(
    [switch]$CheckOnly
)

$Root = Split-Path -Parent $PSCommandPath
$Workspace = Split-Path -Parent (Split-Path -Parent $Root)

function Test-Cmd($Name) {
    $cmd = Get-Command $Name -ErrorAction SilentlyContinue
    [pscustomobject]@{ name = $Name; available = [bool]$cmd; path = if($cmd){$cmd.Source}else{$null} }
}

$checks = @(
    Test-Cmd "node",
    Test-Cmd "git",
    Test-Cmd "powershell.exe"
)

$pythonCandidates = @()
if ($env:SWCODEX_PYTHON) { $pythonCandidates += $env:SWCODEX_PYTHON }
$codexPython = Join-Path $env:USERPROFILE ".cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"
if (Test-Path $codexPython) { $pythonCandidates += $codexPython }
$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) { $pythonCandidates += "py -3" }

$result = [ordered]@{
    workspace = $Workspace
    check_only = [bool]$CheckOnly
    commands = $checks
    python_candidates = $pythonCandidates
    mcp_server = Join-Path $Workspace "tools\solidworks_codex\mcp\server.cjs"
    usage = Join-Path $Workspace "docs\solidworks-codex-usage.md"
    next = @(
        ".\tools\solidworks_codex\swctl.ps1 preflight",
        ".\tools\solidworks_codex\swctl.ps1 audit",
        "node tools\solidworks_codex\mcp\smoke-test.cjs"
    )
}

$ok = ($checks | Where-Object { -not $_.available }).Count -eq 0 -and $pythonCandidates.Count -gt 0
$result["ok"] = $ok

if (-not $CheckOnly) {
    Write-Host "This installer is intentionally conservative."
    Write-Host "It does not modify Codex config automatically."
    Write-Host "Copy examples/codex-mcp-config.example.toml manually if desired."
}

$result | ConvertTo-Json -Depth 5
exit ($(if($ok){0}else{1}))
