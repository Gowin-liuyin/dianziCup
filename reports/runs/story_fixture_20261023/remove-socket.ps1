$ErrorActionPreference = "Continue"
$target = Join-Path $env:LOCALAPPDATA "Docker\run\dockerInference"
$log = "D:\dianzi\reports\runs\story_fixture_20261023\remove-socket.log"
"target=$target" | Set-Content $log
Get-Process -Name "com.docker.backend","Docker Desktop","docker-ai" -ErrorAction SilentlyContinue |
    ForEach-Object { "stop $($_.ProcessName) $($_.Id)"; Stop-Process -Id $_.Id -Force }
Start-Sleep -Seconds 2
cmd /c "del /f /q `"$target`"" >> $log 2>&1
if (Test-Path -LiteralPath $target) {
    "still-present-after-del" | Add-Content $log
    cmd /c "rmdir /s /q `"$target`"" >> $log 2>&1
}
if (Test-Path -LiteralPath $target) {
    "still-present" | Add-Content $log
} else {
    "removed" | Add-Content $log
}
