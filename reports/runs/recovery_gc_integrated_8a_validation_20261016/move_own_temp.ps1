$ErrorActionPreference = 'Stop'
$source = [System.IO.Path]::GetFullPath('D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/backend_pytest_tmp')
$destination = [System.IO.Path]::GetFullPath('D:/wt/gc-8a-validation-tmp/backend_pytest_tmp')
if ($source -ne 'D:\wt\gc-8a-validation\reports\runs\recovery_gc_integrated_8a_validation_20261016\backend_pytest_tmp' -or $destination -ne 'D:\wt\gc-8a-validation-tmp\backend_pytest_tmp') { throw 'Unexpected temporary path' }
if (Test-Path -LiteralPath $destination) { throw 'Destination already exists' }
$before = @(Get-ChildItem -LiteralPath $source -File -Recurse | ForEach-Object { @{ path = $_.FullName.Substring($source.Length); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() } })
New-Item -ItemType Directory -Path 'D:/wt/gc-8a-validation-tmp' -Force | Out-Null
Move-Item -LiteralPath $source -Destination $destination
$after = @(Get-ChildItem -LiteralPath $destination -File -Recurse | ForEach-Object { @{ path = $_.FullName.Substring($destination.Length); bytes = $_.Length; sha256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash.ToLowerInvariant() } })
if (($before | ConvertTo-Json -Depth 3 -Compress) -ne ($after | ConvertTo-Json -Depth 3 -Compress)) { throw 'Temporary bytes changed' }
@{ source = $source; destination = $destination; moved_at = [System.DateTimeOffset]::Now.ToString('o'); files = $before; exact_bytes_unchanged = $true } | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath 'D:/wt/gc-8a-validation/reports/runs/recovery_gc_integrated_8a_validation_20261016/temp_relocation.json' -Encoding utf8
Write-Output 'Own temporary files moved with exact SHA-256 preservation.'
