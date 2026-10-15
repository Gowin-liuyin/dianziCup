$ErrorActionPreference = 'Stop'
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
try {
    $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    & 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/prepare_live.py"
    if ($LASTEXITCODE -ne 0) { throw 'controlled runtime preparation failed; inspect safe receipt' }
} finally {
    Remove-Item Env:DIANZI_E2E_USERNAME, Env:DIANZI_E2E_PASSWORD -ErrorAction SilentlyContinue
    $identity = $null
}
