$ErrorActionPreference = 'Stop'
function GetCheckedHash($path) {
    $hash = [System.Security.Cryptography.SHA256]::Create()
    try { return ([System.BitConverter]::ToString($hash.ComputeHash([System.IO.File]::ReadAllBytes($path)))).Replace('-', '').ToLowerInvariant() }
    finally { $hash.Dispose() }
}
$source = [System.IO.Path]::GetFullPath('D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/pg_pytest_tmp')
$destination = [System.IO.Path]::GetFullPath('D:/wt/gc-8a-validation-tmp/pg_pytest_tmp')
if ($source -ne 'D:\wt\gc-8a-validation\reports\runs\recovery_gc_integrated_8a_validation_20261016\pg_pytest_tmp' -or $destination -ne 'D:\wt\gc-8a-validation-tmp\pg_pytest_tmp') { throw 'Unexpected temporary path' }
if (Test-Path -LiteralPath $destination) { throw 'Destination already exists' }
$before = @(Get-ChildItem -LiteralPath $source -File -Recurse | ForEach-Object { @{ path = $_.FullName.Substring($source.Length); bytes = $_.Length; sha256 = (GetCheckedHash $_.FullName) } })
Move-Item -LiteralPath $source -Destination $destination
$after = @(Get-ChildItem -LiteralPath $destination -File -Recurse | ForEach-Object { @{ path = $_.FullName.Substring($destination.Length); bytes = $_.Length; sha256 = (GetCheckedHash $_.FullName) } })
if (($before | ConvertTo-Json -Depth 3 -Compress) -ne ($after | ConvertTo-Json -Depth 3 -Compress)) { throw 'Temporary bytes changed' }
@{ source = $source; destination = $destination; moved_at = [System.DateTimeOffset]::Now.ToString('o'); files = $before; exact_bytes_unchanged = $true } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath 'D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/pg_temp_relocation.json' -Encoding utf8
Write-Output 'Own PostgreSQL temporary files moved with exact SHA-256 preservation.'
