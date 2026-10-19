param([ValidateSet('prepare','start','collect','browser','preview','diagnose','browser-v2','finalize')][string]$Mode)
$ErrorActionPreference = 'Stop'
$runPath = 'D:/dianzi/reports/runs/recovery_r06_integrated_live_20261015'
$privateText = & wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json
if ($LASTEXITCODE -ne 0) { throw 'authorized private configuration unavailable' }
$configuration = ($privateText -join "`n") | ConvertFrom-Json
$minioText = & wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-minio-r02-20261015/private/connection.json
if ($LASTEXITCODE -ne 0) { throw 'authorized MinIO configuration unavailable' }
$minioConfiguration = ($minioText -join "`n") | ConvertFrom-Json
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$previous = @{}
$ownedNames = @('PYTHONPATH','PYTHONUTF8','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE','DIANZI_E2E_USERNAME','DIANZI_E2E_PASSWORD','ALLOWED_ORIGINS','API_PROXY_TARGET','DIANZI_BEAT_SCHEDULE_PATH','DIANZI_LOG_SECRET_VALUES','GENERATION_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY','SOURCE_POLLING_ENABLED','RAW_CONTENT_DIRECTORY','APP_ENV','CONTENT_STORE_BACKEND','MINIO_ENDPOINT','MINIO_BUCKET','MINIO_ACCESS_KEY','MINIO_SECRET_KEY','MINIO_SECURE')
try {
    foreach ($field in $configuration.environment.PSObject.Properties) {
        $previous[$field.Name] = [Environment]::GetEnvironmentVariable($field.Name, 'Process')
        [Environment]::SetEnvironmentVariable($field.Name, $field.Value, 'Process')
    }
    foreach ($name in $ownedNames) { if (-not $previous.ContainsKey($name)) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') } }
    if (-not $env:DATABASE_URL.EndsWith('/test_dianzi_r04_pipeline_20261015')) { throw 'unexpected baseline database URI' }
    $env:DATABASE_URL = $env:DATABASE_URL -replace '/test_dianzi_r04_pipeline_20261015$', '/test_dianzi_r06_integrated_live_20261015'
    $env:REDIS_URL = $env:REDIS_URL -replace '/[0-9]+$', '/15'
    if (-not $env:REDIS_URL.EndsWith('/15')) { throw 'unexpected Redis URI suffix' }
    $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    $env:ALLOWED_ORIGINS = '["http://127.0.0.1:25175"]'
    $env:SOURCE_POLLING_ENABLED = 'true'
    $env:APP_ENV = 'test'
    $env:CONTENT_STORE_BACKEND = 'minio'
    $env:MINIO_ENDPOINT = $minioConfiguration.endpoint
    $env:MINIO_BUCKET = $minioConfiguration.bucket
    $env:MINIO_ACCESS_KEY = $minioConfiguration.access_key
    $env:MINIO_SECRET_KEY = $minioConfiguration.secret_key
    $env:MINIO_SECURE = 'false'
    $env:RAW_CONTENT_DIRECTORY = 'D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/raw'
    $env:API_PROXY_TARGET = 'http://127.0.0.1:28012'
    $env:PYTHONPATH = 'D:\wt\r06-integrated-live-1156/backend/src;D:/dianzi/reports/runs/recovery_r06_integrated_live_20261015'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:DIANZI_BEAT_SCHEDULE_PATH = "$env:USERPROFILE/.codex/cache/dianzi/r06_integrated_live_1156_20261015_beat"
    $env:DIANZI_LOG_SECRET_VALUES = @($configuration.secret_values) + @($identity.DIANZI_E2E_PASSWORD,$minioConfiguration.access_key,$minioConfiguration.secret_key) | ConvertTo-Json -Compress
    foreach ($name in @('GENERATION_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')) { [Environment]::SetEnvironmentVariable($name, $null, 'Process') }
    if ($Mode -eq 'prepare') {
        $started=Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
        & D:\wt\r06-integrated-live-1156\backend\.venv\Scripts\python.exe -B "$runPath/prepare.py" *> "$runPath/prepare.log"
        $result=$LASTEXITCODE
        [PSCustomObject]@{started_at=$started;ended_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');exit_code=$result;command='python -B prepare.py';cwd='D:/dianzi';code_sha='1156b2ed6616e3a4297215c2893d2cbe633f5215'} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/prepare_command.json"
        Write-Output "isolated preparation exit $result"
        if ($result -ne 0) { throw 'new isolated integrated-live DB preparation failed; sanitized receipt retained' }
    } elseif ($Mode -eq 'collect') {
        $started=Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
        & D:\wt\r06-integrated-live-1156\backend\.venv\Scripts\python.exe -B "$runPath/collect.py" *> "$runPath/collection.log"
        $result=$LASTEXITCODE
        [PSCustomObject]@{started_at=$started;ended_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');exit_code=$result;command='python -B collect.py';cwd='D:/dianzi';code_sha='1156b2ed6616e3a4297215c2893d2cbe633f5215'} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/collection_command.json"
        Write-Output "actual default beat collection observation exit $result"
        if ($result -ne 0) { throw 'bounded actual default beat collection observation failed; retained receipt has details' }
    } elseif ($Mode -eq 'browser') {
        if (-not (Test-Path -LiteralPath "$runPath/collection_receipt.json")) { throw 'actual collection receipt required before browser observation' }
        if (Test-Path -LiteralPath "$runPath/browser.request") { throw 'owned browser command already requested' }
        [PSCustomObject]@{requested_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');owner='r06_integrated_live_validation';code_sha='1156b2ed6616e3a4297215c2893d2cbe633f5215'} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/browser.request"
        Write-Output 'actual browser requested inside owned supervisor resource job'
    } elseif ($Mode -eq 'finalize') {
        $started=Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
        & D:\wt\r06-integrated-live-1156\backend\.venv\Scripts\python.exe -B "$runPath/finalize_observation.py" *> "$runPath/finalize.log"
        $result=$LASTEXITCODE
        [PSCustomObject]@{started_at=$started;ended_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');exit_code=$result;command='python -B finalize_observation.py';cwd='D:/dianzi';code_sha='1156b2ed6616e3a4297215c2893d2cbe633f5215';only_local_postgresql_minio=$true} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/finalize_command.json"
        Write-Output "final read-only observation exit $result"
        if ($result -ne 0) { throw 'final read-only metadata or evidence check instrument failed; original run retained' }
    } elseif ($Mode -eq 'browser-v2') {
        & D:\wt\r06-integrated-live-1156\backend\.venv\Scripts\python.exe -B "$runPath/browser_v2_controller.py" *> "$runPath/browser_v2_controller.log"
        if ($LASTEXITCODE -ne 0) { throw 'corrected browser controller failed; bounded original segment retained' }
        Get-Content -LiteralPath "$runPath/browser_command_v2.json" -Raw
    } elseif ($Mode -eq 'diagnose') {
        $started=Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
        & D:\wt\r06-integrated-live-1156\backend\.venv\Scripts\python.exe -B "$runPath/diagnose_sources.py" *> "$runPath/source_diagnosis.log"
        $result=$LASTEXITCODE
        [PSCustomObject]@{started_at=$started;ended_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');exit_code=$result;command='python -B diagnose_sources.py';cwd='D:/dianzi';code_sha='1156b2ed6616e3a4297215c2893d2cbe633f5215';external_request_limit=4} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/source_diagnosis_command.json"
        Write-Output "fixed-source raw-input diagnosis exit $result"
        if ($result -ne 0) { throw 'diagnosis instrument failed; partial raw evidence retained' }
    } elseif ($Mode -eq 'preview') {
        & node.exe "$runPath/capture-visible.cjs" *> "$runPath/visible_capture.log"
        if ($LASTEXITCODE -ne 0) { throw 'visible capture failed; sanitized log retained' }
        Write-Output 'real-data viewport captures recorded'
    } else {
        foreach ($port in @(28012,25175)) { if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "owned port $port is occupied" } }
        if (Test-Path -LiteralPath "$runPath/runtime_start.json") { throw 'run already started' }
        $process = Start-Process -FilePath 'D:\wt\r06-integrated-live-1156\backend\.venv\Scripts\python.exe' -ArgumentList "-B $runPath/supervise.py" -WorkingDirectory 'D:/dianzi' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$runPath/supervisor.stdout.log" -RedirectStandardError "$runPath/supervisor.stderr.log"
        [PSCustomObject]@{observed_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');launcher_pid=$process.Id;maximum_seconds=1200;api_port=28012;frontend_port=25175;redis_database=15;credentials_in_arguments=$false} | ConvertTo-Json | Set-Content -LiteralPath "$runPath/launch_receipt.json" -Encoding utf8
        Get-Content -LiteralPath "$runPath/launch_receipt.json" -Raw
    }
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    $configuration = $null
    $identity = $null
    $privateText = $null
    $minioText = $null
    $minioConfiguration = $null
}
