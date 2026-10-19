$ErrorActionPreference = 'Stop'
$taskListener = @(Get-NetTCPConnection -LocalPort 26573 -State Listen -ErrorAction SilentlyContinue)
$taskNodes = @(Get-CimInstance Win32_Process -Filter "Name = 'node.exe'" | Where-Object { $_.CommandLine -like '*r17-sbom-review1-fix1*' })
[pscustomobject]@{ checked_at = (Get-Date).ToString('o'); review_port = 26573; listening_count = $taskListener.Count; review_node_count = $taskNodes.Count; killed_process_count = 0 } | ConvertTo-Json
if ($taskListener.Count -ne 0 -or $taskNodes.Count -ne 0) { exit 1 }
