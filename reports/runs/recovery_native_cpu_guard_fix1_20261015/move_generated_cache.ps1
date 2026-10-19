$ErrorActionPreference = 'Stop'
$sourceRoot = (Resolve-Path -LiteralPath 'D:/wt/native-cpu-guard/backend/src').Path
$cacheRoot = 'D:/tmp/nativecpu-guard-fix1-20261015/generated-pyc'
New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
$moves = @()
foreach ($relativePath in @('ai_intel/__pycache__', 'ai_intel/infrastructure/__pycache__', 'ai_intel/ingestion/parsing/__pycache__')) {
    $sourcePath = (Resolve-Path -LiteralPath (Join-Path $sourceRoot $relativePath)).Path
    if (-not $sourcePath.StartsWith($sourceRoot + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'cache outside owned source root' }
    $items = @(Get-Item -LiteralPath $sourcePath) + @(Get-ChildItem -LiteralPath $sourcePath -Recurse -Force)
    if ($items.Where({ $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }).Count -ne 0) { throw 'cache has a reparse point' }
    if ($items.Where({ -not $_.PSIsContainer -and $_.Extension -ne '.pyc' }).Count -ne 0) { throw 'cache contains other files' }
    $targetPath = [System.IO.Path]::GetFullPath((Join-Path $cacheRoot ($relativePath.Replace('/', '_'))))
    if (-not $targetPath.StartsWith([System.IO.Path]::GetFullPath($cacheRoot) + '\', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'cache destination escaped' }
    if (Test-Path -LiteralPath $targetPath) { throw 'cache destination already exists' }
    $files = @($items.Where({ -not $_.PSIsContainer }) | ForEach-Object { $_.FullName })
    Move-Item -LiteralPath $sourcePath -Destination $targetPath
    $moves += @{ source = $sourcePath; destination = $targetPath; files = $files }
}
@{ completed_at = (Get-Date).ToString('o'); moves = $moves } | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath 'D:/wt/native-cpu-guard/reports/runs/recovery_native_cpu_guard_fix1_20261015/cache_moves.json' -Encoding utf8
