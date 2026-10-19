"""Capture review commands and keep approved test credentials in memory only."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = ROOT / "backend/.venv/Scripts/python.exe"
RUN_ID = "r11r08_review1_20261016"
DATABASE_PREFIX = "test_dianzi_" + RUN_ID


def now():
    return datetime.now(timezone(timedelta(hours=8))).isoformat()


def approved_test_url():
    from sqlalchemy.engine import make_url

    capture = subprocess.run(
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
    parsed = make_url(json.loads(capture.stdout)["TEST_DATABASE_URL"])
    if not (
        parsed.host in {"127.0.0.1", "localhost"}
        and parsed.port == 25432
        and parsed.database.startswith("test_dianzi_")
        and parsed.username.startswith("test_")
    ):
        raise RuntimeError("approved test service isolation rejected")
    return parsed


def create_database(suffix):
    from sqlalchemy import create_engine, text

    name = DATABASE_PREFIX + "_" + suffix
    if not suffix.isalnum() or len(name) > 63:
        raise RuntimeError("invalid owned database suffix")
    parsed = approved_test_url()
    engine = create_engine(parsed, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with engine.connect() as connection:
        exists = connection.scalar(
            text("SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"),
            {"name": name},
        )
        if exists:
            raise RuntimeError("new independent database already exists")
        connection.exec_driver_sql(f'CREATE DATABASE "{name}"')
    engine.dispose()
    return parsed.set(database=name)


def execute(label, argv, *, environment=None, cwd=None):
    started = now()
    result = subprocess.run(
        [str(item) for item in argv],
        cwd=cwd or ROOT / "backend",
        env=environment,
        capture_output=True,
        check=False,
    )
    for kind, output in (("stdout", result.stdout), ("stderr", result.stderr)):
        for name in ("TEST_DATABASE_URL",):
            if environment and environment.get(name):
                from sqlalchemy.engine import make_url

                raw_url = environment[name]
                output = output.replace(raw_url.encode(), b"[redacted test DSN]")
                password = make_url(raw_url).password
                if password:
                    output = output.replace(password.encode(), b"[redacted]")
        (RUN / f"{label}.{kind}.log").write_bytes(output)
    receipt = {
        "label": label,
        "argv": [str(item) for item in argv],
        "cwd": str(cwd or ROOT / "backend"),
        "started_at": started,
        "finished_at": now(),
        "exit_code": result.returncode,
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8", newline="\n") as stream:
        stream.write(json.dumps(receipt) + "\n")
    print(json.dumps(receipt), flush=True)
    return result


if __name__ == "__main__":
    label, mode, *arguments = sys.argv[1:]
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    if mode == "pg":
        environment["TEST_DATABASE_URL"] = (
            approved_test_url()
            .set(database=DATABASE_PREFIX + "_fresh")
            .render_as_string(hide_password=False)
        )
        environment["DIANZI_ENV"] = "test"
        environment["DIANZI_TEST_RUN_ID"] = RUN_ID + "_fresh"
        argv = [PYTHON, *arguments]
    elif mode == "python":
        argv = [PYTHON, *arguments]
    else:
        argv = [mode, *arguments]
    raise SystemExit(execute(label, argv, environment=environment).returncode)
