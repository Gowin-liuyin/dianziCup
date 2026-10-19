param([ValidateSet('prepare','start','verify','status','diagnose','export','seal','freeze')][string]$Mode)
$ErrorActionPreference = 'Stop'
$runPath = 'D:/dianzi/reports/runs/recovery_r06_live_segment_8a_20261016'
$pythonPath = 'D:/dianzi-runtime-cache/r06-live-8a-20261016/runtime_env/.venv/Scripts/python.exe'
$gate = Get-Content -LiteralPath "$runPath/root_authorization.json" -Raw | ConvertFrom-Json
if (-not $gate.root_live_authorized -or $gate.product_sha -ne '8a1b04d48346d8550f0326a77f003246a0ebbab5' -or $gate.database -ne 'test_dianzi_r06_catalog_live_8a_20261016') { throw 'frozen authorization required before secrets' }
$connectionText = & wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json
if ($LASTEXITCODE -ne 0) { throw 'owned dependency connection unavailable' }
$connection = ($connectionText -join "`n") | ConvertFrom-Json
$minioText = & wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-minio-r02-20261015/private/connection.json
if ($LASTEXITCODE -ne 0) { throw 'owned MinIO identity unavailable' }
$minio = ($minioText -join "`n") | ConvertFrom-Json
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$values = @{
 DATABASE_URL=($connection.TEST_DATABASE_URL -replace '/[^/]+$','/test_dianzi_r06_catalog_live_8a_20261016'); REDIS_URL=($connection.TEST_REDIS_URL -replace '/[0-9]+$','/15'); OPENSEARCH_URL='http://127.0.0.1:29200';
 APP_ENV='test'; DATA_MODE='live'; CONTENT_STORE_BACKEND='minio'; MINIO_ENDPOINT='127.0.0.1:29400'; MINIO_BUCKET=$minio.bucket; MINIO_ACCESS_KEY=$minio.access_key; MINIO_SECRET_KEY=$minio.secret_key; MINIO_SECURE='false';
 DIANZI_E2E_USERNAME=$identity.DIANZI_E2E_USERNAME; DIANZI_E2E_PASSWORD=$identity.DIANZI_E2E_PASSWORD; ALLOWED_ORIGINS='["http://127.0.0.1:25176"]'; SOURCE_POLLING_ENABLED='true'; DNS_RESOLVER='cloudflare_doh';
 PYTHONPATH="D:/wt/r06-live-8a-20261016/backend/src;$runPath"; PYTHONUTF8='1'; PYTHONIOENCODING='utf-8'; PYTHONDONTWRITEBYTECODE='1';
 DIANZI_BEAT_SCHEDULE_PATH='D:/dianzi-runtime-cache/r06-live-8a-20261016/beat'; RAW_CONTENT_DIRECTORY='D:/dianzi-runtime-cache/r06-live-8a-20261016/raw'; NO_PROXY='127.0.0.1,localhost';
 DIANZI_LOG_SECRET_VALUES=(@($connection.postgres_password,$connection.redis_password,$identity.DIANZI_E2E_PASSWORD,$minio.access_key,$minio.secret_key) | ConvertTo-Json -Compress)
}
$previous = @{}
try {
 foreach ($name in $values.Keys) { $previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process'); [Environment]::SetEnvironmentVariable($name,$values[$name],'Process') }
 foreach ($name in @('GENERATION_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')) { $previous[$name]=[Environment]::GetEnvironmentVariable($name,'Process'); [Environment]::SetEnvironmentVariable($name,$null,'Process') }
 $started=Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
 if ($Mode -eq 'start') {
  if (Test-Path -LiteralPath "$runPath/runtime_start.json") { throw 'new segment already started' }
  if (Get-NetTCPConnection -LocalPort 28013 -State Listen -ErrorAction SilentlyContinue) { throw 'API port occupied; do not terminate listener' }
  $process=Start-Process -FilePath $pythonPath -ArgumentList "-B $runPath/supervise.py" -WorkingDirectory 'D:/wt/r06-live-8a-20261016/backend' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$runPath/supervisor.stdout.log" -RedirectStandardError "$runPath/supervisor.stderr.log"
  [PSCustomObject]@{observed_at=$started;launcher_pid=$process.Id;creation_time=$process.StartTime.ToUniversalTime().ToString('o');maximum_seconds=21600;credentials_in_arguments=$false} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/launch_receipt.json"
  Write-Output "owned segment launched PID $($process.Id)"
 } else {
  $scriptName = @{prepare='prepare.py';verify='verify_startup.py';status='status.py';diagnose='diagnose.py';export='export_release.py';seal='seal.py';freeze='freeze_artifacts.py'}[$Mode]
  & $pythonPath -B "$runPath/$scriptName" *> "$runPath/$($Mode).log"
  $result=$LASTEXITCODE
  [PSCustomObject]@{started_at=$started;ended_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');exit_code=$result;command="python -B $scriptName";cwd='D:/wt/r06-live-8a-20261016/backend';product_sha=$gate.product_sha} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/$($Mode)_command.json"
  Write-Output "$Mode exit $result"
  if ($result -ne 0) { throw 'owned operation failed; sanitized log retained' }
 }
} finally {
 foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name,$previous[$name],'Process') }
 $connectionText=$null; $connection=$null; $identity=$null; $minioText=$null; $minio=$null
}
