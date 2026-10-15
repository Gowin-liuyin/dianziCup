param(
    [Parameter(Mandatory = $true)][ValidatePattern('^[a-z0-9_-]+$')][string]$ProbeName,
    [Parameter(Mandatory = $true)][string]$Executable,
    [string]$ArgumentLine = '',
    [ValidateRange(20, 360)][int]$TimeoutSeconds = 25
)

$ErrorActionPreference = 'Stop'
$startedAt = [DateTimeOffset]::Now
$processInfo = New-Object System.Diagnostics.ProcessStartInfo
$processInfo.FileName = $Executable
$processInfo.Arguments = $ArgumentLine
$processInfo.UseShellExecute = $false
$processInfo.CreateNoWindow = $true
$processInfo.RedirectStandardOutput = $true
$processInfo.RedirectStandardError = $true
if ([IO.Path]::GetFileName($Executable) -eq 'wsl.exe' -and $ArgumentLine -match '^--(list|status|version)') {
    $processInfo.StandardOutputEncoding = [Text.Encoding]::Unicode
    $processInfo.StandardErrorEncoding = [Text.Encoding]::Unicode
}
$probeProcess = New-Object System.Diagnostics.Process
$probeProcess.StartInfo = $processInfo
$null = $probeProcess.Start()
$stdoutTask = $probeProcess.StandardOutput.ReadToEndAsync()
$stderrTask = $probeProcess.StandardError.ReadToEndAsync()
$completed = $probeProcess.WaitForExit($TimeoutSeconds * 1000)
if (-not $completed) {
    $probeProcess.Kill()
    $null = $probeProcess.WaitForExit(1000)
}
$stdout = if ($stdoutTask.Wait(1000)) { $stdoutTask.Result } else { '[stdout stream did not close after CLI timeout]' }
$stderr = if ($stderrTask.Wait(1000)) { $stderrTask.Result } else { '[stderr stream did not close after CLI timeout]' }
$exitCode = if ($completed) { $probeProcess.ExitCode } else { 124 }
$record = [ordered]@{
    probe_name = $ProbeName
    started_at = $startedAt.ToString('o')
    ended_at = [DateTimeOffset]::Now.ToString('o')
    executable = $Executable
    arguments = $ArgumentLine
    working_directory = (Get-Location).Path
    timeout_seconds = $TimeoutSeconds
    timed_out = -not $completed
    exit_code = $exitCode
    actual_process_exit_code = $probeProcess.ExitCode
    stdout_file = "$ProbeName.stdout.log"
    stderr_file = "$ProbeName.stderr.log"
}
[IO.File]::WriteAllText((Join-Path $PSScriptRoot "$ProbeName.stdout.log"), $stdout, [Text.Encoding]::UTF8)
[IO.File]::WriteAllText((Join-Path $PSScriptRoot "$ProbeName.stderr.log"), $stderr, [Text.Encoding]::UTF8)
$record | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath (Join-Path $PSScriptRoot "$ProbeName.json") -Encoding UTF8
$record | ConvertTo-Json -Compress
$stdout
$stderr
$probeProcess.Dispose()
exit $exitCode
