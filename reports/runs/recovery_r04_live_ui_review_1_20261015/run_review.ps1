param([ValidateSet('run2','complement','nvd_dates')][string]$Label = 'run2')
$ErrorActionPreference = 'Stop'
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
try {
    $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    $env:UI_REVIEW_LABEL = $Label
    & 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/run_review.py"
    exit $LASTEXITCODE
} finally {
    Remove-Item Env:DIANZI_E2E_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:DIANZI_E2E_PASSWORD -ErrorAction SilentlyContinue
    Remove-Item Env:UI_REVIEW_LABEL -ErrorAction SilentlyContinue
    $identity = $null
}
