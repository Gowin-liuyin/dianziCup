$ErrorActionPreference = 'Stop'
$workspaceRoot = (Resolve-Path -LiteralPath 'D:/dianzi').Path
$cacheRoot = [System.IO.Path]::GetFullPath('D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/retired-review-venvs/20261015')
$names = @('recovery_r02_persistence_review_1_20261015', 'recovery_r05_grounded_answer_review_1_20261015')
$plans = @()
foreach ($name in $names) {
    $source = (Resolve-Path -LiteralPath (Join-Path $workspaceRoot "reports/runs/$name/venv")).Path
    $destination = [System.IO.Path]::GetFullPath((Join-Path $cacheRoot $name))
    if (-not $source.StartsWith($workspaceRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'source is outside the owned workspace' }
    if (-not $destination.StartsWith($cacheRoot + [System.IO.Path]::DirectorySeparatorChar, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'destination is outside the owned cache' }
    if (Test-Path -LiteralPath $destination) { throw 'cache destination already exists' }
    if ((Get-Item -LiteralPath $source).Attributes -band [System.IO.FileAttributes]::ReparsePoint) { throw 'source root is a reparse point' }
    $active = Get-CimInstance Win32_Process | Where-Object { ($_.ExecutablePath -and $_.ExecutablePath.StartsWith($source + '\', [System.StringComparison]::OrdinalIgnoreCase)) -or ($_.CommandLine -and $_.CommandLine.Contains($source)) }
    if ($active) { throw 'owned environment still has active process references' }
    $plans += [PSCustomObject]@{source=$source; destination=$destination}
}
& 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/retired_venv_inventory.py" before
if ($LASTEXITCODE -ne 0) { throw 'owned environment inventory failed' }
New-Item -ItemType Directory -Path $cacheRoot -Force | Out-Null
foreach ($plan in $plans) { Move-Item -LiteralPath $plan.source -Destination $plan.destination -ErrorAction Stop }
& 'D:/dianzi/backend/.venv/Scripts/python.exe' "$PSScriptRoot/retired_venv_inventory.py" after
if ($LASTEXITCODE -ne 0) { throw 'moved environment verification failed' }
$plans | ConvertTo-Json | Set-Content -LiteralPath "$PSScriptRoot/retired_review_venvs_move.json" -Encoding utf8
