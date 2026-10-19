param(
    [Parameter(Mandatory)][string]$Packet,
    [Parameter(Mandatory)][ValidateSet('qa_reader_closed_pairs_pg_1', 'qa_reader_closed_pairs_pg_2', 'qa_reader_closed_pairs_pg_3', 'qa_reader_closed_pairs_pg_4', 'qa_reader_closed_pairs_pg_5', 'qa_reader_closed_pairs_pg_6', 'qa_reader_closed_pairs_pg_7', 'pg_policy_original4', 'pg_history_original13')][string]$Group
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$bindingsPath = $PSScriptRoot + '/launch_bindings.json'
if ((Get-FileHash -LiteralPath $bindingsPath).Hash.ToLowerInvariant() -ne '852217ca0703f76fbe01f8a69799bbc51d2428a20ca54129883f726582142d9a') {
    throw 'frozen launch mapping changed'
}
$bindings = Get-Content -LiteralPath $bindingsPath -Raw | ConvertFrom-Json -DateKind String
if ($bindings.schema_version -ne 'root-pg-packets-preparation-1' -or
    $bindings.deadline.controller_seconds -ne 58 -or $bindings.deadline.child_cutoff_seconds -ne 48 -or
    $bindings.deadline.root_outer_seconds -ne 60 -or $bindings.resource_caps.target -ne 2 -or
    $bindings.resource_caps.sampler -ne 1 -or $bindings.resource_caps.process_memory -ne 536870912 -or
    $bindings.resource_caps.job_memory -ne 1073741824 -or $bindings.resource_caps.cpu_cores -ne 2 -or
    $bindings.resource_caps.native_process -ne 9 -or $bindings.resource_caps.full_windows -ne 10 -or
    (@($bindings.source_oids_identity_only) -join ',') -ne '10451302,10434264') {
    throw 'launch mapping schema or fixed budget mismatch'
}
$packetPath = (Resolve-Path -LiteralPath $Packet).Path
$matches = @($bindings.packets | Where-Object { [IO.Path]::GetFullPath($_.packet_path) -eq $packetPath })
if ($matches.Count -ne 1) { throw 'packet path not in frozen whitelist' }
$binding = $matches[0]
if ($null -eq $binding.groups.PSObject.Properties[$Group]) { throw 'group not allowed for this packet' }
foreach ($file in $binding.frozen_files) {
    $actual = Get-Item -LiteralPath $file.path
    if ($actual.Length -ne $file.bytes -or
        (($actual.LastWriteTimeUtc.Ticks - 621355968000000000) * [decimal]100).ToString() -ne $file.mtime_ns -or
        (Get-FileHash -LiteralPath $file.path).Hash.ToLowerInvariant() -ne $file.raw_sha256) {
        throw ('frozen input changed: ' + $file.path)
    }
}
$packetDocument = Get-Content -LiteralPath $packetPath -Raw | ConvertFrom-Json -DateKind String
$admission = Get-Content -LiteralPath $binding.admission_path -Raw | ConvertFrom-Json -DateKind String
if ($packetDocument.source_sha -ne $binding.source_sha -or $admission.source_sha -ne $binding.source_sha -or
    [IO.Path]::GetFullPath($packetDocument.controller_path) -ne [IO.Path]::GetFullPath($binding.controller_path) -or
    [IO.Path]::GetFullPath($packetDocument.admission_path) -ne [IO.Path]::GetFullPath($binding.admission_path) -or
    $packetDocument.root_required_environment.DIANZI_REVIEW_RESOURCE_AUTHORIZED -ne $binding.authority_header -or
    $Group -notin $packetDocument.allowed_labels -or
    $null -eq $admission.entry_raw_sha256.PSObject.Properties['run_pg_review.py'] -or
    $null -eq $admission.entry_raw_sha256.PSObject.Properties['worker_entry.py'] -or
    $admission.entry_raw_sha256.PSObject.Properties['run_pg_review.py'].Value -ne $packetDocument.controller_raw_sha256) {
    throw 'packet or admission content schema mismatch'
}
$receiptPath = $PSScriptRoot + ('/root_launch_' + $Group + '_launch.json')
$stdoutPath = $PSScriptRoot + ('/root_launch_' + $Group + '_stdout.log')
$stderrPath = $PSScriptRoot + ('/root_launch_' + $Group + '_stderr.log')
foreach ($path in @($receiptPath, $stdoutPath, $stderrPath, ($binding.support_root + '/' + $Group + '.command.json'))) {
    if (Test-Path -LiteralPath $path) { throw 'refusing execution evidence overwrite' }
}
$started = [DateTimeOffset]::Now.ToString('o')
$deadline = [DateTimeOffset]::UtcNow.AddSeconds(600)
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
$info.WorkingDirectory = $binding.source_root
$info.UseShellExecute = $false
$info.CreateNoWindow = $true
$info.RedirectStandardOutput = $true
$info.RedirectStandardError = $true
$info.Environment.Clear()
$info.Environment['SystemRoot'] = 'C:/Windows'
$info.Environment['WINDIR'] = 'C:/Windows'
$info.Environment['PATH'] = 'C:/Windows/System32'
$info.Environment['TEMP'] = $PSScriptRoot
$info.Environment['TMP'] = $PSScriptRoot
$info.Environment['PYTHONPATH'] = 'D:/dianzi/backend/.venv/Lib/site-packages;' + $binding.support_root
$info.Environment['PYTHONNOUSERSITE'] = '1'
$info.Environment['PYTHONDONTWRITEBYTECODE'] = '1'
$info.Environment['PYTHONIOENCODING'] = 'utf-8'
$info.Environment['R18_REVIEW_PARENT_DATABASE_URL'] = $parentResource.TEST_DATABASE_URL
$info.Environment['DIANZI_REVIEW_RESOURCE_AUTHORIZED'] = $binding.authority_header
$info.Environment['R18_REVIEW_BATCH_ALLOWLIST'] = ConvertTo-Json -Compress -InputObject @($Group)
$info.Environment['R18_REVIEW_AUTHORIZED_UNTIL_UTC'] = $deadline.ToString('o')
$info.ArgumentList.Add($binding.entry_path)
$info.ArgumentList.Add('run_pg_review')
$info.ArgumentList.Add($Group)
$process = [Diagnostics.Process]::new()
$process.StartInfo = $info
[void]$process.Start()
$stdoutTask = $process.StandardOutput.ReadToEndAsync()
$stderrTask = $process.StandardError.ReadToEndAsync()
$timedOut = -not $process.WaitForExit(60000)
if ($timedOut) { $process.Kill($true); $process.WaitForExit() }
$stdoutText = $stdoutTask.GetAwaiter().GetResult().Replace([string]$parentResource.TEST_DATABASE_URL, '[REDACTED]')
$stderrText = $stderrTask.GetAwaiter().GetResult().Replace([string]$parentResource.TEST_DATABASE_URL, '[REDACTED]')
[IO.File]::WriteAllText($stdoutPath, $stdoutText)
[IO.File]::WriteAllText($stderrPath, $stderrText)
$receipt = [ordered]@{
    packet = $packetPath; group = $Group; source_sha = $binding.source_sha
    expected_cases = $binding.groups.PSObject.Properties[$Group].Value
    started_at = $started; ended_at = [DateTimeOffset]::Now.ToString('o')
    exit_code = $process.ExitCode; timeout_seconds = 60; outer_timeout = $timedOut
    authorized_until_utc = $deadline.ToString('o'); root_environment_injected = $true
    secret_values_printed = $false; resource_caps = $bindings.resource_caps
    full_process_peak = 'independent native controller receipt'
    pg_connection_cap_claim = 'sample peak only when actual parent role is superuser'
}
$receipt | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $receiptPath -Encoding utf8
$parentResource = $null
$info.Environment.Remove('R18_REVIEW_PARENT_DATABASE_URL') | Out-Null
$stdoutText = $null
$stderrText = $null
$receipt | ConvertTo-Json -Compress -Depth 5
if ($timedOut) { exit 124 }
exit $process.ExitCode
