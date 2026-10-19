param([ValidateSet('pg_ports_receipts','pg_ports_identity','pg_ports_limits','pg_ports_sourcecycle')][string]$Batch)
$ErrorActionPreference = 'Stop'
$reviewRoot = 'D:/wt/r18-ports-review1'
$run = $reviewRoot + '/reports/runs/r18_plugin_production_ports_review1_20261017/pg_support'
$hashes = @{
    'run_pg_review.py' = 'e59295cae97d8f566d8eadf49b1a57d57342706ab11c91348e19d69f0fa57a10'
    'worker_entry.py' = 'c0fb18c77711223557c0568107aad0160571e6e00b0cdb2e79f7999514085dde'
    'pg_controller_admission.json' = '1183f98a9781cb7a90be4f3843b91638bd37d438c6b70b17de06448c3f06c51f'
}
foreach ($name in $hashes.Keys) {
    if ((Get-FileHash -LiteralPath ($run + '/' + $name)).Hash.ToLowerInvariant() -ne $hashes[$name]) {
        throw 'frozen review entry changed'
    }
}
$receiptRoot = 'D:/wt/r18-ports-review1/reports/runs/r18_plugin_production_ports_review1_20261017'
$receiptPath = $receiptRoot + ('/root_launch_' + $Batch + '_launch.json')
if (Test-Path -LiteralPath $receiptPath) { throw 'refusing receipt overwrite' }
$started = [DateTimeOffset]::Now.ToString('o')
$deadline = [DateTimeOffset]::UtcNow.AddMinutes(10)
$pointer = [IntPtr]::Zero
try {
    $secure = ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi'))
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
    $parentResource = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) | ConvertFrom-Json -DateKind String
} finally {
    if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}
if (-not $parentResource.TEST_DATABASE_URL) { throw 'authorized parent reference missing' }
$info = [Diagnostics.ProcessStartInfo]::new()
$info.FileName = 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe'
$info.WorkingDirectory = $reviewRoot
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$info.ArgumentList.Add($run + '/worker_entry.py')
$info.ArgumentList.Add('run_pg_review')
$info.ArgumentList.Add($Batch)
$info.Environment['PYTHONPATH'] = 'D:/dianzi/backend/.venv/Lib/site-packages;' + $run
$info.Environment['PYTHONNOUSERSITE'] = '1'
$info.Environment['R18_REVIEW_PARENT_DATABASE_URL'] = $parentResource.TEST_DATABASE_URL
$info.Environment['DIANZI_REVIEW_RESOURCE_AUTHORIZED'] = 'root-batch17-review1'
$info.Environment['R18_REVIEW_BATCH_ALLOWLIST'] = ('["' + $Batch + '"]')
$info.Environment['R18_REVIEW_AUTHORIZED_UNTIL_UTC'] = $deadline.ToString('o')
$process = [Diagnostics.Process]::new()
$process.StartInfo = $info
[void]$process.Start()
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$timedOut = -not $process.WaitForExit(60000)
if ($timedOut) { $process.Kill(); $process.WaitForExit() }
$stdoutText = $stdoutTask.GetAwaiter().GetResult().Replace([string]$parentResource.TEST_DATABASE_URL, '[REDACTED]')
$stderrText = $stderrTask.GetAwaiter().GetResult().Replace([string]$parentResource.TEST_DATABASE_URL, '[REDACTED]')
[IO.File]::WriteAllText($receiptRoot + ('/root_launch_' + $Batch + '_stdout.log'), $stdoutText)
[IO.File]::WriteAllText($receiptRoot + ('/root_launch_' + $Batch + '_stderr.log'), $stderrText)
$receipt = [ordered]@{
    batch = $Batch; started_at = $started; ended_at = [DateTimeOffset]::Now.ToString('o')
    exit_code = $process.ExitCode; timeout_seconds = 60; outer_timeout = $timedOut
    authorized_until_utc = $deadline.ToString('o'); source_sha = 'eea52940506fb19b07d452c25ec3a273b0e42cca'
    root_environment_injected = $true; secret_values_printed = $false
    full_process_peak = 'independent native controller receipt'
}
$receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8
$parentResource = $null
$stdoutText = $null
$stderrText = $null
$receipt | ConvertTo-Json -Compress
if ($timedOut) { exit 124 }
exit $process.ExitCode
