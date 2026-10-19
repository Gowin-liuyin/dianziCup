$ErrorActionPreference = 'Stop'
$scanSecretPaths = @(
    'C:/Users/yinha/.codex/secrets/dianzi/01a13a70-858c-7d92-8070-0b2693ad7fc4.dpapi',
    'C:/Users/yinha/.codex/secrets/dianzi/fofa_relay_20261015.dpapi',
    'C:/Users/yinha/.codex/secrets/dianzi/r01_runtime_20261015.dpapi',
    'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi',
    'D:/dianzi-private/r14-generation-live-20261016.dpapi',
    'D:/dianzi-private/revalidation-cursor-key-20261016.dpapi'
)
$scanValues = [System.Collections.Generic.HashSet[string]]::new()
$scanLoadMetadata = [System.Collections.Generic.List[object]]::new()
function Add-PrivateScanValue($node, [string]$fieldName) {
    if ($null -eq $node) { return }
    if ($node -is [string]) {
        if ($node.Length -ge 8 -and $fieldName -match '(?i)(pass(word)?|api.?key|access.?key|(^|_)secret($|_)|(^|_)token$|database_url)' -and $fieldName -notmatch '(?i)(ref|path|hash|digest|budget|count|model|base_url)') {
            [void]$scanValues.Add($node)
        }
        return
    }
    if ($node -is [System.Collections.IDictionary]) {
        foreach ($key in $node.Keys) { Add-PrivateScanValue $node[$key] ([string]$key) }
        return
    }
    if ($node -is [System.Collections.IEnumerable]) {
        foreach ($item in $node) { Add-PrivateScanValue $item $fieldName }
        return
    }
    foreach ($property in $node.PSObject.Properties) { Add-PrivateScanValue $property.Value $property.Name }
}
foreach ($scanSecretPath in $scanSecretPaths) {
    $pointer = [IntPtr]::Zero
    try {
        $protectedText = [System.IO.File]::ReadAllText($scanSecretPath)
        $secured = ConvertTo-SecureString -String $protectedText
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secured)
        $decoded = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        $document = $decoded | ConvertFrom-Json
        Add-PrivateScanValue $document ''
        $scanLoadMetadata.Add([ordered]@{path=$scanSecretPath;loaded=$true})
    } catch {
        $scanLoadMetadata.Add([ordered]@{path=$scanSecretPath;loaded=$false;error_type=$_.Exception.GetType().Name})
    } finally {
        if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
        $decoded = $null
        $document = $null
    }
}
$runPath = 'D:/dianzi/reports/runs/recovery_reviewed_integration_20261016'
$scanLoadMetadata | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath ($runPath + '/known_secret_load_metadata.json') -Encoding utf8
if ($scanValues.Count -eq 0) { throw 'No authorized values could be loaded; no success claimed' }
$startInfo = [System.Diagnostics.ProcessStartInfo]::new()
$startInfo.FileName = 'D:/dianzi/backend/.venv/Scripts/python.exe'
$startInfo.ArgumentList.Add($runPath + '/check_known_secret_values.py')
$startInfo.WorkingDirectory = 'D:/dianzi'
$startInfo.UseShellExecute = $false
$startInfo.CreateNoWindow = $true
$startInfo.RedirectStandardOutput = $true
$startInfo.RedirectStandardError = $true
$valueArray = @($scanValues | ForEach-Object { $_ })
$startInfo.Environment['DIANZI_PRIVATE_SCAN_VALUES_JSON'] = ConvertTo-Json -InputObject $valueArray -Compress
$scanProcess = [System.Diagnostics.Process]::Start($startInfo)
$startInfo.Environment.Remove('DIANZI_PRIVATE_SCAN_VALUES_JSON') | Out-Null
$valueArray = $null
$scanValues.Clear()
$stdoutTask = $scanProcess.StandardOutput.ReadToEndAsync()
$stderrTask = $scanProcess.StandardError.ReadToEndAsync()
if (-not $scanProcess.WaitForExit(180000)) {
    $scanProcess.Kill($true)
    $scanProcess.WaitForExit()
    throw 'Owned exact-value scan exceeded 180 seconds'
}
$stdout = $stdoutTask.GetAwaiter().GetResult()
$stderr = $stderrTask.GetAwaiter().GetResult()
[System.IO.File]::WriteAllText($runPath + '/known_secret_scan.log', $stdout + $stderr, [System.Text.UTF8Encoding]::new($false))
Write-Output $stdout
exit $scanProcess.ExitCode
