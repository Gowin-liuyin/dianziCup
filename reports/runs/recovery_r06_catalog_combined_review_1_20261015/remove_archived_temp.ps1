$reviewRunRoot = 'D:/wt/r06-catalog-final-review/reports/runs/recovery_r06_catalog_combined_review_1_20261015'
$reviewTempRoot = (Resolve-Path -LiteralPath "$reviewRunRoot/temp_pure").Path
$expectedTempRoot = [System.IO.Path]::GetFullPath("$reviewRunRoot/temp_pure")
if ($reviewTempRoot -ne $expectedTempRoot) { throw 'Unexpected temporary target' }
$reviewArchiveManifest = Get-Content -LiteralPath "$reviewRunRoot/synthetic_temp_archive_manifest.json" -Raw | ConvertFrom-Json
if (-not $reviewArchiveManifest.verified_original_bytes) { throw 'Unverified archive' }
if ((Get-FileHash -LiteralPath $reviewArchiveManifest.archive -Algorithm SHA256).Hash.ToLower() -ne $reviewArchiveManifest.sha256) { throw 'Archive changed' }
Remove-Item -LiteralPath $reviewTempRoot -Recurse
Write-Output 'Removed only verified archived synthetic test scratch directory.'
