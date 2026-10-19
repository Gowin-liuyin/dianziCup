param([ValidateSet('initial', 'restored')][string]$Phase = 'initial')
$ErrorActionPreference = 'Stop'
$argumentLine = '-d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/runtime.py start'
$startedAt = [DateTimeOffset]::Now
$launcher = Start-Process -FilePath wsl.exe -ArgumentList $argumentLine -WindowStyle Hidden -PassThru -RedirectStandardOutput "D:/dianzi-runtime-cache/r10-neo4j-operations-fix1-20261016/supervisor_$Phase.stdout.log" -RedirectStandardError "D:/dianzi-runtime-cache/r10-neo4j-operations-fix1-20261016/supervisor_$Phase.stderr.log"
$record = [ordered]@{
    started_at = $startedAt.ToString('o')
    launcher_pid = $launcher.Id
    executable = 'wsl.exe'
    arguments = $argumentLine
    window_style = 'Hidden'
    phase = $Phase
    exit_code = $null
    exit_code_semantics = 'Background supervisor is ongoing; receipt is not a completion exit.'
}
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot "launch_$Phase.json") -Encoding UTF8
$record | ConvertTo-Json -Compress
