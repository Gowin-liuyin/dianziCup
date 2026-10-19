$ErrorActionPreference = 'Stop'
$pointer = [IntPtr]::Zero
try {
  $secure = ConvertTo-SecureString ([IO.File]::ReadAllText('D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi'))
  $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
  $resource = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer) | ConvertFrom-Json -DateKind String
} finally {
  if ($pointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer) }
}
$env:R06_PHASE_PARENT_DATABASE_URL = $resource.TEST_DATABASE_URL
$env:R06_PHASE_PARENT_REDIS_URL = $resource.TEST_REDIS_URL
try {
 & 'C:/Users/yinha/AppData/Roaming/uv/python/cpython-3.12-windows-x86_64-none/python.exe' -B 'D:/dianzi/reports/runs/r06_root_native_control_install_20261017/run_owned_audit.py' actual_startup_common_pair_resources 'D:/dianzi/reports/runs/r06_startup_common_actual_install_20261017/pin_pair_fix1/probe_authorized_resources.py'
 $code = $LASTEXITCODE
} finally {
 [Environment]::SetEnvironmentVariable('R06_PHASE_PARENT_DATABASE_URL', $null, 'Process')
 [Environment]::SetEnvironmentVariable('R06_PHASE_PARENT_REDIS_URL', $null, 'Process')
 $resource = $null
}
exit $code
