$ErrorActionPreference = 'Stop'
$cleanupRunRoot = [System.IO.Path]::GetFullPath('D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015')
$cleanupExpectedRunRoot = 'D:\dianzi\reports\runs\recovery_r01_dependency_review_1_20261015'
if (-not $cleanupRunRoot.Equals($cleanupExpectedRunRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Unexpected review run root' }
$cleanupResolvedRoot = (Resolve-Path -LiteralPath $cleanupRunRoot).Path
if (-not $cleanupResolvedRoot.Equals($cleanupExpectedRunRoot, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Resolved review root differs from authorized path' }
$cleanupPrefix = $cleanupRunRoot.TrimEnd('\') + '\'
$cleanupTargets = @('candidate_replay','baseline_replay') | ForEach-Object { [System.IO.Path]::GetFullPath((Join-Path $cleanupRunRoot $_)) }
$cleanupInputPath = Join-Path $cleanupRunRoot 'inputs.json'
$cleanupInputs = Get-Content -LiteralPath $cleanupInputPath -Raw | ConvertFrom-Json
$cleanupRecordedCommands = Get-Content -LiteralPath (Join-Path $cleanupRunRoot 'commands.json') -Raw | ConvertFrom-Json
if ($cleanupRecordedCommands.Count -ne 33) { throw 'Original review command manifest changed' }
if ($cleanupInputs.candidate_sha -ne '497740a771e7cb2d719ab22ebad34bd30539e20d' -or $cleanupInputs.baseline_sha -ne 'd0a179eeb3621cdf21a4cba94a6b5bd4e8a2a120') { throw 'Frozen input identity mismatch' }
$cleanupPrepare = Get-Content -LiteralPath (Join-Path $cleanupRunRoot 'prepare_review.py') -Raw
if (-not $cleanupPrepare.Contains('if destination.exists():') -or -not $cleanupPrepare.Contains('Review exports must be fresh')) { throw 'Exclusive initial creation guard missing' }
$cleanupOwned = @()
foreach ($cleanupTarget in $cleanupTargets) {
    if (-not $cleanupTarget.StartsWith($cleanupPrefix,[System.StringComparison]::OrdinalIgnoreCase)) { throw "Target outside authorized review root: $cleanupTarget" }
    if (-not (Test-Path -LiteralPath $cleanupTarget -PathType Container)) { throw "Missing owned workspace: $cleanupTarget" }
    if (-not (Resolve-Path -LiteralPath $cleanupTarget).Path.Equals($cleanupTarget,[System.StringComparison]::OrdinalIgnoreCase)) { throw 'Resolved cleanup target differs' }
    $cleanupTargetItem = Get-Item -LiteralPath $cleanupTarget -Force
    if (($cleanupTargetItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'Target is a reparse point' }
    $cleanupItems = @(Get-ChildItem -LiteralPath $cleanupTarget -Recurse -Force)
    if (@($cleanupItems | Where-Object { ($_.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 }).Count -ne 0) { throw 'Target contains a reparse point' }
    $cleanupFiles = @($cleanupItems | Where-Object { -not $_.PSIsContainer })
    $cleanupOwned += [pscustomobject]@{ path=$cleanupTarget; files=$cleanupFiles.Count; bytes=($cleanupFiles | Measure-Object -Property Length -Sum).Sum; reparse_points=0; ownership='Created fresh by this reviewer prepare_review.py, npm ci/build/test and frozen-quality imports; no pre-existing user files'; initially_absent_guard='prepare_review.py export_frontend rejects existing destination'; exclusive_top_level_children=@(Get-ChildItem -LiteralPath $cleanupTarget -Force | ForEach-Object Name) }
}
$cleanupRetained = @()
foreach ($cleanupArtifact in @(Get-ChildItem -LiteralPath $cleanupRunRoot -File -Force)) {
    if ($cleanupArtifact.Name -like 'cleanup_replay_workspaces*' -or $cleanupArtifact.Name -eq 'retained_artifacts.sha256.json') { continue }
    $cleanupRetained += [pscustomobject]@{ path=$cleanupArtifact.FullName; bytes=$cleanupArtifact.Length; sha256=(Get-FileHash -LiteralPath $cleanupArtifact.FullName -Algorithm SHA256).Hash.ToLowerInvariant() }
}
$cleanupZone = [System.TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time')
$cleanupStarted = [System.TimeZoneInfo]::ConvertTime([System.DateTimeOffset]::UtcNow,$cleanupZone).ToString('yyyy-MM-ddTHH:mm:sszzz')
foreach ($cleanupTarget in $cleanupTargets) { Remove-Item -LiteralPath $cleanupTarget -Recurse -Force }
foreach ($cleanupTarget in $cleanupTargets) { if (Test-Path -LiteralPath $cleanupTarget) { throw "Owned replay cleanup incomplete: $cleanupTarget" } }
foreach ($cleanupArtifact in $cleanupRetained) {
    if (-not (Test-Path -LiteralPath $cleanupArtifact.path -PathType Leaf)) { throw 'Retained artifact missing' }
    if ((Get-FileHash -LiteralPath $cleanupArtifact.path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $cleanupArtifact.sha256) { throw 'Original artifact changed during cleanup' }
}
$cleanupEnded = [System.TimeZoneInfo]::ConvertTime([System.DateTimeOffset]::UtcNow,$cleanupZone).ToString('yyyy-MM-ddTHH:mm:sszzz')
$cleanupRecord = [ordered]@{ task='R01 dependency reviewer temporary replay workspace recovery'; root=$cleanupRunRoot; started_at=$cleanupStarted; ended_at=$cleanupEnded; timezone='Asia/Shanghai'; exit_code=0; targets=$cleanupOwned; deleted_files=($cleanupOwned | Measure-Object -Property files -Sum).Sum; deleted_bytes=($cleanupOwned | Measure-Object -Property bytes -Sum).Sum; retained_original_command_count=33; retained_top_level_artifact_count=$cleanupRetained.Count; retained_original_artifact_hashes_unchanged=$true; remaining_copied_frontend_fixture_source_files=@(); reproduction='Export frontend from candidate/baseline Git SHAs and quality scripts/dev.py from fixed quality SHA using retained prepare_review.py in a fresh disposable replay workspace; replay sources and install caches are unnecessary submission artifacts'; preserved='Original 33 metadata/stdout/stderr logs, commands.json, actual_commands.md, JSON/JUnit test reports, inputs.json, independent_summary.json, frozen paths/diff, helper scripts and review report'; frozen_worktree_untouched='C:\Users\yinha\.codex\worktrees\recovery-r01-vitest-candidate\dianzi'; authorization='Explicit parent request to reclaim this reviewer exclusive generated replay workspaces; no user pre-existing files' }
$cleanupRetained | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath (Join-Path $cleanupRunRoot 'retained_artifacts.sha256.json') -Encoding utf8
$cleanupRecord | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath (Join-Path $cleanupRunRoot 'cleanup_replay_workspaces.ownership.json') -Encoding utf8
$cleanupRecord | ConvertTo-Json -Depth 8
