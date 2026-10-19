param([Parameter(Mandatory)][ValidateSet('default8','pg19','neo4j7','transitions2')][string]$Phase, [int]$Attempt=2)
$ErrorActionPreference = 'Stop'
$reviewRun = 'r10_default_graph_73a6f5dcc780'
$reviewRoot = 'D:/wt/r10g-review1'
$receiptRoot = 'D:/dianzi/reports/runs/recovery_reviewed_integration_20261016'
$receiptPath = Join-Path $receiptRoot ('r10_fresh_' + $Phase + '_attempt' + $Attempt + '_launch.json')
if (Test-Path -LiteralPath $receiptPath) { throw 'refusing receipt overwrite' }
function Read-AuthorizedPrivateDocument([string]$path) {
    $pointer = [IntPtr]::Zero
    try {
        $secured = ConvertTo-SecureString -String ([IO.File]::ReadAllText($path))
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secured)
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) | ConvertFrom-Json -DateKind String
    } finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
    }
}
$started = [DateTimeOffset]::Now.ToString('o')
$parentResource = Read-AuthorizedPrivateDocument 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi'
$graphResource = Read-AuthorizedPrivateDocument 'D:/dianzi-private/r10_default_graph_73a6f5dcc780.dpapi'
if ($graphResource.TEST_NEO4J_RESOURCE_ID -ne ('dianzi-' + $reviewRun)) { throw 'resource identity mismatch' }
if ([DateTimeOffset]::Now -ge [DateTimeOffset]::Parse($graphResource.TEST_NEO4J_DEADLINE)) { throw 'resource deadline exhausted' }
if (-not $parentResource.TEST_DATABASE_URL) { throw 'parent test resource missing' }
$startInfo = [Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe'
$startInfo.ArgumentList.Add($reviewRoot + '/reports/runs/r10_default_worker_graph_review1_20261017/run_pg_review.py')
$startInfo.ArgumentList.Add($Phase)
$startInfo.WorkingDirectory = $reviewRoot
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$startInfo.Environment['PYTHONPATH'] = 'D:/dianzi/backend/.venv/Lib/site-packages'
$startInfo.Environment['PYTHONNOUSERSITE'] = '1'
$startInfo.Environment['R10_REVIEW_PARENT_DATABASE_URL'] = $parentResource.TEST_DATABASE_URL
$startInfo.Environment['DIANZI_TEST_RUN_ID'] = $reviewRun
$startInfo.Environment['DIANZI_REVIEW_RESOURCE_AUTHORIZED'] = $reviewRun
foreach ($name in @('URI','USERNAME','PASSWORD','RESOURCE_ID','DEADLINE')) {
    $field = 'TEST_NEO4J_' + $name
    $startInfo.Environment[$field] = [string]$graphResource.$field
}
$process = [Diagnostics.Process]::new()
$process.StartInfo = $startInfo
[void]$process.Start()
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$timedOut = -not $process.WaitForExit(58000)
if ($timedOut) { $process.Kill(); $process.WaitForExit() }
$stdout = $stdoutTask.GetAwaiter().GetResult()
$stderr = $stderrTask.GetAwaiter().GetResult()
foreach ($value in @($parentResource.TEST_DATABASE_URL, $graphResource.TEST_NEO4J_PASSWORD)) {
    if ($value) { $stdout = $stdout.Replace([string]$value, '[REDACTED]'); $stderr = $stderr.Replace([string]$value, '[REDACTED]') }
}
[IO.File]::WriteAllText((Join-Path $receiptRoot ('r10_fresh_' + $Phase + '_attempt' + $Attempt + '_stdout.log')), $stdout)
[IO.File]::WriteAllText((Join-Path $receiptRoot ('r10_fresh_' + $Phase + '_attempt' + $Attempt + '_stderr.log')), $stderr)
$receipt = [ordered]@{phase=$Phase;run_id=$reviewRun;started_at=$started;ended_at=[DateTimeOffset]::Now.ToString('o');exit_code=$process.ExitCode;outer_timeout_seconds=58;outer_timeout=$timedOut;root_environment_injected=$true;private_values_printed=$false;resource_id=$graphResource.TEST_NEO4J_RESOURCE_ID;full_process_peak='recorded_by_independent_controller';source_sha='73634f30f6c3e49d207a955dcc14e7ca94ea7942'}
$receipt | ConvertTo-Json | Set-Content -LiteralPath $receiptPath -Encoding utf8
$parentResource = $null
$graphResource = $null
$stdout = $null
$stderr = $null
$receipt | ConvertTo-Json -Compress
if ($timedOut) { exit 124 }
exit $process.ExitCode
