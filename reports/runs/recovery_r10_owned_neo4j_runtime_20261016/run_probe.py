"""Capture the fixed owned-resource checks with actual command exit codes."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"
WSL = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-B"]
RUNTIME = (
    "/mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_20261016/runtime.py"
)
COMMANDS = {
    "ruff_check": [PYTHON, "-m", "ruff", "check", str(OUTPUT)],
    "ruff_format": [PYTHON, "-m", "ruff", "format", str(OUTPUT)],
    "ruff_format_check": [PYTHON, "-m", "ruff", "format", "--check", str(OUTPUT)],
    "guard_unit": WSL + [RUNTIME.replace("runtime.py", "test_runtime_guard.py")],
    "image_verify": WSL + [RUNTIME, "verify_image"],
    "health_snapshot": WSL + [RUNTIME, "snapshot"],
    "stop_check": WSL + [RUNTIME, "stop", "--check"],
    "kernel_security": WSL + [RUNTIME.replace("runtime.py", "inspect_security.py")],
    "windows_health": [PYTHON, str(OUTPUT / "windows_health.py")],
    "bolt_authentication": [PYTHON, str(OUTPUT / "bolt_smoke.py")],
}
parser = argparse.ArgumentParser()
parser.add_argument("name", choices=COMMANDS)
arguments = parser.parse_args()
started = datetime.now(timezone.utc)
result = subprocess.run(
    COMMANDS[arguments.name],
    cwd="D:/dianzi",
    capture_output=True,
    text=True,
    timeout=30,
    check=False,
)
(OUTPUT / (arguments.name + ".stdout.log")).write_text(result.stdout)
(OUTPUT / (arguments.name + ".stderr.log")).write_text(result.stderr)
receipt = {
    "command": COMMANDS[arguments.name],
    "started_at": started.isoformat(),
    "ended_at": datetime.now(timezone.utc).isoformat(),
    "cwd": "D:/dianzi",
    "timeout_seconds": 30,
    "exit_code": result.returncode,
}
(OUTPUT / (arguments.name + ".command.json")).write_text(
    json.dumps(receipt, indent=2) + "\n"
)
print(json.dumps(receipt))
raise SystemExit(result.returncode)
