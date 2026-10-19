$ErrorActionPreference = 'Stop'
$providerAccountPath = Join-Path $env:USERPROFILE '.codex/secrets/dianzi/01a13a70-858c-7d92-8070-0b2693ad7fc4.dpapi'
$providerAccountValues = (Get-Content -LiteralPath $providerAccountPath -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json -AsHashtable
$previousAccountValues = @{}
try {
    foreach ($providerAccountLabel in @('QUAKE', 'ZOOMEYE')) {
        $providerAccountFields = @($providerAccountValues.Keys | Where-Object { $_ -match $providerAccountLabel })
        if ($providerAccountFields.Count -ne 1) { throw 'ambiguous provider credential fields' }
        $providerAccountVariable = 'DIANZI_ACCOUNT_' + $providerAccountLabel + '_KEY'
        $previousAccountValues[$providerAccountVariable] = [Environment]::GetEnvironmentVariable($providerAccountVariable, 'Process')
        [Environment]::SetEnvironmentVariable($providerAccountVariable, $providerAccountValues[$providerAccountFields[0]], 'Process')
    }
    $env:PYTHONIOENCODING = 'utf-8'
    & D:/dianzi/backend/.venv/Scripts/python.exe -B "$PSScriptRoot/check_accounts.py"
    $providerAccountResult = $LASTEXITCODE
} finally {
    foreach ($providerAccountVariable in $previousAccountValues.Keys) {
        [Environment]::SetEnvironmentVariable($providerAccountVariable, $previousAccountValues[$providerAccountVariable], 'Process')
    }
    $providerAccountValues = $null
}
exit $providerAccountResult
