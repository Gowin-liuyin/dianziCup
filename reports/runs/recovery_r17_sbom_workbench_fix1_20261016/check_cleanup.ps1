$taskListeners = @(Get-NetTCPConnection -LocalPort 26373 -State Listen -ErrorAction SilentlyContinue)
$taskPreviewNodes = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object { $_.CommandLine -match 'vite.*preview.*26373' })
[ordered]@{ checked_at=(Get-Date -Format o); port=26373; listener_count=$taskListeners.Count; owned_preview_node_count=$taskPreviewNodes.Count } | ConvertTo-Json
if ($taskListeners.Count -ne 0 -or $taskPreviewNodes.Count -ne 0) { exit 1 }
