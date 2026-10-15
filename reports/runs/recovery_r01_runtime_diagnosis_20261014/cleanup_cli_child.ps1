$ErrorActionPreference = 'Stop'
$OutputEncoding = [Text.Encoding]::UTF8
[Console]::OutputEncoding = [Text.Encoding]::UTF8
$cliProcess = Get-Process -Id 13848 -ErrorAction SilentlyContinue
if ($null -eq $cliProcess) {
    [ordered]@{ recorded_at = [DateTimeOffset]::Now.ToString('o'); pid = 13848; already_exited = $true; stopped = $false } | ConvertTo-Json
    exit 0
}
$expectedStart = [DateTimeOffset]::Parse('2026-10-14T21:16:34.6092078+08:00')
$actualStart = [DateTimeOffset]$cliProcess.StartTime
$expectedExecutable = 'C:\Program Files\Docker\Docker\resources\cli-plugins\docker-desktop.exe'
$before = [ordered]@{ pid = $cliProcess.Id; process_name = $cliProcess.ProcessName; executable = $cliProcess.Path; started_at = $actualStart.ToString('o') }
if ($cliProcess.ProcessName -ne 'docker-desktop' -or $cliProcess.Path -ne $expectedExecutable -or [math]::Abs(($actualStart - $expectedStart).TotalMilliseconds) -gt 1) {
    $before | ConvertTo-Json
    throw 'The remaining process does not match the exact diagnostic CLI child; it was not stopped.'
}
Stop-Process -Id $cliProcess.Id -ErrorAction Stop
[ordered]@{ recorded_at = [DateTimeOffset]::Now.ToString('o'); verified_before = $before; stopped = $true; still_exists = ($null -ne (Get-Process -Id 13848 -ErrorAction SilentlyContinue)) } | ConvertTo-Json -Depth 3
