$ErrorActionPreference = 'Stop'
$snapshot = [ordered]@{
    recorded_at = [DateTimeOffset]::Now.ToString('o')
    docker_processes = @(Get-Process -ErrorAction SilentlyContinue | Where-Object { $_.ProcessName -match '^(Docker Desktop|com\.docker\.|docker$|docker-desktop)' } | Select-Object Id,ProcessName,StartTime,Path)
    afunix_file = (Get-Item -LiteralPath 'C:\Windows\System32\drivers\afunix.sys' | Select-Object FullName,Length,@{Name='Version';Expression={$_.VersionInfo.FileVersion}})
    runtime_directory = (Get-Item -LiteralPath 'C:\Users\yinha\AppData\Local\Docker\run' | Select-Object FullName,Attributes)
}
$snapshot | ConvertTo-Json -Depth 5
