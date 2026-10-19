"""Read back Job settings and vary only the launch phase, within four attempts."""

import json
import time

import probe_native_cpu as probe


SETTINGS = """import json,os,ctypes
from ctypes import wintypes
kernel=ctypes.WinDLL('kernel32',use_last_error=True)
kernel.QueryInformationJobObject.argtypes=[wintypes.HANDLE,ctypes.c_int,ctypes.c_void_p,wintypes.DWORD,ctypes.c_void_p]
extended=ctypes.create_string_buffer(144)
action=wintypes.DWORD()
settings_ok=kernel.QueryInformationJobObject(handle,9,extended,144,None)
action_ok=kernel.QueryInformationJobObject(handle,6,ctypes.byref(action),4,None)
print('LIMIT_APPLIED',flush=True)
print('DIAG '+json.dumps({'pid':os.getpid(),'job_handle':handle,'query_ok':settings_ok,'process_time_100ns':ctypes.c_longlong.from_buffer(extended,0).value,'flags':ctypes.c_ulong.from_buffer(extended,16).value,'memory_bytes':ctypes.c_size_t.from_buffer(extended,112).value,'end_action_ok':action_ok,'end_action':action.value}),flush=True)"""
probe.INSTRUMENTED = probe.EXACT.replace("print('LIMIT_APPLIED',flush=True)", SETTINGS)
started = time.perf_counter()
results = [probe.attempt(13, "settings")]
for number, delay in ((14, 5.9), (15, 6.0), (16, 6.1)):
    time.sleep(delay)
    result = probe.attempt(number, "settings_phase")
    result["prelaunch_delay_seconds"] = delay
    (probe.OUTPUT / f"attempt_{number:02d}_settings_phase.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    results.append(result)
summary = {"attempts": 4, "wall_seconds": time.perf_counter() - started, "timeouts": sum(result["outcome"] == "timeout" for result in results), "results": [{key: result.get(key) for key in ("attempt", "mode", "outcome", "prelaunch_delay_seconds", "wall_seconds", "returncode", "child_metadata", "final_job")} for result in results]}
(probe.OUTPUT / "phase_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
print(json.dumps(summary), flush=True)
