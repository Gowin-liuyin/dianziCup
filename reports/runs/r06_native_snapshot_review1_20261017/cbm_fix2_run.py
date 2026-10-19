"""Use the mature full-guest supervisor for the single authorized source-only CLI window."""

import sys
from pathlib import Path

import cbm_fix2_windows_supervise as checks

RUN = Path(__file__).resolve().parent
command = ["C:/Windows/System32/wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-B",
           "/mnt/d/wt/r06-native-review1/codex/r06-native-review1/reports/runs/r06_native_snapshot_review1_20261017/cbm_fix2_linux_tools.py"]
raise SystemExit(checks.execute("cbm_resource_recheck", command, timeout=45, process_cap=16))
