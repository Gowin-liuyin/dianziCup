$ErrorActionPreference = 'Stop'
$runPath = 'D:/dianzi/reports/runs/recovery_gb_controlled_collection_20261015'
if (Get-NetTCPConnection -LocalPort 28010 -State Listen -ErrorAction SilentlyContinue) { throw 'observation API port occupied' }
if (Test-Path -LiteralPath "$runPath/runtime_start.json") { throw 'run already used' }
$privateText = & wsl -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json
if ($LASTEXITCODE -ne 0) { throw 'authorized runtime configuration unavailable' }
$configuration = ($privateText -join "`n") | ConvertFrom-Json
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$previous = @{}
$setNames = @('PYTHONPATH','PYTHONUTF8','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE','DIANZI_BEAT_SCHEDULE_PATH','DIANZI_LOG_SECRET_VALUES','GENERATION_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')
try {
    foreach ($field in $configuration.environment.PSObject.Properties) {
        $previous[$field.Name] = [Environment]::GetEnvironmentVariable($field.Name, 'Process')
        [Environment]::SetEnvironmentVariable($field.Name, $field.Value, 'Process')
    }
    foreach ($name in $setNames) {
        $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
    }
    $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    $env:REDIS_URL = $env:REDIS_URL -replace '/[0-9]+$', '/12'
    if (-not $env:REDIS_URL.EndsWith('/12')) { throw 'Redis database suffix did not match' }
    $env:PYTHONPATH = 'D:/wt/gb-controlled-collection-1927/backend/src;D:/dianzi/reports/runs/recovery_gb_controlled_collection_20261015'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:DIANZI_BEAT_SCHEDULE_PATH = "$env:USERPROFILE/.codex/cache/dianzi/gb_collection_1927_20261015_beat"
    $env:DIANZI_LOG_SECRET_VALUES = @($configuration.secret_values) + @($identity.DIANZI_E2E_PASSWORD) | ConvertTo-Json -Compress
    foreach ($name in @('GENERATION_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')) {
        [Environment]::SetEnvironmentVariable($name, $null, 'Process')
    }
    $process = Start-Process -FilePath 'D:/dianzi/backend/.venv/Scripts/python.exe' -ArgumentList "-B $runPath/supervise.py" -WorkingDirectory 'D:/dianzi' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$runPath/supervisor.stdout.log" -RedirectStandardError "$runPath/supervisor.stderr.log"
    [PSCustomObject]@{observed_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');supervisor_launcher_pid=$process.Id;maximum_seconds=21600;api_port=28010;redis_database=12;queue='gb_collection_1927';credentials_in_arguments=$false} | ConvertTo-Json | Set-Content -LiteralPath "$runPath/launch_receipt.json" -Encoding utf8
    Get-Content -LiteralPath "$runPath/launch_receipt.json" -Raw
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    $identity = $null
    $configuration = $null
    $privateText = $null
}
