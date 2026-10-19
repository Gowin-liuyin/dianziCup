param([ValidateSet('preflight','start')][string]$Mode = 'preflight')
$ErrorActionPreference = 'Stop'
$ops = 'D:/dianzi-runtime-cache/r06-f3-ops-20261017'
$python = 'D:/dianzi-runtime-cache/r06-live-restart-20261016/runtime_env/.venv/Scripts/python.exe'
if ($Mode -eq 'preflight') {
    & "$ops/windows_preflight.ps1"
    exit
}
& $python -B -c "import sys;from datetime import datetime;sys.path.insert(0,'$ops');from configuration import require_activation,require_start_window,ZONE;require_activation();require_start_window(datetime.now(ZONE))"
if ($LASTEXITCODE -ne 0) { throw 'new root activation refused before credentials or processes' }
& "$ops/windows_preflight.ps1"
& $python -B -c "import sys;sys.path.insert(0,'$ops');from configuration import require_activation,prepare_launch;prepare_launch(require_activation())"
if ($LASTEXITCODE -ne 0) { throw 'exact frozen runtime gate creation failed' }
try {
$connectionText = (Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText
$connection = $connectionText | ConvertFrom-Json
$databaseUri = [Uri]$connection.TEST_DATABASE_URL
$redisUri = [Uri]$connection.TEST_REDIS_URL
if ($databaseUri.Host -cne '127.0.0.1' -or $databaseUri.Port -ne 25432 -or $databaseUri.AbsolutePath -cne '/test_dianzi_r01_20261014' -or [Uri]::UnescapeDataString(($databaseUri.UserInfo -split ':',2)[0]) -cne 'test_dianzi_r01') { throw 'fixed parent PostgreSQL identity differs' }
if ($redisUri.Host -cne '127.0.0.1' -or $redisUri.Port -ne 26379 -or $redisUri.Scheme -cne 'redis' -or -not $redisUri.UserInfo.Contains(':') -or ($redisUri.UserInfo -split ':',2)[1].Length -eq 0) { throw 'fixed authenticated Redis identity differs' }
$cursorText = (Get-Content -LiteralPath 'D:/dianzi-private/revalidation-cursor-key-20261016.dpapi' -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText
$cursor = $cursorText | ConvertFrom-Json
if ($cursor.REVALIDATION_CURSOR_SIGNING_KEY -cnotmatch '^[0-9a-f]{64}$') { throw 'persisted cursor signing key unavailable' }
$minioText = & wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-minio-r02-20261015/private/connection.json
if ($LASTEXITCODE -ne 0) { throw 'owned store reference unavailable' }
$minio = ($minioText -join "`n") | ConvertFrom-Json
$identity = (Get-Content -LiteralPath 'C:/Users/yinha/.codex/secrets/dianzi/r01_runtime_20261015.dpapi' -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$runtime = 'D:/dianzi-runtime-cache/r06-f3-core-20261017'
$values = @{
    DATABASE_URL = ($connection.TEST_DATABASE_URL -replace '/[^/]+$','/test_dianzi_r06_912_20261017_f15191e6ea74')
    REDIS_URL = ($connection.TEST_REDIS_URL -replace '/[0-9]+$','/15')
    REVALIDATION_CURSOR_SIGNING_KEY = $cursor.REVALIDATION_CURSOR_SIGNING_KEY
    OPENSEARCH_URL = 'http://127.0.0.1:29200'
    APP_ENV = 'test'; DATA_MODE = 'live'; CONTENT_STORE_BACKEND = 'minio'
    MINIO_ENDPOINT = '127.0.0.1:29400'; MINIO_BUCKET = $minio.bucket
    MINIO_ACCESS_KEY = $minio.access_key; MINIO_SECRET_KEY = $minio.secret_key; MINIO_SECURE = 'false'
    DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME; DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    ALLOWED_ORIGINS = '["http://127.0.0.1:25176"]'; SOURCE_POLLING_ENABLED = 'true'; DNS_RESOLVER = 'cloudflare_doh'
    PYTHONPATH = "D:/wt/r06-product-912-runtime-20261017/backend/src;$runtime;$ops"
    PYTHONUTF8 = '1'; PYTHONIOENCODING = 'utf-8'; PYTHONDONTWRITEBYTECODE = '1'
    DIANZI_BEAT_SCHEDULE_PATH = "$ops/beat"; RAW_CONTENT_DIRECTORY = "$ops/raw-unused-minio-forced"
    NO_PROXY = '127.0.0.1,localhost'
    DIANZI_LOG_SECRET_VALUES = (@($connection.postgres_password,$connection.redis_password,$identity.DIANZI_E2E_PASSWORD,$minio.access_key,$minio.secret_key,$cursor.REVALIDATION_CURSOR_SIGNING_KEY) | ConvertTo-Json -Compress)
}
    $minioProcess = Start-Process -FilePath 'wsl.exe' -ArgumentList '-d Ubuntu-22.04 -u root --exec python3 -B /mnt/d/dianzi-runtime-cache/r06-f3-ops-20261017/minio_segment.py --start' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$ops/minio_supervisor.stdout.log" -RedirectStandardError "$ops/minio_supervisor.stderr.log"
    $limit = (Get-Date).AddSeconds(15)
    while (-not (Test-Path -LiteralPath "$ops/minio_start.json")) {
        if ($minioProcess.HasExited -or (Get-Date) -ge $limit) { throw 'new MinIO identity unavailable' }
        Start-Sleep -Milliseconds 100
    }
    $start = New-Object System.Diagnostics.ProcessStartInfo
    $start.FileName = $python
    $start.Arguments = "-B $ops/guardian.py --start"
    $start.WorkingDirectory = 'D:/wt/r06-product-912-runtime-20261017/backend'
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $start.Environment.Clear()
    foreach ($name in @('SystemRoot','SystemDrive','WINDIR','PATH','TEMP','TMP')) {
        $value = [Environment]::GetEnvironmentVariable($name,'Process')
        if ($value) { $start.Environment[$name] = $value }
    }
    foreach ($name in $values.Keys) { $start.Environment[$name] = [string]$values[$name] }
    $guardian = [System.Diagnostics.Process]::Start($start)
    [ordered]@{ observed_at = (Get-Date -Format o); guardian_launcher_pid = $guardian.Id; minio_launcher_pid = $minioProcess.Id; credentials_in_arguments = $false; maximum_seconds = 22500 } | ConvertTo-Json | Set-Content -Encoding utf8 "$ops/launch_receipt.json"
    $readyLimit = (Get-Date).AddSeconds(30)
    while (-not (Test-Path -LiteralPath "$ops/guardian_start.json")) {
        if ($guardian.HasExited -or (Get-Date) -ge $readyLimit) { throw 'new guardian identity unavailable' }
        Start-Sleep -Milliseconds 100
    }
} catch {
    if ($minioProcess) {
        'owned startup failed; original MinIO owner requested to stop' | Set-Content -Encoding utf8 "$ops/minio_stop.request"
    }
    [ordered]@{ error_type = $_.Exception.GetType().Name; details = 'withheld'; formal_six_hour_pass = $false } | ConvertTo-Json
    exit 1
} finally {
    $connectionText = $null; $connection = $null; $minioText = $null; $minio = $null; $identity = $null; $values = $null
    $cursorText = $null; $cursor = $null; $databaseUri = $null; $redisUri = $null
}
