param([string]$Label,[string]$WorkingDirectory,[string]$Command)
$ErrorActionPreference='Continue'
$startedAt=[DateTimeOffset]::Now.ToString('yyyy-MM-ddTHH:mm:sszzz')
$logPath=Join-Path $PSScriptRoot ($Label+'.log')
Push-Location -LiteralPath $WorkingDirectory
try { & pwsh -NoProfile -Command $Command *> $logPath; $commandExitCode=$LASTEXITCODE } finally { Pop-Location }
$endedAt=[DateTimeOffset]::Now.ToString('yyyy-MM-ddTHH:mm:sszzz')
$entry=[ordered]@{label=$Label;cwd=$WorkingDirectory;command=$Command;started_at=$startedAt;ended_at=$endedAt;exit_code=$commandExitCode;log_path=$logPath}
$entry | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $PSScriptRoot 'commands.jsonl')
Get-Content -LiteralPath $logPath -Tail 28
exit $commandExitCode
