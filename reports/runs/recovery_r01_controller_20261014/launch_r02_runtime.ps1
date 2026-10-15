param([ValidatePattern('^[a-z0-9_]{1,48}$')][string]$Segment = 'r02_default_4bab')

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$segmentPath = Join-Path $PSScriptRoot $Segment
if (Test-Path -LiteralPath $segmentPath) { throw 'runtime segment already exists' }
if (Get-NetTCPConnection -LocalPort 28000 -State Listen -ErrorAction SilentlyContinue) { throw 'owned runtime port already occupied' }
$privateOutput = & wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json
if ($LASTEXITCODE -ne 0) { throw 'private test connection unavailable' }
$runtimeConnections = ($privateOutput -join "`n") | ConvertFrom-Json
$runtimeIdentity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$runtimeEnvironment = @{
    DATABASE_URL = $runtimeConnections.TEST_DATABASE_URL
    REDIS_URL = $runtimeConnections.TEST_REDIS_URL
    OPENSEARCH_URL = 'http://127.0.0.1:29200'
    APP_ENV = 'test'
    DATA_MODE = 'live'
    ALLOWED_ORIGINS = '["http://127.0.0.1:25173","http://127.0.0.1:25300"]'
    DIANZI_E2E_USERNAME = $runtimeIdentity.DIANZI_E2E_USERNAME
    DIANZI_E2E_PASSWORD = $runtimeIdentity.DIANZI_E2E_PASSWORD
    DIANZI_RUNTIME_SEGMENT = $Segment
    DIANZI_RUNTIME_COMPONENTS = 'api,worker,scheduler'
    DIANZI_RUNTIME_CODE_SHA = (& git -C $repositoryRoot rev-parse HEAD)
    DIANZI_BEAT_SCHEDULE_PATH = "$env:USERPROFILE/.codex/cache/dianzi/$Segment-beat"
    DIANZI_BOOTSTRAP_RECEIPT = (Join-Path $PSScriptRoot "$Segment-bootstrap.json")
    PYTHONPATH = (Join-Path $repositoryRoot 'backend/src')
    PYTHONIOENCODING = 'utf-8'
    PYTHONUTF8 = '1'
}
$oldEnvironment = @{}
try {
    foreach ($name in $runtimeEnvironment.Keys) {
        $oldEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process')
        [Environment]::SetEnvironmentVariable($name, $runtimeEnvironment[$name], 'Process')
    }
    & "$repositoryRoot/backend/.venv/Scripts/python.exe" "$PSScriptRoot/bootstrap_runtime.py" *> (Join-Path $PSScriptRoot "$Segment-bootstrap.log")
    if ($LASTEXITCODE -ne 0) { throw 'isolated runtime bootstrap failed; inspect redacted receipt' }
    $supervisor = Start-Process -FilePath "$repositoryRoot/backend/.venv/Scripts/python.exe" -ArgumentList @("$PSScriptRoot/supervise_runtime.py") -WorkingDirectory $repositoryRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput (Join-Path $PSScriptRoot "$Segment-supervisor.stdout.log") -RedirectStandardError (Join-Path $PSScriptRoot "$Segment-supervisor.stderr.log")
    [PSCustomObject]@{ segment = $Segment; supervisor_pid = $supervisor.Id; maximum_duration_seconds = 3600; code_sha = $runtimeEnvironment.DIANZI_RUNTIME_CODE_SHA; port = 28000; credentials_in_arguments = $false } | ConvertTo-Json
} finally {
    foreach ($name in $oldEnvironment.Keys) { [Environment]::SetEnvironmentVariable($name, $oldEnvironment[$name], 'Process') }
    $runtimeIdentity = $null
    $runtimeConnections = $null
    $privateOutput = $null
}
