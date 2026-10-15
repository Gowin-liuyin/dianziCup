param([Parameter(Mandatory=$true)][string]$Name, [Parameter(Mandatory=$true)][string]$Command, [string[]]$CommandArguments)
$ErrorActionPreference = 'Continue'
$taskRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$outputRoot = Join-Path $taskRoot 'reports/runs/recovery_r05_question_frontend_20261015'
$started = Get-Date -Format o
Set-Location (Join-Path $taskRoot 'frontend')
& $Command @CommandArguments > (Join-Path $outputRoot "$Name.log") 2>&1
$commandExitCode = $LASTEXITCODE
$ended = Get-Date -Format o
@{ name=$Name; command=$Command; arguments=$CommandArguments; cwd=(Get-Location).Path; started_at=$started; ended_at=$ended; exit_code=$commandExitCode; code_sha=(& git rev-parse HEAD); data_mode='isolated_fixture_or_static'; live_calls=0 } | ConvertTo-Json -Depth 5 | Set-Content -Encoding utf8 (Join-Path $outputRoot "$Name.command.json")
Get-Content (Join-Path $outputRoot "$Name.log")
exit $commandExitCode
