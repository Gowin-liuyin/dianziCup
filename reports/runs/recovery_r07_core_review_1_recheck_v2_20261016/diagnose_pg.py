"""Observe only loopback reachability and local runtime state without printing credentials."""

import json
import socket
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
private = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"], capture_output=True, check=True)
parsed = urlsplit(json.loads(private.stdout)["TEST_DATABASE_URL"])
assert parsed.hostname in {"127.0.0.1", "localhost"}
checks = []
for host in (parsed.hostname, "127.0.0.1"):
    try:
        with socket.create_connection((host, parsed.port), timeout=5):
            checks.append({"loopback_only": True, "reachable": True})
    except OSError as error:
        checks.append({"loopback_only": True, "reachable": False, "error_type": type(error).__name__})
runtime = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "docker", "ps", "--format", "{{.Names}} {{.Status}}"], capture_output=True, timeout=30)
result = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "socket_checks": checks, "runtime_exit": runtime.returncode, "runtime_state": runtime.stdout.decode(errors="replace"), "runtime_error": runtime.stderr.decode(errors="replace"), "connection_values_recorded": False, "first_pg_attempt": {"exit_code": 1, "phase": "bootstrap before pytest", "error_type": "sqlalchemy.exc.OperationalError", "cause": "psycopg.errors.ConnectionTimeout", "detail": "connection timeout expired", "initial_wall_clock": "not captured in file; tool output retained in chat", "tests_executed": 0}}
(RUN / "pg_environment_diagnosis.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
print(json.dumps({"socket_checks": checks, "runtime_exit": runtime.returncode}))
