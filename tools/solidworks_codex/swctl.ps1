param(
    [Parameter(Position=0)]
    [ValidateSet('probe','inspect','backup','backup-status','restore-backup','set-dimension','safe-set-dimension','mcp-tools','start-probe','start-inspect','summary','compare','change-verify','rebuild','start-rebuild','export','mass','start-mass','audit','component-state','start-component-state','interference','start-interference','template-macro','issue-report','mate-macro','selection-report','start-selection-report','session-snapshot','start-session-snapshot','preflight','design-review','change-plan','report-search','report-context','model-understand','worklog','handoff-bundle','tool-catalog','offline-demo','public-copy-guard','github-readiness','repo-health','release-tree','capability-matrix','finalize')]
    [string]$Command = 'probe',

    [string]$Out = '', [string]$Model = '', [string]$Dimension = '', [double]$ValueM = [double]::NaN,
    [switch]$Save, [switch]$Apply, [string[]]$Files = @(), [string]$Report = '', [string]$Before = '', [string]$After = '',
    [string]$JsonOut = '', [string]$Target = '', [string]$Component = '', [string]$Action = '', [string]$View = 'auto',
    [string]$Template = '', [double]$OuterDiameterMm = [double]::NaN, [double]$InnerDiameterMm = [double]::NaN,
    [double]$LengthMm = [double]::NaN, [double]$ThicknessMm = [double]::NaN, [double]$CenterBoreMm = [double]::NaN,
    [int]$HoleCount = -1, [double]$HolePcdMm = [double]::NaN, [double]$HoleDiameterMm = [double]::NaN,
    [double]$PlateWidthMm = [double]::NaN, [double]$PlateHeightMm = [double]::NaN,
    [double]$MotorHoleXMm = [double]::NaN, [double]$MotorHoleYMm = [double]::NaN,
    [double]$BearingOuterDiameterMm = [double]::NaN, [double]$RecessDepthMm = [double]::NaN,
    [string]$Manifest = '', [string]$Mate = '', [double]$DistanceMm = 0, [double]$AngleDeg = 0, [switch]$Flip,
    [string]$SessionName = 'session', [string]$FromReport = '', [string]$OutDir = '',
    [string]$Message = '', [string]$Next = '', [string[]]$Artifact = @(),
    [string[]]$AllowDimension = @(), [string[]]$AllowComponent = @(), [string[]]$AllowComponentAdded = @(), [string[]]$AllowComponentRemoved = @(), [string[]]$AllowFeatureType = @(),
    [switch]$RequireAllowedChange
)

$Root = Split-Path -Parent $PSCommandPath
$Workspace = Split-Path -Parent (Split-Path -Parent $Root)
function DefaultOut([string]$Name) { return "tools/solidworks_codex/reports/$Name" }
function Expand-List([string[]]$Items) {
    $result = @()
    foreach ($item in $Items) {
        if ($null -eq $item) { continue }
        foreach ($part in ([string]$item -split ',')) {
            $trimmed = $part.Trim()
            if ($trimmed) { $result += $trimmed }
        }
    }
    return $result
}
function Invoke-SwPython([object[]]$Arguments) {
    $candidates = @()
    if ($env:SWCODEX_PYTHON) { $candidates += ,@($env:SWCODEX_PYTHON) }
    $codexPython = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
    if (Test-Path $codexPython) { $candidates += ,@($codexPython) }
    $candidates += @(@('py','-3.12'), @('py','-3'), @('python'), @('python3'))

    $scriptPath = if ($Arguments.Count -gt 0) { [string]$Arguments[0] } else { '' }
    $requiresPywin32 = $false
    if ($scriptPath -and (Test-Path $scriptPath)) {
        $head = Get-Content -LiteralPath $scriptPath -TotalCount 80 -ErrorAction SilentlyContinue
        $requiresPywin32 = ($head -match 'import pythoncom|win32com').Count -gt 0
    }

    foreach ($candidate in $candidates) {
        $exe = [string]$candidate[0]
        $prefix = @()
        if ($candidate.Count -gt 1) { $prefix = $candidate[1..($candidate.Count - 1)] }
        & $exe @prefix -c "import sys; print(sys.executable)" *> $null
        if ($LASTEXITCODE -ne 0) { continue }
        if ($requiresPywin32) {
            & $exe @prefix -c "import pythoncom, win32com.client" *> $null
            if ($LASTEXITCODE -ne 0) { continue }
        }
        & $exe @prefix @Arguments | ForEach-Object { Write-Host $_ }
        $code = $LASTEXITCODE
        if ($null -eq $code) { return 0 }
        return [int]$code
    }
    if ($requiresPywin32) {
        Write-Error "No usable Python with pywin32 found. Install pywin32 or set SWCODEX_PYTHON to a python.exe path that can import pythoncom and win32com.client."
    } else {
        Write-Error "No usable Python found. Install Python 3 or set SWCODEX_PYTHON to a python.exe path."
    }
    return 127
}

