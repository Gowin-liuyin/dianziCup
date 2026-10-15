param([ValidateSet('real')][string]$Profile = 'real')

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$identity = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
try {
    $env:DIANZI_E2E_USERNAME = $identity.DIANZI_E2E_USERNAME
    $env:DIANZI_E2E_PASSWORD = $identity.DIANZI_E2E_PASSWORD
    & "$repositoryRoot/backend/.venv/Scripts/python.exe" "$PSScriptRoot/run_browser_recheck.py" $Profile
    if ($LASTEXITCODE -ne 0) { throw 'real browser tests failed; inspect redacted evidence' }
} finally {
    Remove-Item Env:DIANZI_E2E_USERNAME -ErrorAction SilentlyContinue
    Remove-Item Env:DIANZI_E2E_PASSWORD -ErrorAction SilentlyContinue
    $identity = $null
}
