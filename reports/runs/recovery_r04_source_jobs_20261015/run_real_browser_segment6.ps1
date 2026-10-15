$ErrorActionPreference = 'Stop'
$privatePath = Join-Path $env:USERPROFILE '.codex/secrets/dianzi/r01_runtime_20261015.dpapi'
$secret = (Get-Content -LiteralPath $privatePath -Raw).Trim() | ConvertTo-SecureString
$credentials = ($secret | ConvertFrom-SecureString -AsPlainText) | ConvertFrom-Json
$env:DIANZI_E2E_USERNAME = $credentials.DIANZI_E2E_USERNAME
$env:DIANZI_E2E_PASSWORD = $credentials.DIANZI_E2E_PASSWORD
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $env:USERPROFILE '.codex/cache/dianzi/r01_playwright_1248'
$env:PYTHONUTF8 = '1'
try {
    & 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/run_real_browser_segment6.py"
    $resultCode = $LASTEXITCODE
} finally {
    Remove-Item Env:DIANZI_E2E_USERNAME, Env:DIANZI_E2E_PASSWORD, Env:PLAYWRIGHT_BROWSERS_PATH, Env:PYTHONUTF8 -ErrorAction SilentlyContinue
    $credentials = $null
    $secret = $null
}
exit $resultCode
