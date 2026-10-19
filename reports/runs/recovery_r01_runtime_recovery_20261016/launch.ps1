param([ValidatePattern('^[a-z0-9_]+$')][string]$Attempt = 'retry_1')
$ErrorActionPreference = 'Stop'
$startedAt = [DateTimeOffset]::Now
$argumentLine = '-d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r01_runtime_recovery_20261016/supervise_recovered_daemon.py'
$launcher = Start-Process -FilePath wsl.exe -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot "supervisor_$Attempt.stdout.log") -RedirectStandardError (Join-Path $PSScriptRoot "supervisor_$Attempt.stderr.log")
$record = [ordered]@{
    started_at = $startedAt.ToString('o')
    launch_receipt_at = [DateTimeOffset]::Now.ToString('o')
    executable = 'wsl.exe'
    arguments = $argumentLine
    working_directory = (Get-Location).Path
    launcher_pid = $launcher.Id
    window_style = 'Hidden'
    planned_end_at = '2026-10-17T21:49:15+08:00'
    exit_code = $null
    exit_code_semantics = 'Launcher remains running; receipt is not a completion exit.'
    resourceBudget = @{ memory_bytes = 8589934592; swap_bytes = 2147483648; cpu_count = 2; pids = 2048; daemon_log_bytes = 10485760 }
}
$record | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $PSScriptRoot "launch_$Attempt.json") -Encoding UTF8
$record | ConvertTo-Json -Compress -Depth 5
