$ErrorActionPreference = 'Stop'
$argumentLine = '-d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_20261016/runtime.py resume_stopped'
$startedAt = [DateTimeOffset]::Now
$launcher = Start-Process -FilePath wsl.exe -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput 'D:/dianzi-runtime-cache/r10-neo4j-operations-20261016/supervisor_resume.stdout.log' -RedirectStandardError 'D:/dianzi-runtime-cache/r10-neo4j-operations-20261016/supervisor_resume.stderr.log'
$record = [ordered]@{
    started_at = $startedAt.ToString('o')
    launcher_pid = $launcher.Id
    executable = 'wsl.exe'
    arguments = $argumentLine
    window_style = 'Hidden'
    exit_code = $null
    exit_code_semantics = 'Background supervisor is ongoing; this is not a completion exit.'
}
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'launch_resume.json') -Encoding UTF8
$record | ConvertTo-Json -Compress
