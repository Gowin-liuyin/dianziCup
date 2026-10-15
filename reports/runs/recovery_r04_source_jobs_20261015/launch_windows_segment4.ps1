$ErrorActionPreference = 'Stop'
if (Get-NetTCPConnection -LocalPort 28000 -State Listen -ErrorAction SilentlyContinue) { throw 'owned API port is still occupied' }
$privateText = & wsl -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json
if ($LASTEXITCODE -ne 0) { throw 'private runtime configuration unavailable' }
$configuration = ($privateText -join "`n") | ConvertFrom-Json
$previous = @{}
try {
    foreach ($field in $configuration.environment.PSObject.Properties) {
        $previous[$field.Name] = [Environment]::GetEnvironmentVariable($field.Name, 'Process')
        [Environment]::SetEnvironmentVariable($field.Name, $field.Value, 'Process')
    }
    $env:PYTHONPATH = 'C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi/backend/src'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:DIANZI_BEAT_SCHEDULE_PATH = "$env:USERPROFILE/.codex/cache/dianzi/r04-live-windows-8f6bd9-20261015-beat"
    $env:DIANZI_LOG_SECRET_VALUES = $configuration.secret_values | ConvertTo-Json -Compress
    $process = Start-Process -FilePath 'D:/dianzi/backend/.venv/Scripts/python.exe' -ArgumentList "$PSScriptRoot/supervise_windows_segment4.py" -WorkingDirectory 'D:/dianzi' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot/windows_supervisor_8f6bd9.stdout.log" -RedirectStandardError "$PSScriptRoot/windows_supervisor_8f6bd9.stderr.log"
    [PSCustomObject]@{supervisor_pid=$process.Id; maximum_seconds=900; port=28000; credentials_in_arguments=$false} | ConvertTo-Json
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    Remove-Item Env:PYTHONPATH, Env:PYTHONUTF8, Env:PYTHONIOENCODING, Env:DIANZI_BEAT_SCHEDULE_PATH, Env:DIANZI_LOG_SECRET_VALUES -ErrorAction SilentlyContinue
    $configuration = $null
    $privateText = $null
}
