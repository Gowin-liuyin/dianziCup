param([ValidateSet('prepare', 'supervise', 'probe')][string]$Mode)
$ErrorActionPreference = 'Stop'
$privateText = & wsl -d Ubuntu-22.04 -u root --exec cat /tmp/dianzi-r04-live-20261015/private/runtime_8f6bd9.json
if ($LASTEXITCODE -ne 0) { throw 'owned private runtime configuration unavailable' }
$configuration = ($privateText -join "`n") | ConvertFrom-Json
$vaultPath = Join-Path $env:USERPROFILE '.codex/secrets/dianzi/01a13a70-858c-7d92-8070-0b2693ad7fc4.dpapi'
$vaultText = (Get-Content -Raw -LiteralPath $vaultPath).Trim()
$modelSecrets = ($vaultText | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText) | ConvertFrom-Json
$previous = @{}
$ownedNames = @('PYTHONPATH', 'PYTHONUTF8', 'PYTHONIOENCODING', 'GENERATION_PROVIDER', 'GENERATION_MODEL', 'GENERATION_API_KEY', 'SEMANTIC_MODEL_CACHE_DIRECTORY', 'DIANZI_LOG_SECRET_VALUES')
$pythonPath = 'C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi/backend/.venv/Scripts/python.exe'
try {
    foreach ($field in $configuration.environment.PSObject.Properties) {
        $previous[$field.Name] = [Environment]::GetEnvironmentVariable($field.Name, 'Process')
        [Environment]::SetEnvironmentVariable($field.Name, $field.Value, 'Process')
    }
    foreach ($name in $ownedNames) { if (-not $previous.ContainsKey($name)) { $previous[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') } }
    $env:PYTHONPATH = 'C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi/backend/src'
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    $env:GENERATION_PROVIDER = 'deepseek_openai'
    $env:GENERATION_MODEL = 'deepseek-flash'
    $env:GENERATION_API_KEY = $modelSecrets.DEEPSEEK_API_KEY
    $env:SEMANTIC_MODEL_CACHE_DIRECTORY = "$env:USERPROFILE/.codex/cache/dianzi/r05-semantic-runtime"
    $env:DIANZI_LOG_SECRET_VALUES = @($configuration.secret_values) + @($modelSecrets.DEEPSEEK_API_KEY) | ConvertTo-Json -Compress
    if ($Mode -eq 'prepare') {
        & $pythonPath "$PSScriptRoot/prepare_product_live_dc014.py"
        if ($LASTEXITCODE -ne 0) { throw 'isolated migration failed' }
    } elseif ($Mode -eq 'supervise') {
        if (Get-NetTCPConnection -LocalPort 28000 -State Listen -ErrorAction SilentlyContinue) { throw 'owned API port is occupied' }
        $process = Start-Process -FilePath $pythonPath -ArgumentList "$PSScriptRoot/supervise_product_live_dc014.py" -WorkingDirectory 'D:/dianzi' -WindowStyle Hidden -PassThru -RedirectStandardOutput "$PSScriptRoot/product_supervisor_dc014c9.stdout.log" -RedirectStandardError "$PSScriptRoot/product_supervisor_dc014c9.stderr.log"
        [PSCustomObject]@{ supervisor_pid=$process.Id; maximum_seconds=900; port=28000; credentials_in_arguments=$false } | ConvertTo-Json
    } else {
        & $pythonPath "$PSScriptRoot/probe_product_live.py"
        if ($LASTEXITCODE -ne 0) { throw 'bounded real product probe failed; inspect retained evidence' }
    }
} finally {
    foreach ($name in $previous.Keys) { [Environment]::SetEnvironmentVariable($name, $previous[$name], 'Process') }
    $configuration = $null
    $privateText = $null
    $vaultText = $null
    $modelSecrets = $null
}
