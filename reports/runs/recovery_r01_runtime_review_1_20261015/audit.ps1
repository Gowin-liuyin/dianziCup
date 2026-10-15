param([string]$Label,[string]$WorkingDirectory,[string]$Command)
$reviewRoot = 'D:\dianzi\reports\runs\recovery_r01_runtime_review_1_20261015'
$zone = [TimeZoneInfo]::FindSystemTimeZoneById('China Standard Time')
$start = [TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow,$zone).ToString('yyyy-MM-ddTHH:mm:sszzz')
$logPath = Join-Path $reviewRoot ($Label + '.log')
Push-Location -LiteralPath $WorkingDirectory
$global:LASTEXITCODE = 0
try { & ([scriptblock]::Create($Command)) *>&1 | Tee-Object -FilePath $logPath; $code = $global:LASTEXITCODE; if ($null -eq $code) { $code = 0 } }
catch { $_ | Out-String | Tee-Object -FilePath $logPath -Append; $code = 1 }
finally { Pop-Location }
$end = [TimeZoneInfo]::ConvertTime([DateTimeOffset]::UtcNow,$zone).ToString('yyyy-MM-ddTHH:mm:sszzz')
$entry = [ordered]@{label=$Label;cwd=$WorkingDirectory;start=$start;end=$end;exit=$code;command=$Command;raw_log=$logPath}
$entry | ConvertTo-Json -Compress | Add-Content -LiteralPath (Join-Path $reviewRoot 'commands.jsonl')
Write-Output ('AUDIT '+($entry|ConvertTo-Json -Compress))
exit $code
