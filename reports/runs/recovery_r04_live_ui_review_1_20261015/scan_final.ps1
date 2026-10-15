$ErrorActionPreference = 'Stop'
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
try {
    $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    & 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/scan_final.py"
    exit $LASTEXITCODE
} finally {
    Remove-Item Env:DIANZI_E2E_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:DIANZI_E2E_PASSWORD -ErrorAction SilentlyContinue
    $identity = $null
}
