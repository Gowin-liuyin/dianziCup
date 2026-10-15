$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$processes = Get-Process 'Docker Desktop','com.docker.backend','com.docker.proxy','vmmemWSL','wslservice' -ErrorAction SilentlyContinue | Select-Object Id,ProcessName,StartTime,CPU,WorkingSet64
$operatingSystem = Get-CimInstance Win32_OperatingSystem | Select-Object Caption,Version,TotalVisibleMemorySize,FreePhysicalMemory
$drives = Get-PSDrive C,D | Select-Object Name,Used,Free
$services = Get-Service 'com.docker.service','WslService','LxssManager','vmcompute' -ErrorAction SilentlyContinue | Select-Object Name,@{ Name = 'Status'; Expression = { $_.Status.ToString() } },@{ Name = 'StartType'; Expression = { $_.StartType.ToString() } }
$pipes = [IO.Directory]::GetFiles('\\.\pipe\') | Where-Object { $_ -match 'docker|Docker' }
$logFiles = Get-Item -LiteralPath (Join-Path $env:LOCALAPPDATA 'Docker\log\host\com.docker.backend.exe.log'),(Join-Path $env:LOCALAPPDATA 'Docker\log\host\Docker Desktop.exe.log') -ErrorAction SilentlyContinue | Select-Object FullName,Length,LastWriteTime
$appFiles = Get-Item -LiteralPath 'C:\Program Files\Docker\Docker\Docker Desktop.exe','C:\Program Files\Docker\Docker\resources\com.docker.diagnose.exe','C:\Program Files\Docker\Docker\resources\bin\docker.exe' -ErrorAction SilentlyContinue | Select-Object FullName,LastWriteTime,@{ Name = 'Version'; Expression = { $_.VersionInfo.ProductVersion } }
[ordered]@{ recorded_at = [DateTimeOffset]::Now.ToString('o'); processes = @($processes); operating_system = $operatingSystem; drives = @($drives); services = @($services); docker_pipes = @($pipes); docker_log_files = @($logFiles); application_files = @($appFiles) } | ConvertTo-Json -Depth 5
