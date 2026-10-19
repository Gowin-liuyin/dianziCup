param()
$ErrorActionPreference = 'Stop'
$processes = Get-CimInstance Win32_Process
$actors = @($processes | Where-Object {
    $_.Name -eq 'python.exe' -and $_.CommandLine -match 'recovery_r06_live_restart_preparation_20261016|r06_live_8a_20261016|r06-live-e310-operations-20261016|r06-nine-script-operations-20261016|r06_nine_script_20261016|r06-f3-ops-20261017'
})
$listeners = @(Get-NetTCPConnection -State Listen -ErrorAction SilentlyContinue | Where-Object {
    $_.LocalPort -in 28013,29400,25176
})
[ordered]@{
    observed_at = (Get-Date -Format o)
    old_source_actor_count = $actors.Count
    old_source_actors = @($actors | Select-Object ProcessId,ParentProcessId,CreationDate)
    requested_ports_free = ($listeners.Count -eq 0)
    listeners = @($listeners | Select-Object LocalAddress,LocalPort,OwningProcess)
    disks = @(Get-PSDrive C,D | Select-Object Name,Free,Used)
    processes_started = 0
    source_requests = 0
} | ConvertTo-Json -Depth 6
if ($actors.Count -ne 0 -or $listeners.Count -ne 0) {
    throw 'owned source actors or requested ports occupied; no signal sent'
}
