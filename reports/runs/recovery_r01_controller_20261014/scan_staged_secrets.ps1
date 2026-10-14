param([Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9_]+\.json$')][string]$ReceiptName)

$ErrorActionPreference = 'Stop'
$repositoryRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$providerSecrets = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/01a13a70-858c-7d92-8070-0b2693ad7fc4.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$runtimeSecrets = (Get-Content -LiteralPath "$env:USERPROFILE/.codex/secrets/dianzi/r01_runtime_20261015.dpapi" -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json
$scanNames = @('DEEPSEEK_API_KEY', 'HUNTER_API_KEY', 'FOFA_API_KEY', 'QUAKE_API_KEY', 'ZOOMEYE_API_KEY')
try {
    foreach ($scanName in $scanNames) {
        [Environment]::SetEnvironmentVariable("DIANZI_SCAN_$scanName", $providerSecrets.$scanName, 'Process')
    }
    $env:DIANZI_SCAN_TEST_PASSWORD = $runtimeSecrets.DIANZI_E2E_PASSWORD
    Push-Location -LiteralPath $repositoryRoot
    try {
        & "$repositoryRoot/backend/.venv/Scripts/python.exe" "$PSScriptRoot/scan_staged_secrets.py" *> (Join-Path $PSScriptRoot $ReceiptName)
        if ($LASTEXITCODE -ne 0) { throw 'staged exact secret scan failed; inspect path-only receipt' }
    } finally { Pop-Location }
} finally {
    foreach ($scanName in $scanNames) {
        [Environment]::SetEnvironmentVariable("DIANZI_SCAN_$scanName", $null, 'Process')
    }
    Remove-Item Env:DIANZI_SCAN_TEST_PASSWORD -ErrorAction SilentlyContinue
    $providerSecrets = $null
    $runtimeSecrets = $null
}
