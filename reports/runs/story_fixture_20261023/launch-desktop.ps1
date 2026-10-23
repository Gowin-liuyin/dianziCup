$ErrorActionPreference = "Continue"
$log = "D:\dianzi\reports\runs\story_fixture_20261023\docker-start.log"
try {
    $process = Start-Process -FilePath "C:\Program Files\Docker\Docker\Docker Desktop.exe" -PassThru
    "started pid=$($process.Id)" | Set-Content -Path $log
} catch {
    "start-failed $($_.Exception.GetType().FullName) $($_.Exception.Message)" | Set-Content -Path $log
}
Start-Sleep -Seconds 8
Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue |
    ForEach-Object { "running pid=$($_.Id)" } |
    Add-Content -Path $log
if (-not (Get-Process -Name "Docker Desktop" -ErrorAction SilentlyContinue)) {
    "not-running" | Add-Content -Path $log
}
