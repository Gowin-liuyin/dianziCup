$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$runtimeEvidence = (& (Join-Path $PSScriptRoot 'reparse_tag.ps1')) | ConvertFrom-Json
if (-not $runtimeEvidence.expected_af_unix -or $runtimeEvidence.is_name_surrogate -or $runtimeEvidence.length_bytes -ne 0 -or $null -ne $runtimeEvidence.link_target) {
    throw 'The listener is not the verified zero-byte, non-redirecting AF_UNIX runtime object.'
}
$runtimeDirectoryPath = 'C:\Users\yinha\AppData\Local\Docker\run'
$runtimePath = $runtimeEvidence.resolved_path
$backupPath = Join-Path $runtimeDirectoryPath ('dockerInference.backup-' + [DateTimeOffset]::Now.ToString('yyyyMMddTHHmmsszzz').Replace(':',''))
if ((Split-Path -Parent $runtimePath) -ne $runtimeDirectoryPath -or (Split-Path -Parent $backupPath) -ne $runtimeDirectoryPath -or (Test-Path -LiteralPath $backupPath)) {
    throw 'The isolation paths did not satisfy the same-directory, non-overwrite boundary.'
}
$runtimeEvidence | ConvertTo-Json -Depth 3 | Set-Content -LiteralPath (Join-Path $PSScriptRoot 'socket_isolation_before.json') -Encoding UTF8
try {
    Move-Item -LiteralPath $runtimePath -Destination $backupPath -ErrorAction Stop
    $backupMetadata = Get-Item -LiteralPath $backupPath -Force | Select-Object FullName,Length,Attributes,LinkType,Target,CreationTime,LastWriteTime
    [ordered]@{
        recorded_at = [DateTimeOffset]::Now.ToString('o')
        moved = $true
        original_path = $runtimePath
        backup_path = $backupPath
        original_still_exists = (Test-Path -LiteralPath $runtimePath)
        backup_metadata = $backupMetadata
        restore_command = "Move-Item -LiteralPath '$backupPath' -Destination '$runtimePath'"
        restore_precondition = 'Docker Desktop stopped; original path absent; do not overwrite a recreated listener.'
    } | ConvertTo-Json -Depth 4
} catch {
    [ordered]@{
        recorded_at = [DateTimeOffset]::Now.ToString('o')
        moved = $false
        original_path = $runtimePath
        backup_path = $backupPath
        error = $_.Exception.Message
        original_still_exists = (Test-Path -LiteralPath $runtimePath)
        backup_exists = (Test-Path -LiteralPath $backupPath)
    } | ConvertTo-Json -Depth 4
    exit 1
}
