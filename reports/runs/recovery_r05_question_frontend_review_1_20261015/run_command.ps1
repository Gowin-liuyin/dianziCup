param([string]$Label,[string]$WorkingDirectory,[string]$Executable,[string[]]$Arguments)
$ErrorActionPreference = 'Stop'
$runRoot = 'D:\dianzi\reports\runs\recovery_r05_question_frontend_review_1_20261015'
$started = (Get-Date).ToUniversalTime().AddHours(8).ToString('yyyy-MM-ddTHH:mm:ss+08:00')
Push-Location -LiteralPath $WorkingDirectory
try {
  & $Executable @Arguments *> (Join-Path $runRoot "$Label.log")
  $exitCode = $LASTEXITCODE
} finally { Pop-Location }
$finished = (Get-Date).ToUniversalTime().AddHours(8).ToString('yyyy-MM-ddTHH:mm:ss+08:00')
[ordered]@{ label=$Label; started_at=$started; completed_at=$finished; cwd=$WorkingDirectory; executable=$Executable; arguments=$Arguments; exit_code=$exitCode } | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 -LiteralPath (Join-Path $runRoot "$Label.command.json")
Get-Content -LiteralPath (Join-Path $runRoot "$Label.log")
exit $exitCode
