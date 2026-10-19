$ErrorActionPreference = 'Stop'
$hunterAccountPath = Join-Path $env:USERPROFILE '.codex/secrets/dianzi/01a13a70-858c-7d92-8070-0b2693ad7fc4.dpapi'
$hunterAccountValues = (Get-Content -LiteralPath $hunterAccountPath -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json -AsHashtable
$hunterAccountFields = @($hunterAccountValues.Keys | Where-Object { $_ -match 'HUNTER' })
if ($hunterAccountFields.Count -ne 1) { throw 'ambiguous Hunter credential fields' }
$hunterPreviousValue = [Environment]::GetEnvironmentVariable('DIANZI_ACCOUNT_HUNTER_KEY', 'Process')
try {
    $env:DIANZI_ACCOUNT_HUNTER_KEY = $hunterAccountValues[$hunterAccountFields[0]]
    $env:PYTHONIOENCODING = 'utf-8'
    & D:/dianzi/backend/.venv/Scripts/python.exe -B "$PSScriptRoot/check_hunter.py"
    $hunterAccountResult = $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable('DIANZI_ACCOUNT_HUNTER_KEY', $hunterPreviousValue, 'Process')
    $hunterAccountValues = $null
}
exit $hunterAccountResult
