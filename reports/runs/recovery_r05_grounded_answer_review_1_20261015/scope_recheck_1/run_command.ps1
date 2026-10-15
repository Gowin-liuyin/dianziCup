param(
    [Parameter(Mandatory=$true)][string]$Executable,
    [Parameter(Mandatory=$true)][string[]]$Arguments,
    [Parameter(Mandatory=$true)][string]$Label
)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [Console]::OutputEncoding
$env:PYTHONIOENCODING = 'utf-8'
$env:PYTHONUTF8 = '1'
$runPath = 'D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/scope_recheck_1'
$workingDirectory = 'C:/Users/yinha/.codex/worktrees/r05-grounded-answer-independent-review/dianzi/backend'
$env:COVERAGE_FILE = "$runPath/$Label.coverage"
$started = Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
Set-Location -LiteralPath $workingDirectory
& $Executable @Arguments 2>&1 | Tee-Object -FilePath "$runPath/$Label.log"
$commandExit = $LASTEXITCODE
$ended = Get-Date -Format 'yyyy-MM-ddTHH:mm:sszzz'
@{
    executable = $Executable
    arguments = $Arguments
    cwd = $workingDirectory
    started_at = $started
    completed_at = $ended
    exit_code = $commandExit
    code_sha = 'b1511145d4e6c15c5b1f6595bb7c776781ecf2ab'
    environment = 'D:/dianzi/reports/runs/recovery_r05_grounded_answer_review_1_20261015/venv'
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$runPath/$Label.receipt.json" -Encoding utf8
exit $commandExit
