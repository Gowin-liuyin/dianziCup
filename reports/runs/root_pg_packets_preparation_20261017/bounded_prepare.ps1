$ErrorActionPreference = 'Stop'
$preparationDirectory = $PSScriptRoot
$info = [Diagnostics.ProcessStartInfo]::new()
$info.FileName = 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe'
$info.WorkingDirectory = $preparationDirectory
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$info.Environment.Clear()
$info.Environment['SystemRoot'] = 'C:/Windows'
$info.Environment['WINDIR'] = 'C:/Windows'
$info.Environment['PATH'] = 'C:/Windows/System32'
$info.Environment['TEMP'] = $preparationDirectory
$info.Environment['TMP'] = $preparationDirectory
$info.ArgumentList.Add('-I')
$info.ArgumentList.Add($preparationDirectory + '/prepare_packets.py')
$process = [Diagnostics.Process]::new()
$process.StartInfo = $info
[void]$process.Start()
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$timedOut = -not $process.WaitForExit(10000)
if ($timedOut) { $process.Kill($true); $process.WaitForExit() }
$stdoutTask.GetAwaiter().GetResult() | Set-Content -LiteralPath ($preparationDirectory + '/bounded_prepare.stdout.log') -Encoding utf8
$stderrTask.GetAwaiter().GetResult() | Set-Content -LiteralPath ($preparationDirectory + '/bounded_prepare.stderr.log') -Encoding utf8
if ($timedOut) { exit 124 }
exit $process.ExitCode
