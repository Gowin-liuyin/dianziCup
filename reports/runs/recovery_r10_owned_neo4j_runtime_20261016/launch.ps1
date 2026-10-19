$ErrorActionPreference = 'Stop'
$argumentLine = '-d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_20261016/runtime.py supervise'
$startedAt = [DateTimeOffset]::Now
$launcher = Start-Process -FilePath wsl.exe -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput 'D:/dianzi-runtime-cache/r10-neo4j-operations-20261016/supervisor.stdout.log' -RedirectStandardError 'D:/dianzi-runtime-cache/r10-neo4j-operations-20261016/supervisor.stderr.log'
$record = [ordered]@{
    started_at = $startedAt.ToString('o')
    launcher_pid = $launcher.Id
    executable = 'wsl.exe'
    arguments = $argumentLine
    window_style = 'Hidden'
    exit_code = $null
    exit_code_semantics = 'Background launcher is ongoing, not a completion exit.'
}
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'launch.json') -Encoding UTF8
$record | ConvertTo-Json -Compress
