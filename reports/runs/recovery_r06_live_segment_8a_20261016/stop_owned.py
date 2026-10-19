"""Check exact creation time and command before requesting this supervisor to stop."""

import argparse
import json
import subprocess
from pathlib import Path

RUN = Path(__file__).resolve().parent
parser = argparse.ArgumentParser()
parser.add_argument("--check", action="store_true")
check_only = parser.parse_args().check
start = json.loads((RUN / "runtime_start.json").read_text())
expected = start["supervisor"]
query = "$p=Get-CimInstance Win32_Process -Filter 'ProcessId=" + str(expected["pid"]) + "'; if (-not $p) { exit 1 }; [ordered]@{pid=$p.ProcessId;creation_time=$p.CreationDate.ToUniversalTime().ToString('o');parent_pid=$p.ParentProcessId;executable=$p.ExecutablePath;command=$p.CommandLine} | ConvertTo-Json -Compress"
actual = json.loads(subprocess.check_output(["powershell.exe", "-NoProfile", "-Command", query], text=True))
assert actual == expected
assert str(RUN / "supervise.py").replace("\\", "/") in actual["command"].replace("\\", "/")
assert not (RUN / "runtime_end.json").exists()
if not check_only:
    (RUN / "stop.request").write_text("owned supervisor identity checked\n")
print(json.dumps({"operation": "identity_checked" if check_only else "owned_stop_requested", "supervisor_pid": expected["pid"], "creation_time": expected["creation_time"], "signals_sent": 0}))
