$ErrorActionPreference = 'Stop'
$providerSecrets = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/01a13a70-858c-7d92-8070-0b2693ad7fc4.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
try {
    $env:DIANZI_LIVE_MODEL_KEY = $providerSecrets.DEEPSEEK_API_KEY
    $env:PYTHONUTF8 = '1'
    $env:PYTHONIOENCODING = 'utf-8'
    & 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/probe_generation_live_single_line.py"
    if ($LASTEXITCODE -ne 0) { throw 'bounded supplier probe failed before safe result completion' }
} finally {
    Remove-Item Env:DIANZI_LIVE_MODEL_KEY, Env:PYTHONUTF8, Env:PYTHONIOENCODING -ErrorAction SilentlyContinue
    $providerSecrets = $null
}
