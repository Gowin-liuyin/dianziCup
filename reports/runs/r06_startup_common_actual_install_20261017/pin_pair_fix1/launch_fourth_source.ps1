$ErrorActionPreference = 'Stop'
$sourceLaunchStarted = [DateTimeOffset]::Now.ToString('o')
$sourceLaunchCode = 0
$sourceErrorType = $null
try {
    & 'D:/dianzi-runtime-cache/r06-f3-ops-20261017/launch.ps1' -Mode start *> 'D:/dianzi/reports/runs/r06_startup_common_actual_install_20261017/pin_pair_fix1/fourth_source_launch.stdout.log'
    if ($LASTEXITCODE -ne 0) { $sourceLaunchCode = $LASTEXITCODE }
} catch {
    $sourceLaunchCode = 1
    $sourceErrorType = $_.Exception.GetType().Name
} finally {
    $sourceReceipt = [ordered]@{
        started_at = $sourceLaunchStarted
        ended_at = [DateTimeOffset]::Now.ToString('o')
        exit_code = $sourceLaunchCode
        error_type = $sourceErrorType
        core_source_sha = 'af63972be5964830216f8f8dd469b8571583c68b'
        operations_source_sha = '6b775e814e0f4d857be56bc99d4323dcb0d68ff3'
        binding_sha256 = 'f6429ab66a5aca152bc91b436e8c662684cd7f3ba0610b8421149bbb0bc4ff6a'
        formal_six_hour_pass = $false
        readiness = 'not_yet_verified'
    }
    $sourceReceipt | ConvertTo-Json | Set-Content -LiteralPath 'D:/dianzi/reports/runs/r06_startup_common_actual_install_20261017/pin_pair_fix1/fourth_source_launch.command.json' -Encoding utf8
    $sourceReceipt | ConvertTo-Json -Compress
}
exit $sourceLaunchCode
