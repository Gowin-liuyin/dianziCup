$ErrorActionPreference = 'Stop'
$reviewRoot = 'D:/wt/r18-component-review1'
$run = $reviewRoot + '/reports/runs/r18_component_selector_review1_pg_retry1_20261017'
$hashes = @{
    'run_pg_review.py' = 'def4d7bf45b4d570a5e078df1caa25f7a96668e8726a14c964e42536df4f7c31'
    'worker_entry.py' = '6190130e3ca76690044207b213fc3b1995d0d2b0cb63de10462cc44808f4af5b'
    'pg_controller_admission.json' = '729b6d18bfafcc2f92767afa2afb79ea7990ffae7bbc64118f6996129427beaf'
}
foreach ($name in $hashes.Keys) {
    if ((Get-FileHash -LiteralPath ($run + '/' + $name)).Hash.ToLowerInvariant() -ne $hashes[$name]) {
        throw 'frozen review entry changed'
    }
}
$receiptRoot = 'D:/dianzi/reports/runs/recovery_reviewed_integration_20261016'
$receiptPath = $receiptRoot + '/r18_component_pg7_retry1_launch.json'
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
$info.ArgumentList.Add($run + '/run_pg_review.py')
$info.Environment['PYTHONPATH'] = 'D:/dianzi/backend/.venv/Lib/site-packages'
$info.Environment['PYTHONNOUSERSITE'] = '1'
$info.Environment['R18_REVIEW_PARENT_DATABASE_URL'] = $parentResource.TEST_DATABASE_URL
$info.Environment['DIANZI_REVIEW_RESOURCE_AUTHORIZED'] = 'r18-component-selector-review1'
$info.Environment['R18_REVIEW_BATCH_ALLOWLIST'] = '["pg_selector_7"]'
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
[IO.File]::WriteAllText($receiptRoot + '/r18_component_pg7_retry1_stdout.log', $stdoutText)
[IO.File]::WriteAllText($receiptRoot + '/r18_component_pg7_retry1_stderr.log', $stderrText)
$receipt = [ordered]@{
    batch = 'pg_selector_7'; started_at = $started; ended_at = [DateTimeOffset]::Now.ToString('o')
    exit_code = $process.ExitCode; timeout_seconds = 60; outer_timeout = $timedOut
    authorized_until_utc = $deadline.ToString('o'); source_sha = '4c35d5a198c54584d4c17e4f3b556b62ebee645c'
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
