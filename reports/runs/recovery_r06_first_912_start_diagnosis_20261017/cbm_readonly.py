"""One bounded official CBM window over copied public control source only."""

import ctypes
import hashlib
import json
import os
import shutil
import subprocess
import threading
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
SOURCE = RUN / "cbm_source"
ZONE = ZoneInfo("Asia/Shanghai")


class ProcessEntry(ctypes.Structure):
    _fields_ = [("size", wintypes.DWORD), ("usage", wintypes.DWORD), ("pid", wintypes.DWORD), ("heap", ctypes.c_size_t), ("module", wintypes.DWORD), ("threads", wintypes.DWORD), ("parent", wintypes.DWORD), ("priority", wintypes.LONG), ("flags", wintypes.DWORD), ("name", wintypes.WCHAR * 260)]


def windows_scope() -> set[int]:
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.CreateToolhelp32Snapshot.argtypes = [wintypes.DWORD, wintypes.DWORD]
    kernel.CreateToolhelp32Snapshot.restype = wintypes.HANDLE
    kernel.Process32FirstW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.Process32NextW.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessEntry)]
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateToolhelp32Snapshot(2, 0)
    if handle == ctypes.c_void_p(-1).value:
        raise OSError("process snapshot failed")
    entry = ProcessEntry()
    entry.size = ctypes.sizeof(entry)
    parents = {}
    try:
        more = kernel.Process32FirstW(handle, ctypes.byref(entry))
        while more:
            parents[int(entry.pid)] = int(entry.parent)
            more = kernel.Process32NextW(handle, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(handle)
    result = {os.getpid(), os.getppid()}
    while True:
        expanded = result | {pid for pid, parent in parents.items() if parent in result}
        if expanded == result:
            return result
        result = expanded


def main() -> None:
    for directory in ("core", "ops"):
        target = SOURCE / directory
        target.mkdir(parents=True, exist_ok=False)
        root = Path(f"D:/dianzi-runtime-cache/r06-f3-{directory}-20261017")
        for path in root.glob("*.py"):
            shutil.copyfile(path, target / path.name)
        if directory == "ops":
            for name in ("launch.ps1", "windows_preflight.ps1"):
                shutil.copyfile(root / name, target / name)
    wsl_source = "/mnt/d/dianzi/reports/runs/recovery_r06_first_912_start_diagnosis_20261017/cbm_source"
    linux = r'''
import os,json,time,subprocess,threading
from pathlib import Path
root=os.getpid()
def scope():
 parents={}
 for item in Path('/proc').iterdir():
  if item.name.isdigit():
   try:
    value=(item/'stat').read_text(); tail=value[value.rfind(')')+2:].split(); parents[int(item.name)]=int(tail[1])
   except (OSError,ValueError,IndexError): pass
 found={root}
 while True:
  next_found=found|{pid for pid,parent in parents.items() if parent in found}
  if found==next_found:return found
  found=next_found
stop=threading.Event(); peaks=[]
def sample():
 while not stop.wait(.05):peaks.append(len(scope()))
thread=threading.Thread(target=sample);thread.start()
base=['/usr/bin/env','CBM_CACHE_DIR=/tmp/r06-first-912-start-diagnosis-20261017','/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp']
commands=[('index',['cli','--json','index_repository','--repo-path',os.environ['R06_DIAG_SOURCE'],'--name','r06_first_912_start_diagnosis','--mode','fast','--persistence','false']),('schema',['cli','--json','get_graph_schema','--project','r06_first_912_start_diagnosis','--format','json']),('calls',['cli','--json','query_graph','--project','r06_first_912_start_diagnosis','--query',"MATCH (n:Function) WHERE n.name IN ['main', 'verify_live_binding', 'load_owned_application', 'install_owned_stop_watcher'] RETURN n LIMIT 20"])]
started=time.monotonic();rows=[]
for label,args in commands:
 remaining=48-(time.monotonic()-started)
 if remaining<=0:break
 clock=time.monotonic()
 try:
  value=subprocess.run(base+args,capture_output=True,timeout=min(14,remaining),check=False)
  row={'label':label,'exit_code':value.returncode,'stdout':value.stdout.decode(errors='replace'),'stderr':value.stderr.decode(errors='replace'),'seconds':round(time.monotonic()-clock,6)}
 except subprocess.TimeoutExpired as exc:row={'label':label,'exit_code':124,'stdout':(exc.stdout or b'').decode(errors='replace'),'stderr':(exc.stderr or b'').decode(errors='replace'),'seconds':round(time.monotonic()-clock,6)}
 rows.append(row)
stop.set();thread.join();print(json.dumps({'rows':rows,'linux_scope_peak':max(peaks,default=1),'linux_descendants_after':len(scope()-{root}),'wall_seconds':round(time.monotonic()-started,6)}))
'''
    argv = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "/usr/bin/env", "R06_DIAG_SOURCE=" + wsl_source, "python3", "-B", "-c", linux]
    started = datetime.now(ZONE).isoformat()
    clock = time.monotonic()
    peak = []
    stop = threading.Event()

    def sample() -> None:
        while not stop.wait(0.05):
            peak.append(len(windows_scope()))

    thread = threading.Thread(target=sample)
    thread.start()
    process = subprocess.Popen(argv, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    stdout, stderr = process.communicate(timeout=55)
    stop.set()
    thread.join()
    result = json.loads(stdout)
    for row in result["rows"]:
        for stream in ("stdout", "stderr"):
            raw = row.pop(stream).encode()
            (RUN / f"cbm_{row['label']}.{stream}.log").write_bytes(raw)
            row[stream + "_sha256"] = hashlib.sha256(raw).hexdigest()
    result.update({"started_at": started, "ended_at": datetime.now(ZONE).isoformat(), "windows_wrapper_exit_code": process.returncode, "windows_scope_peak": max(peak, default=2), "windows_scope_after": sorted(windows_scope()), "windows_launch_pid": process.pid, "windows_launch_wait_ack": process.poll() is not None, "wsl_wrapper_stderr_sha256": hashlib.sha256(stderr).hexdigest(), "wall_seconds": round(time.monotonic()-clock,6), "source_scope": "copied installed 11 CORE + 9 OPS public sources only; no JSON/log/environment/holdout"})
    result["full_windows_plus_linux_peak_upper_bound"] = result["windows_scope_peak"] + result["linux_scope_peak"]
    (RUN / "cbm_actual.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"commands": result["rows"], "windows_scope_peak": result["windows_scope_peak"], "linux_scope_peak": result["linux_scope_peak"], "full_peak_upper_bound": result["full_windows_plus_linux_peak_upper_bound"], "linux_descendants_after": result["linux_descendants_after"], "windows_wait_ack": result["windows_launch_wait_ack"], "exit_code": process.returncode, "wall_seconds": result["wall_seconds"]}))


if __name__ == "__main__":
    main()
