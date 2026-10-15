param(
    [Parameter(Mandatory = $true)][string]$Id,
    [Parameter(Mandatory = $true)][string]$Cwd,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string[]]$CommandArguments = @()
)

$ErrorActionPreference = 'Continue'
$PSNativeCommandUseErrorActionPreference = $false
$artifactRoot = Split-Path -Parent $PSCommandPath
$runStartedAt = [DateTimeOffset]::Now
$runWatch = [System.Diagnostics.Stopwatch]::StartNew()
$runLogPath = Join-Path $artifactRoot ($Id + '.log')
Push-Location -LiteralPath $Cwd
try {
    & $Executable @CommandArguments *> $runLogPath
    $commandExitCode = $LASTEXITCODE
    if ($null -eq $commandExitCode) { $commandExitCode = 0 }
} catch {
    $_ | Out-String | Add-Content -LiteralPath $runLogPath
    $commandExitCode = 1
} finally {
    Pop-Location
}
$runWatch.Stop()
$runRecord = [ordered]@{
    id = $Id
    candidate_sha = '4a17ca7b967a10d6077ba5219984a2d1a74cf320'
    baseline_sha = 'f0b154ee0e10100bc9a9d293ebeded13926d0a42'
    started_at = $runStartedAt.ToString('yyyy-MM-ddTHH:mm:sszzz')
    finished_at = [DateTimeOffset]::Now.ToString('yyyy-MM-ddTHH:mm:sszzz')
    wall_seconds = [Math]::Round($runWatch.Elapsed.TotalSeconds, 3)
    cwd = $Cwd
    argv = @($Executable) + $CommandArguments
    exit_code = $commandExitCode
    log = $runLogPath
}
$runRecord | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $artifactRoot ($Id + '.json')) -Encoding utf8
$runRecord | ConvertTo-Json -Depth 5
Get-Content -LiteralPath $runLogPath -Tail 12
exit $commandExitCode
