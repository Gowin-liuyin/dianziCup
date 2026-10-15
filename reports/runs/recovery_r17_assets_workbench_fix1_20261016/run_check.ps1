param([Parameter(Mandatory=$true)][string]$Name, [Parameter(Mandatory=$true)][string[]]$Arguments)
$workspacePath = 'D:\wt\r17-assets-workbench'
$runPath = Join-Path $workspacePath 'reports\runs\recovery_r17_assets_workbench_fix1_20261016'
$startedAt = Get-Date -Format o
Push-Location (Join-Path $workspacePath 'frontend')
try {
    & npm.cmd @Arguments *> (Join-Path $runPath "$Name.log")
    $checkExit = $LASTEXITCODE
} finally { Pop-Location }
$receipt = [ordered]@{ command = @('npm.cmd') + $Arguments; cwd = (Join-Path $workspacePath 'frontend'); started_at = $startedAt; finished_at = (Get-Date -Format o); exit_code = $checkExit; fixture_phase = $env:DIANZI_ASSET_SCOPE_PHASE; log = "$Name.log" }
[IO.File]::WriteAllText((Join-Path $runPath "$Name.command.json"), ($receipt | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
Write-Output "$Name exit=$checkExit"
exit $checkExit
