param([ValidateSet('prepare','start','collect','browser','preview')][string]$Mode)
$ErrorActionPreference = 'Stop'
$runPath = 'D:/dianzi/reports/runs/recovery_r06_document_live_20261015'
$privateText = & wsl.exe -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json
if ($LASTEXITCODE -ne 0) { throw 'authorized private configuration unavailable' }
$configuration = ($privateText -join "`n") | ConvertFrom-Json
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$previous = @{}
$ownedNames = @('PYTHONPATH','PYTHONUTF8','PYTHONIOENCODING','PYTHONDONTWRITEBYTECODE','DIANZI_E2E_USERNAME','DIANZI_E2E_PASSWORD','ALLOWED_ORIGINS','API_PROXY_TARGET','DIANZI_BEAT_SCHEDULE_PATH','DIANZI_LOG_SECRET_VALUES','GENERATION_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')
try {
    foreach ($field in $configuration.environment.PSObject.Properties) {
        $previous[$field.Name] = [Environment]::GetEnvironmentVariable($field.Name, 'Process')
        [Environment]::SetEnvironmentVariable($field.Name, $field.Value, 'Process')
    }
    foreach ($name in $ownedNames) { if (-not $previous.ContainsKey($name)) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') } }
    if (-not $env:DATABASE_URL.EndsWith('/test_dianzi_r04_pipeline_20261015')) { throw 'unexpected baseline database URI' }
    $env:DATABASE_URL = $env:DATABASE_URL -replace '/test_dianzi_r04_pipeline_20261015$', '/test_dianzi_r06_documents_live_20261015'
    $env:REDIS_URL = $env:REDIS_URL -replace '/[0-9]+$', '/13'
    if (-not $env:REDIS_URL.EndsWith('/13')) { throw 'unexpected Redis URI suffix' }
    $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    $env:ALLOWED_ORIGINS = '["http://127.0.0.1:25174"]'
    $env:API_PROXY_TARGET = 'http://127.0.0.1:28011'
    $env:PYTHONPATH = 'D:/wt/r06-document-live-0a45185/backend/src;D:/dianzi/reports/runs/recovery_r06_document_live_20261015;D:/dianzi/reports/runs/recovery_gb_controlled_collection_20261015'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:PYTHONDONTWRITEBYTECODE = '1'
    $env:DIANZI_BEAT_SCHEDULE_PATH = "$env:USERPROFILE/.codex/cache/dianzi/r06_document_live_0a45185_20261015_beat"
    $env:DIANZI_LOG_SECRET_VALUES = @($configuration.secret_values) + @($identity.DIANZI_E2E_PASSWORD) | ConvertTo-Json -Compress
    foreach ($name in @('GENERATION_API_KEY','DEEPSEEK_API_KEY','OPENAI_API_KEY','ANTHROPIC_API_KEY')) { [Environment]::SetEnvironmentVariable($name, $null, 'Process') }
    if ($Mode -eq 'prepare') {
        & D:/dianzi/backend/.venv/Scripts/python.exe -B "$runPath/prepare.py"
        if ($LASTEXITCODE -ne 0) { throw 'new isolated document DB preparation failed' }
    } elseif ($Mode -eq 'collect') {
        & D:/dianzi/backend/.venv/Scripts/python.exe -B "$runPath/collect.py"
        if ($LASTEXITCODE -ne 0) { throw 'bounded authenticated document collection failed; retained receipt has details' }
    } elseif ($Mode -eq 'browser') {
        $started=Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
        & node.exe 'D:/wt/r06-document-live-0a45185/frontend/node_modules/@playwright/test/cli.js' test --config "$runPath/playwright.config.cjs" *> "$runPath/browser.log"
        $result=$LASTEXITCODE
        [PSCustomObject]@{started_at=$started;ended_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');exit_code=$result;code_sha='0a45185ae3ffb73a6d186b98421e26a52f78bfc6';scope='actual PG authentication and source data; no request interception/model calls'} | ConvertTo-Json | Set-Content -Encoding utf8 "$runPath/browser_command.json"
        Write-Output "browser exit $result"
        if ($result -ne 0) { throw 'real document browser check failed; logs retained' }
    } elseif ($Mode -eq 'preview') {
        & node.exe "$runPath/capture-visible.cjs" *> "$runPath/visible_capture.log"
        if ($LASTEXITCODE -ne 0) { throw 'visible capture failed; sanitized log retained' }
        Write-Output 'real-data viewport captures recorded'
    } else {
        foreach ($port in @(28011,25174)) { if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { throw "owned port $port is occupied" } }
        if (Test-Path -LiteralPath "$runPath/runtime_start.json") { throw 'run already started' }
        $process = Start-Process -FilePath 'D:/dianzi/backend/.venv/Scripts/python.exe' -ArgumentList "-B $runPath/supervise.py" -WorkingDirectory 'D:/dianzi' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$runPath/supervisor.stdout.log" -RedirectStandardError "$runPath/supervisor.stderr.log"
        [PSCustomObject]@{observed_at=(Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz');launcher_pid=$process.Id;maximum_seconds=1200;api_port=28011;frontend_port=25174;redis_database=13;credentials_in_arguments=$false} | ConvertTo-Json | Set-Content -LiteralPath "$runPath/launch_receipt.json" -Encoding utf8
        Get-Content -LiteralPath "$runPath/launch_receipt.json" -Raw
    }
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    $configuration = $null
    $identity = $null
    $privateText = $null
}
