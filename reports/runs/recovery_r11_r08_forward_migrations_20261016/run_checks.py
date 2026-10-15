"""Capture commands and isolate approved PostgreSQL credentials in process memory."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
RUN_ID = "r11_r08_forward_migrations_20261016"


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def execute(label, argv, *, environment=None, cwd=None):
    started = now()
    result = subprocess.run(
        [str(argument) for argument in argv],
        cwd=cwd or ROOT / "backend",
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    for kind, output in (("stdout", result.stdout), ("stderr", result.stderr)):
        if environment and environment.get("TEST_DATABASE_URL"):
            database_url = environment["TEST_DATABASE_URL"]
            output = output.replace(database_url, "[redacted test connection]")
            password = make_url(database_url).password
            if password:
                output = output.replace(password, "[redacted]")
        (RUN / f"{label}.{kind}.log").write_text(output, encoding="utf-8")
    receipt = {
        "label": label,
        "argv": [str(argument) for argument in argv],
        "cwd": str(cwd or ROOT / "backend"),
        "started_at": started,
        "finished_at": now(),
        "exit_code": result.returncode,
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(receipt) + "\n")
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    return result


def approved_test_url():
    captured = subprocess.run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        capture_output=True,
        check=True,
    )
    configured = json.loads(captured.stdout)
    database_url = configured.get("TEST_DATABASE_URL")
    if not isinstance(database_url, str):
        raise RuntimeError("approved test connection field unavailable")
    parsed = make_url(database_url)
    if (
        parsed.host not in {"127.0.0.1", "localhost"}
        or parsed.port != 25432
        or not parsed.database
        or not parsed.database.startswith("test_dianzi_")
        or not parsed.username
        or not parsed.username.startswith("test_")
    ):
        raise RuntimeError("approved test connection isolation rejected")
    return parsed


def create_test_database(parsed, database_name):
    if not database_name.startswith("test_dianzi_" + RUN_ID) or len(database_name) > 63:
        raise RuntimeError("database outside this run")
    engine = create_engine(parsed, isolation_level="AUTOCOMMIT", hide_parameters=True)
    try:
        with engine.connect() as connection:
            if connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database_name}
            ):
                raise RuntimeError("fresh migration proof requires a new database")
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    finally:
        engine.dispose()
    return parsed.set(database=database_name).render_as_string(hide_password=False)


if __name__ == "__main__":
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    label, *arguments = sys.argv[1:]
    if label.startswith("pg_"):
        suffix = os.environ.get("MIGRATION_TEST_SUFFIX", "empty")
        if suffix not in {"empty", "fresh2", "hist1", "hist2"}:
            raise RuntimeError("test suffix outside this run")
        environment["TEST_DATABASE_URL"] = (
            approved_test_url()
            .set(database="test_dianzi_" + RUN_ID + "_" + suffix)
            .render_as_string(hide_password=False)
        )
        environment["DIANZI_ENV"] = "test"
        environment["DIANZI_TEST_RUN_ID"] = RUN_ID + "_" + suffix
    result = execute(label, [PYTHON, *arguments], environment=environment)
    raise SystemExit(result.returncode)
