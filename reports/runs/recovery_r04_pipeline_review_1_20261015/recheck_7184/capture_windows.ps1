$ErrorActionPreference = 'Stop'
$reviewWorkspace = 'C:/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review-fix/dianzi'
$reviewRun = 'D:/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015/recheck_7184'
Push-Location -LiteralPath $reviewWorkspace
try {
    $reviewStarted = (Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz')
    $reviewHead = (& git rev-parse HEAD).Trim()
    $reviewTree = (& git rev-parse 'HEAD^{tree}').Trim()
    $reviewStatus = @(& git status --porcelain=v1)
    $reviewDiffNames = @(& git diff --name-only)
    & git diff --exit-code --quiet
    $reviewDiffExit = $LASTEXITCODE
    $reviewHashes = @()
    $reviewPaths = @(& git ls-files backend/src)
    foreach ($reviewPath in $reviewPaths) {
        $reviewBlob = (& git rev-parse ($reviewHead + ':' + $reviewPath)).Trim()
        $reviewActualBlob = (& git hash-object ('--path=' + $reviewPath) $reviewPath).Trim()
        $reviewSha256 = (Get-FileHash -Algorithm SHA256 -LiteralPath $reviewPath).Hash.ToLowerInvariant()
        $reviewHashes += [ordered]@{path=$reviewPath; git_blob=$reviewBlob; filtered_working_blob=$reviewActualBlob; sha256=$reviewSha256; matches_candidate=($reviewBlob -eq $reviewActualBlob)}
    }
    [ordered]@{cwd=$reviewWorkspace; started_at=$reviewStarted; ended_at=(Get-Date).ToString('yyyy-MM-ddTHH:mm:sszzz'); head=$reviewHead; tree=$reviewTree; status=$reviewStatus; diff_names=$reviewDiffNames; diff_exit_code=$reviewDiffExit; commands=@('git status --porcelain=v1','git diff --name-only','git diff --exit-code --quiet','git ls-files backend/src','git rev-parse HEAD:path','git hash-object --path=path path'); source_files=$reviewHashes} | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ($reviewRun + '/candidate_fixed_windows_git.json') -Encoding utf8
    [ordered]@{head=$reviewHead; status_count=$reviewStatus.Count; source_files=$reviewHashes.Count; source_mismatches=@($reviewHashes | Where-Object { -not $_.matches_candidate }).Count} | ConvertTo-Json -Compress
} finally { Pop-Location }