switch ($Command) {
    'probe' { $outPath = if ($Out) { $Out } else { DefaultOut 'com_probe.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_com_probe.py'), '--out', $outPath)) }
    'start-probe' { $outPath = if ($Out) { $Out } else { DefaultOut 'com_probe_start.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_com_probe.py'), '--start', '--out', $outPath)) }
    'inspect' { $outPath = if ($Out) { $Out } else { DefaultOut 'assembly_inspect.json' }; $argsList = @((Join-Path $Root 'scripts/sw_assembly_inspect.py'), '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; exit (Invoke-SwPython $argsList) }
    'start-inspect' { $outPath = if ($Out) { $Out } else { DefaultOut 'assembly_inspect_start.json' }; $argsList = @((Join-Path $Root 'scripts/sw_assembly_inspect.py'), '--start', '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; exit (Invoke-SwPython $argsList) }
    'session-snapshot' { $argsList = @((Join-Path $Root 'scripts/sw_session_snapshot.py'), '--name', $SessionName, '--out-dir', $OutDir); if ($FromReport) { $argsList += @('--from-report', $FromReport) }; exit (Invoke-SwPython $argsList) }
    'start-session-snapshot' { $argsList = @((Join-Path $Root 'scripts/sw_session_snapshot.py'), '--start', '--name', $SessionName, '--out-dir', $OutDir); if ($FromReport) { $argsList += @('--from-report', $FromReport) }; exit (Invoke-SwPython $argsList) }
    'selection-report' { $outPath = if ($Out) { $Out } else { DefaultOut 'selection_report.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_selection_report.py'), '--out', $outPath)) }
    'start-selection-report' { $outPath = if ($Out) { $Out } else { DefaultOut 'selection_report_start.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_selection_report.py'), '--start', '--out', $outPath)) }
    'summary' { if (-not $Report) { throw 'summary requires -Report <json report path>' }; $argsList = @((Join-Path $Root 'scripts/sw_report_summary.py'), $Report); if ($Out) { $argsList += @('--out', $Out) }; exit (Invoke-SwPython $argsList) }
    'issue-report' { if (-not $Report) { throw 'issue-report requires -Report <inspect json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'issue_report.md' }; $argsList = @((Join-Path $Root 'scripts/sw_issue_report.py'), '--report', $Report, '--out', $outPath); if ($JsonOut) { $argsList += @('--json-out', $JsonOut) }; exit (Invoke-SwPython $argsList) }
    'compare' { if (-not $Before -or -not $After) { throw 'compare requires -Before and -After' }; $outPath = if ($Out) { $Out } else { DefaultOut 'report_delta.md' }; $argsList = @((Join-Path $Root 'scripts/sw_compare_reports.py'), '--before', $Before, '--after', $After, '--out', $outPath); if ($JsonOut) { $argsList += @('--json-out', $JsonOut) }; exit (Invoke-SwPython $argsList) }
    'change-verify' { if (-not $Report) { throw 'change-verify requires -Report <compare delta json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'change_verify.json' }; $argsList = @((Join-Path $Root 'scripts/sw_change_verify.py'), '--delta', $Report, '--out', $outPath); foreach ($x in (Expand-List $AllowDimension)) { $argsList += @('--allow-dimension', $x) }; foreach ($x in (Expand-List $AllowComponent)) { $argsList += @('--allow-component', $x) }; foreach ($x in (Expand-List $AllowComponentAdded)) { $argsList += @('--allow-component-added', $x) }; foreach ($x in (Expand-List $AllowComponentRemoved)) { $argsList += @('--allow-component-removed', $x) }; foreach ($x in (Expand-List $AllowFeatureType)) { $argsList += @('--allow-feature-type', $x) }; if ($RequireAllowedChange) { $argsList += '--require-allowed-change' }; exit (Invoke-SwPython $argsList) }
    'backup' { if (-not $Files -or $Files.Count -eq 0) { throw 'backup requires -Files <file1,file2,...>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'backup.json' }; $argsList = @((Join-Path $Root 'scripts/sw_backup.py')) + $Files + @('--out', $outPath); exit (Invoke-SwPython $argsList) }
    'backup-status' { if (-not $Report) { throw 'backup-status requires -Report <backup json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'backup_status.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_backup_status.py'), '--report', $Report, '--out', $outPath)) }
    'restore-backup' { if (-not $Report) { throw 'restore-backup requires -Report <backup json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'restore_backup.json' }; $argsList = @((Join-Path $Root 'scripts/sw_restore_backup.py'), '--report', $Report, '--out', $outPath); if ($Apply) { $argsList += '--apply' }; exit (Invoke-SwPython $argsList) }
    'set-dimension' { if (-not $Dimension) { throw 'set-dimension requires -Dimension <full dimension name>' }; if ([double]::IsNaN($ValueM)) { throw 'set-dimension requires -ValueM <meters>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'set_dimension.json' }; $argsList = @((Join-Path $Root 'scripts/sw_set_dimension.py'), '--dimension', $Dimension, '--value-m', $ValueM, '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; if ($Save) { $argsList += '--save' }; exit (Invoke-SwPython $argsList) }
    'safe-set-dimension' { if (-not $Model) { throw 'safe-set-dimension requires -Model <SolidWorks file>' }; if (-not $Dimension) { throw 'safe-set-dimension requires -Dimension <full dimension name>' }; if ([double]::IsNaN($ValueM)) { throw 'safe-set-dimension requires -ValueM <meters>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'safe_set_dimension.json' }; $artifactsDir = if ($OutDir) { $OutDir } else { 'tools/solidworks_codex/reports/safe_set_dimension' }; $argsList = @((Join-Path $Root 'scripts/sw_safe_set_dimension.py'), '--model', $Model, '--dimension', $Dimension, '--value-m', $ValueM, '--out-dir', $artifactsDir, '--out', $outPath); if ($Save) { $argsList += '--save' }; exit (Invoke-SwPython $argsList) }
    'rebuild' { $outPath = if ($Out) { $Out } else { DefaultOut 'rebuild.json' }; $argsList = @((Join-Path $Root 'scripts/sw_rebuild.py'), '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; if ($Save) { $argsList += '--save' }; exit (Invoke-SwPython $argsList) }
    'start-rebuild' { $outPath = if ($Out) { $Out } else { DefaultOut 'rebuild_start.json' }; $argsList = @((Join-Path $Root 'scripts/sw_rebuild.py'), '--start', '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; if ($Save) { $argsList += '--save' }; exit (Invoke-SwPython $argsList) }
    'export' { if (-not $Target) { throw 'export requires -Target <path>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'export.json' }; $argsList = @((Join-Path $Root 'scripts/sw_export.py'), '--target', $Target, '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; exit (Invoke-SwPython $argsList) }
    'mass' { $outPath = if ($Out) { $Out } else { DefaultOut 'mass_properties.json' }; $argsList = @((Join-Path $Root 'scripts/sw_mass_properties.py'), '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; exit (Invoke-SwPython $argsList) }
    'start-mass' { $outPath = if ($Out) { $Out } else { DefaultOut 'mass_properties_start.json' }; $argsList = @((Join-Path $Root 'scripts/sw_mass_properties.py'), '--start', '--out', $outPath); if ($Model) { $argsList += @('--model', $Model) }; exit (Invoke-SwPython $argsList) }
    'component-state' { if (-not $Component -or -not $Action) { throw 'component-state requires -Component and -Action' }; $outPath = if ($Out) { $Out } else { DefaultOut 'component_state.json' }; $argsList = @((Join-Path $Root 'scripts/sw_component_state.py'), '--component', $Component, '--action', $Action, '--out', $outPath); if ($Save) { $argsList += '--save' }; exit (Invoke-SwPython $argsList) }
    'start-component-state' { if (-not $Component -or -not $Action) { throw 'start-component-state requires -Component and -Action' }; $outPath = if ($Out) { $Out } else { DefaultOut 'component_state_start.json' }; $argsList = @((Join-Path $Root 'scripts/sw_component_state.py'), '--start', '--component', $Component, '--action', $Action, '--out', $outPath); if ($Save) { $argsList += '--save' }; exit (Invoke-SwPython $argsList) }
    'interference' { $outPath = if ($Out) { $Out } else { DefaultOut 'interference.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_interference.py'), '--out', $outPath)) }
    'start-interference' { $outPath = if ($Out) { $Out } else { DefaultOut 'interference_start.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_interference.py'), '--start', '--out', $outPath)) }
    'template-macro' { if (-not $Template) { throw 'template-macro requires -Template sleeve|spacer|flange|endcap|motor_adapter|bearing_retainer' }; $outPath = if ($Out) { $Out } else { "tools/solidworks_codex/macros/$Template.swp.vba" }; $manifestPath = if ($Manifest) { $Manifest } else { DefaultOut "${Template}_manifest.json" }; $argsList = @((Join-Path $Root 'scripts/sw_template_macro.py'), '--template', $Template, '--out', $outPath, '--manifest', $manifestPath); if (-not [double]::IsNaN($OuterDiameterMm)) { $argsList += @('--outer-diameter-mm', $OuterDiameterMm) }; if (-not [double]::IsNaN($InnerDiameterMm)) { $argsList += @('--inner-diameter-mm', $InnerDiameterMm) }; if (-not [double]::IsNaN($LengthMm)) { $argsList += @('--length-mm', $LengthMm) }; if (-not [double]::IsNaN($ThicknessMm)) { $argsList += @('--thickness-mm', $ThicknessMm) }; if (-not [double]::IsNaN($CenterBoreMm)) { $argsList += @('--center-bore-mm', $CenterBoreMm) }; if ($HoleCount -ge 0) { $argsList += @('--hole-count', $HoleCount) }; if (-not [double]::IsNaN($HolePcdMm)) { $argsList += @('--hole-pcd-mm', $HolePcdMm) }; if (-not [double]::IsNaN($HoleDiameterMm)) { $argsList += @('--hole-diameter-mm', $HoleDiameterMm) }; if (-not [double]::IsNaN($PlateWidthMm)) { $argsList += @('--plate-width-mm', $PlateWidthMm) }; if (-not [double]::IsNaN($PlateHeightMm)) { $argsList += @('--plate-height-mm', $PlateHeightMm) }; if (-not [double]::IsNaN($MotorHoleXMm)) { $argsList += @('--motor-hole-x-mm', $MotorHoleXMm) }; if (-not [double]::IsNaN($MotorHoleYMm)) { $argsList += @('--motor-hole-y-mm', $MotorHoleYMm) }; if (-not [double]::IsNaN($BearingOuterDiameterMm)) { $argsList += @('--bearing-outer-diameter-mm', $BearingOuterDiameterMm) }; if (-not [double]::IsNaN($RecessDepthMm)) { $argsList += @('--recess-depth-mm', $RecessDepthMm) }; exit (Invoke-SwPython $argsList) }
    'mate-macro' { if (-not $Mate) { throw 'mate-macro requires -Mate coincident|concentric|distance|angle|parallel|perpendicular' }; $outPath = if ($Out) { $Out } else { "tools/solidworks_codex/macros/mate_${Mate}_preselect.swp.vba" }; $manifestPath = if ($Manifest) { $Manifest } else { DefaultOut "mate_${Mate}_manifest.json" }; $argsList = @((Join-Path $Root 'scripts/sw_mate_macro.py'), '--mate', $Mate, '--distance-mm', $DistanceMm, '--angle-deg', $AngleDeg, '--out', $outPath, '--manifest', $manifestPath); if ($Flip) { $argsList += '--flip' }; exit (Invoke-SwPython $argsList) }
    'preflight' { $outPath = if ($Out) { $Out } else { DefaultOut 'preflight.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_preflight.py'), '--out', $outPath)) }
    'design-review' { if (-not $Report) { throw 'design-review requires -Report <inspect json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'design_review.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { DefaultOut 'design_review.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_design_review.py'), '--report', $Report, '--intent', $Target, '--out', $outPath, '--json-out', $jsonTarget)) }
    'change-plan' { if (-not $Report) { throw 'change-plan requires -Report <inspect json>' }; if (-not $Target) { throw 'change-plan requires -Target <change goal text>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'change_plan.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { DefaultOut 'change_plan.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_change_plan.py'), '--report', $Report, '--goal', $Target, '--session-name', $SessionName, '--out', $outPath, '--json-out', $jsonTarget)) }
    'report-search' { if (-not $Report) { throw 'report-search requires -Report <inspect json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'report_search.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { DefaultOut 'report_search.json' }; $kind = if ($Action) { $Action } else { 'all' }; $state = if ($Component) { $Component } else { 'any' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_report_search.py'), '--report', $Report, '--query', $Target, '--kind', $kind, '--state', $state, '--out', $outPath, '--json-out', $jsonTarget)) }
    'report-context' { if (-not $Report) { throw 'report-context requires -Report <inspect json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'report_context.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { DefaultOut 'report_context.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_report_context.py'), '--report', $Report, '--focus', $Target, '--out', $outPath, '--json-out', $jsonTarget)) }
    'model-understand' { if (-not $Report) { throw 'model-understand requires -Report <inspect json>' }; $outPath = if ($Out) { $Out } else { DefaultOut 'model_understanding.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { DefaultOut 'model_understanding.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_model_understand.py'), '--report', $Report, '--task', $Target, '--view', $View, '--out', $outPath, '--json-out', $jsonTarget)) }
    'worklog' { if (-not $Message) { throw 'worklog requires -Message <text>' }; $logPath = if ($Out) { $Out } else { DefaultOut 'worklog.jsonl' }; $summaryPath = if ($JsonOut) { $JsonOut } else { DefaultOut 'worklog.md' }; $eventName = if ($Action) { $Action } else { 'note' }; $argsList = @((Join-Path $Root 'scripts/sw_worklog.py'), '--log', $logPath, '--summary-out', $summaryPath, '--session', $SessionName, '--event', $eventName, '--message', $Message); foreach ($a in $Artifact) { $argsList += @('--artifact', $a) }; if ($Next) { $argsList += @('--next', $Next) }; exit (Invoke-SwPython $argsList) }
    'handoff-bundle' { if (-not $Report) { throw 'handoff-bundle requires -Report <inspect json>' }; $bundleDir = if ($OutDir) { $OutDir } else { 'tools/solidworks_codex/reports/handoff' }; $worklogPath = if ($FromReport) { $FromReport } else { DefaultOut 'worklog.jsonl' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_handoff_bundle.py'), '--report', $Report, '--worklog', $worklogPath, '--focus', $Target, '--out-dir', $bundleDir)) }
    'tool-catalog' { $outPath = if ($Out) { $Out } else { DefaultOut 'tool_catalog.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { DefaultOut 'tool_catalog.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_tool_catalog.py'), '--out', $outPath, '--json-out', $jsonTarget)) }
    'offline-demo' { $demoDir = if ($OutDir) { $OutDir } else { 'docs/demo/offline' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_offline_demo.py'), '--out-dir', $demoDir)) }
    'public-copy-guard' { $outPath = if ($Out) { $Out } else { DefaultOut 'public_copy_guard.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_public_copy_guard.py'), '--out', $outPath)) }
    'github-readiness' { $outPath = if ($Out) { $Out } else { DefaultOut 'github_readiness.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_github_readiness.py'), '--out', $outPath)) }
    'repo-health' { $outPath = if ($Out) { $Out } else { DefaultOut 'repo_health.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_repo_health.py'), '--out', $outPath)) }
    'release-tree' { $outPath = if ($Out) { $Out } else { DefaultOut 'release_tree.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_release_tree.py'), '--out', $outPath)) }
    'capability-matrix' { $outPath = if ($Out) { $Out } else { 'docs/capability-matrix.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { 'docs/capability-matrix.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_capability_matrix.py'), '--out', $outPath, '--json-out', $jsonTarget)) }
    'finalize' { $outPath = if ($Out) { $Out } else { 'docs/solidworks-codex-final-readiness.md' }; $jsonTarget = if ($JsonOut) { $JsonOut } else { DefaultOut 'final_readiness.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_finalize.py'), '--run-audit', '--out', $outPath, '--json-out', $jsonTarget)) }
    'audit' { $outPath = if ($Out) { $Out } else { DefaultOut 'audit_latest.json' }; exit (Invoke-SwPython @((Join-Path $Root 'scripts/sw_audit.py'), '--out', $outPath)) }
    'mcp-tools' { node (Join-Path $Workspace 'tools/mcp-solidworks-ts/list-tools.cjs'); exit $LASTEXITCODE }
}








