$ErrorActionPreference = 'Stop'
$aggregateVaultPath = Join-Path $env:USERPROFILE '.codex/secrets/dianzi/01a13a70-858c-7d92-8070-0b2693ad7fc4.dpapi'
$aggregateVaultValues = (Get-Content -LiteralPath $aggregateVaultPath -Raw).Trim() | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText | ConvertFrom-Json -AsHashtable
$aggregatePriorValues = @{}
try {
    foreach ($aggregateProvider in @('HUNTER', 'QUAKE')) {
        $aggregateFields = @($aggregateVaultValues.Keys | Where-Object { $_ -match $aggregateProvider })
        if ($aggregateFields.Count -ne 1) { throw 'ambiguous aggregate credential fields' }
        $aggregateVariable = 'DIANZI_AGGREGATE_' + $aggregateProvider + '_KEY'
        $aggregatePriorValues[$aggregateVariable] = [Environment]::GetEnvironmentVariable($aggregateVariable, 'Process')
        [Environment]::SetEnvironmentVariable($aggregateVariable, $aggregateVaultValues[$aggregateFields[0]], 'Process')
    }
    $env:PYTHONIOENCODING = 'utf-8'
    & D:/dianzi/backend/.venv/Scripts/python.exe -B "$PSScriptRoot/probe_aggregates.py"
    $aggregateExit = $LASTEXITCODE
} finally {
    foreach ($aggregateVariable in $aggregatePriorValues.Keys) {
        [Environment]::SetEnvironmentVariable($aggregateVariable, $aggregatePriorValues[$aggregateVariable], 'Process')
    }
    $aggregateVaultValues = $null
}
exit $aggregateExit
