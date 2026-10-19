"""Capture fixed fix1 checks and operators with actual command exit codes."""

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

OUTPUT = Path(__file__).resolve().parent
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"
WSL = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-B"]
LINUX_OUTPUT = (
    "/mnt/d/dianzi/reports/runs/recovery_r10_owned_neo4j_runtime_fix1_20261016/"
)
COMMANDS = {
    "ruff_check": [PYTHON, "-m", "ruff", "check", "--no-cache", str(OUTPUT)],
    "ruff_format": [PYTHON, "-m", "ruff", "format", "--no-cache", str(OUTPUT)],
    "ruff_format_check": [
        PYTHON,
        "-m",
        "ruff",
        "format",
        "--check",
        "--no-cache",
        str(OUTPUT),
    ],
    "original_guard": WSL + [LINUX_OUTPUT + "test_original_guard.py"],
    "independent_guard": [
        PYTHON,
        "-m",
        "pytest",
        "-q",
        "-o",
        "addopts=",
        "-p",
        "no:cacheprovider",
        str(OUTPUT / "test_independent_guard.py"),
        "--junitxml=" + str(OUTPUT / "independent_guard.xml"),
    ],
    "synthetic_signals": WSL + [LINUX_OUTPUT + "synthetic_signals.py"],
    "prepare_auth": [PYTHON, str(OUTPUT / "prepare_auth.py")],
    "switch_container": WSL + [LINUX_OUTPUT + "switch_container.py"],
    "stop_check": WSL + [LINUX_OUTPUT + "runtime.py", "stop", "--check"],
    "kernel_security": WSL + [LINUX_OUTPUT + "inspect_security.py"],
    "auth_health": [PYTHON, str(OUTPUT / "bolt_smoke.py")],
    "windows_health": [PYTHON, str(OUTPUT / "windows_health.py")],
    "sentinel_create": [PYTHON, str(OUTPUT / "sentinel.py"), "create"],
    "sentinel_recovered": [PYTHON, str(OUTPUT / "sentinel.py"), "verify_delete"],
    "graceful_stop": WSL + [LINUX_OUTPUT + "graceful_probe.py"],
    "logs_scan": [PYTHON, str(OUTPUT / "collect_logs.py")],
    "graceful_validate": [PYTHON, str(OUTPUT / "validate_graceful.py")],
}
parser = argparse.ArgumentParser()
parser.add_argument("name", choices=COMMANDS)
arguments = parser.parse_args()
started = datetime.now(timezone.utc)
timeout = 60 if arguments.name in ("switch_container", "graceful_stop") else 30
result = subprocess.run(
    COMMANDS[arguments.name],
    cwd="D:/dianzi",
    capture_output=True,
    text=True,
    timeout=timeout,
    check=False,
)
(OUTPUT / (arguments.name + ".stdout.log")).write_text(result.stdout)
(OUTPUT / (arguments.name + ".stderr.log")).write_text(result.stderr)
receipt = {
    "command": COMMANDS[arguments.name],
    "started_at": started.isoformat(),
    "ended_at": datetime.now(timezone.utc).isoformat(),
    "cwd": "D:/dianzi",
    "timeout_seconds": timeout,
    "exit_code": result.returncode,
}
(OUTPUT / (arguments.name + ".command.json")).write_text(
    json.dumps(receipt, indent=2) + "\n"
)
print(json.dumps(receipt))
raise SystemExit(result.returncode)
