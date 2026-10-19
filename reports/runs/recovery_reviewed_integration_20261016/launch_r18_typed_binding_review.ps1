param([ValidateSet('typed_task_pg_atomicity_owner','typed_task_pg_0031_constraints','typed_task_pg_publication','typed_task_pg_integrity_expiry','typed_task_pg_locator_replay_expiry')][string]$Batch)
$ErrorActionPreference = 'Stop'
$reviewRoot = 'D:/wt/r18-typed-task-binding-review1'
$run = $reviewRoot + '/reports/runs/r18_typed_task_binding_review1_20261017/pg_support'
$hashes = @{
    'run_pg_review.py' = 'cce6ce3bf3330ca8239cec84c193e879cb555b55552448c36bd69321ee0397ea'
    'worker_entry.py' = 'c6bf4c406fc7bc61652999dc70c1e7f57ec82ddcf3a2cc5432e9f1ae75f83dbe'
    'pg_controller_admission.json' = 'd4e3672fd3dab2595fef6ef7d955d20f0dc6ca38e6f2a318a89ac47107c3acdd'
}
foreach ($name in $hashes.Keys) {
    if ((Get-FileHash -LiteralPath ($run + '/' + $name)).Hash.ToLowerInvariant() -ne $hashes[$name]) {
        throw 'frozen review entry changed'
    }
}
$receiptRoot = 'D:/dianzi/reports/runs/recovery_reviewed_integration_20261016'
$receiptPath = $receiptRoot + ('/r18_typed_binding_' + $Batch + '_launch.json')
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
$info.ArgumentList.Add($run + '/run_pg_review.py')
$info.ArgumentList.Add($Batch)
$info.Environment['PYTHONPATH'] = 'D:/dianzi/backend/.venv/Lib/site-packages;' + $run
$info.Environment['PYTHONNOUSERSITE'] = '1'
$info.Environment['R18_REVIEW_PARENT_DATABASE_URL'] = $parentResource.TEST_DATABASE_URL
$info.Environment['DIANZI_REVIEW_RESOURCE_AUTHORIZED'] = 'r18-typed-task-binding-review1'
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
[IO.File]::WriteAllText($receiptRoot + ('/r18_typed_binding_' + $Batch + '_stdout.log'), $stdoutText)
[IO.File]::WriteAllText($receiptRoot + ('/r18_typed_binding_' + $Batch + '_stderr.log'), $stderrText)
$receipt = [ordered]@{
    batch = $Batch; started_at = $started; ended_at = [DateTimeOffset]::Now.ToString('o')
    exit_code = $process.ExitCode; timeout_seconds = 60; outer_timeout = $timedOut
    authorized_until_utc = $deadline.ToString('o'); source_sha = '3e84d7655c0f6afcf19094265298cfc43b8afd2a'
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
