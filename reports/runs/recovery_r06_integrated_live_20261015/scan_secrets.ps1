$ErrorActionPreference = 'Stop'
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$previousPassword = $env:DIANZI_E2E_PASSWORD
try {
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    & D:\wt\r06-integrated-live-1156\backend\.venv\Scripts\python.exe -B "$PSScriptRoot/scan_secrets.py"
    $result = $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('DIANZI_E2E_PASSWORD', $previousPassword, 'Process')
    $identity = $null
}
exit $result
