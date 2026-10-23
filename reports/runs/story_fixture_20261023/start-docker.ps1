try {
    Start-Service com.docker.service
    Write-Output "SERVICE_START_OK"
} catch {
    Write-Output ("SERVICE_START_FAIL " + $_.Exception.Message)
}
Get-Service com.docker.service | Format-List Name,Status,StartType
