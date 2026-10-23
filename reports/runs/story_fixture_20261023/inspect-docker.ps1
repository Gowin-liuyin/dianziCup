$log = "D:\dianzi\reports\runs\story_fixture_20261023\docker-start.log"
Get-Process -Id 51576 -ErrorAction SilentlyContinue | ForEach-Object { "pid51576 name=$($_.ProcessName) path=$($_.Path)" } | Add-Content $log
Get-CimInstance Win32_Process -Filter "Name LIKE '%docker%' OR Name LIKE '%Docker%'" |
    ForEach-Object { "proc pid=$($_.ProcessId) name=$($_.Name)" } |
    Add-Content $log
if (-not (Get-CimInstance Win32_Process -Filter "Name LIKE '%ocker%'")) {
    "no-docker-process" | Add-Content $log
}
