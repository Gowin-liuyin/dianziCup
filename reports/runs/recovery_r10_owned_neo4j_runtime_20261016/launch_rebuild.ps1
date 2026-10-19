$ErrorActionPreference = 'Stop'
$argumentLine = '-d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_20261016/runtime.py supervise_rebuild'
$startedAt = [DateTimeOffset]::Now
$launcher = Start-Process -FilePath wsl.exe -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput 'D:/dianzi-runtime-cache/r10-neo4j-operations-20261016/supervisor_rebuild.stdout.log' -RedirectStandardError 'D:/dianzi-runtime-cache/r10-neo4j-operations-20261016/supervisor_rebuild.stderr.log'
$record = [ordered]@{
    started_at = $startedAt.ToString('o')
    launcher_pid = $launcher.Id
    executable = 'wsl.exe'
    arguments = $argumentLine
    window_style = 'Hidden'
    exit_code = $null
    exit_code_semantics = 'Background repair launcher is ongoing, not a completion exit.'
}
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'launch_rebuild.json') -Encoding UTF8
$record | ConvertTo-Json -Compress
