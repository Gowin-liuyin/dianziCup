"""Run checks with a private, dedicated PostgreSQL database and redact credentials."""

import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
RUN_ID = "r06_catalog_bulk_20261016"
PYTHON = "D:/dianzi/backend/.venv/Scripts/python.exe"


def private_environment():
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
         "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, text=True, check=True,
    )
    private = json.loads(result.stdout)
    url = make_url(private["TEST_DATABASE_URL"])
    assert url.port == 25432
    database_name = "test_dianzi_" + RUN_ID
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        exists = connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database_name}
        )
        if not exists:
            connection.execute(text('CREATE DATABASE "' + database_name + '"'))
    admin.dispose()
    dedicated = url.set(database=database_name).render_as_string(hide_password=False)
    environment = dict(os.environ)
    environment.update(
        TEST_DATABASE_URL=dedicated,
        DIANZI_TEST_RUN_ID=RUN_ID,
        PYTHONPATH=str(ROOT / "backend/src"),
    )
    return environment, (dedicated, url.password or "", private["TEST_DATABASE_URL"])


def main():
    label, *arguments = sys.argv[1:]
    environment, secrets = private_environment()
    command = [PYTHON, *arguments]
    started_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    start = time.perf_counter()
    process = subprocess.Popen(
        [PYTHON, str(RUN / "measure_cpu.py"), *arguments], cwd=ROOT / "backend", env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
    )
    stdout, stderr = process.communicate(timeout=240)
    measurements = re.findall(r"CPU_RECEIPT=(\{[^\n]+\})", stdout)
    cpu_seconds = json.loads(measurements[-1])["cpu_seconds"] if measurements else None
    output = stdout + stderr
    for secret in secrets:
        if secret:
            output = output.replace(secret, "[redacted test connection]")
    (RUN / (label + ".log")).write_text(output, encoding="utf-8")
    receipt = {
        "command": command, "cwd": str(ROOT / "backend"),
        "started_at": started_at,
        "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
        "wall_seconds": time.perf_counter() - start, "cpu_seconds": cpu_seconds,
        "exit_code": process.returncode,
        "database": "test_dianzi_" + RUN_ID, "postgres_port": 25432,
        "log": label + ".log",
        "summary": re.findall(r"[^\n]*(?:passed|failed|error|skipped)[^\n]*", output)[-8:],
    }
    (RUN / (label + ".command.json")).write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, ensure_ascii=False))
    sys.exit(process.returncode)


if __name__ == "__main__":
    main()
