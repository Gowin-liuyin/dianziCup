"""Read actual process identities without publishing command lines or environment."""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
OPS = Path("D:/dianzi-runtime-cache/r06-f3-ops-20261017")


def main() -> None:
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    guardian = json.loads((OPS / "guardian_start.json").read_bytes())
    launch = json.loads((OPS / "launch_receipt.json").read_bytes())
    source = json.loads((OPS / "source_identity.json").read_bytes())
    known_windows = {
        "guardian": guardian["guardian_pid"],
        "source_launcher": guardian["launcher_pid"],
        "actual_source": source["actual_pid"],
        "guardian_launcher": launch["guardian_launcher_pid"],
        "minio_wsl_launcher": launch["minio_launcher_pid"],
    }
    query = subprocess.Popen(
        ["powershell.exe", "-NoProfile", "-Command", "Get-CimInstance Win32_Process | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = query.communicate(timeout=20)
    if query.returncode:
        raise RuntimeError("Windows identity query failed")
    processes = json.loads(stdout)
    by_pid = {row["ProcessId"]: row for row in processes}
    excluded = {os.getpid(), os.getppid(), query.pid}
    scope = (
        "dianzi-runtime-cache/r06-f3-core-20261017",
        "dianzi-runtime-cache/r06-f3-ops-20261017",
        "r06_nine_script_20261016",
        "r06-product-912-runtime-20261017",
    )
    matches = []
    for row in processes:
        command = (row.get("CommandLine") or "").replace("\\", "/")
        if row["ProcessId"] not in excluded and any(marker in command for marker in scope):
            matches.append({"pid": row["ProcessId"], "parent_pid": row["ParentProcessId"]})
    linux = r'''
import os,json
from pathlib import Path
scope=['r06-f3-ops-20261017/minio_segment.py','r06-f3-ops-20261017/minio_controller.py','ea89c345e404475d94de02cbe67874e3']
excluded={os.getpid(),os.getppid()};found=[]
for root in Path('/proc').iterdir():
 if not root.name.isdigit() or int(root.name) in excluded:continue
 try:command=(root/'cmdline').read_bytes().replace(b'\0',b' ').decode(errors='replace')
 except OSError:continue
 if any(marker in command for marker in scope):found.append({'pid':int(root.name)})
print(json.dumps({'scope_matches':found,'own_probe_excluded':True}))
'''
    wsl = subprocess.Popen(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-B", "-c", linux], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    linux_stdout, linux_stderr = wsl.communicate(timeout=15)
    if wsl.returncode:
        raise RuntimeError("Linux identity query failed")
    result = {
        "started_at": started,
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "known_windows_pids": [{"role": role, "pid": pid, "present": pid in by_pid} for role, pid in known_windows.items()],
        "windows_scope_matches": matches,
        "windows_query_exit": query.returncode,
        "linux_query_exit": wsl.returncode,
        "linux_scope": json.loads(linux_stdout),
        "worker_beat_api_exact_birth": "not recorded before ready; exact per-actor kernel identity cannot be recovered",
        "secret_bearing_fields_published": False,
    }
    (RUN / "process_identity_actual.json").write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
