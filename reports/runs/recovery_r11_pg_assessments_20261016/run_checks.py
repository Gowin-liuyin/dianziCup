"""Bounded local checks; credentials stay in memory/environment and out of argv/logs."""

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path("D:/dianzi/backend/.venv/Scripts/python.exe")
DATABASE = "test_dianzi_r11_assessment_20261016"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def connection():
    result = subprocess.run(
        [
            "wsl",
            "-u",
            "root",
            "-e",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        capture_output=True,
        check=True,
        timeout=15,
    )
    configuration = json.loads(result.stdout)
    return make_url(configuration["TEST_DATABASE_URL"])


def prepare():
    url = connection()
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
    admin = create_engine(
        url.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True
    )
    with admin.connect() as database_connection:
        if (
            database_connection.scalar(
                text("SELECT 1 FROM pg_database WHERE datname=:database"),
                {"database": DATABASE},
            )
            is None
        ):
            database_connection.exec_driver_sql(f'CREATE DATABASE "{DATABASE}"')
    admin.dispose()
    schema = "r11_assessment_" + uuid4().hex
    database_url = url.set(database=DATABASE)
    engine = create_engine(database_url, hide_parameters=True)
    with engine.begin() as database_connection:
        database_connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    engine.dispose()
    scoped_url = database_url.update_query_dict({"options": f"-csearch_path={schema}"})
    sys.path.insert(0, str(ROOT / "backend/src"))
    from ai_intel.assessment.assessment_persistence import ASSESSMENT_TABLES
    from ai_intel.assessment.rule_persistence import RULE_TABLES
    from ai_intel.infrastructure.database import run_migrations

    started = now()
    run_migrations(
        scoped_url.render_as_string(hide_password=False), "0019_aggregate_observations"
    )
    engine = create_engine(scoped_url, hide_parameters=True)
    with engine.begin() as database_connection:
        for table in (*RULE_TABLES, *ASSESSMENT_TABLES):
            table.create(database_connection)
    with engine.connect() as database_connection:
        migration = database_connection.scalar(
            text("SELECT version_num FROM alembic_version")
        )
        table_count = database_connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.tables WHERE table_schema=:schema"
            ),
            {"schema": schema},
        )
    engine.dispose()
    current_receipt = RUN / "database_receipt.json"
    if current_receipt.exists():
        prior_count = len(list(RUN.glob("database_receipt_prior_*.json")))
        (RUN / f"database_receipt_prior_{prior_count + 1:02d}.json").write_bytes(
            current_receipt.read_bytes()
        )
    current_receipt.write_text(
        json.dumps(
            {
                "database": DATABASE,
                "schema": schema,
                "migration": migration,
                "new_local_tables": [
                    table.name for table in (*RULE_TABLES, *ASSESSMENT_TABLES)
                ],
                "table_count": table_count,
                "started_at": started,
                "finished_at": now(),
                "production_0021": "not_run",
                "forward_only": True,
                "fixture_data": True,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    print(
        "Dedicated database and random schema forward to 0019; six local tables created."
    )


def run(label, arguments):
    receipt = json.loads((RUN / "database_receipt.json").read_text())
    url = (
        connection()
        .set(database=DATABASE)
        .update_query_dict(
            {
                "options": "-csearch_path="
                + receipt["schema"]
                + " -cstatement_timeout=15000 -clock_timeout=5000"
            }
        )
    )
    environment = os.environ.copy()
    environment["TEST_DATABASE_URL"] = url.render_as_string(hide_password=False)
    environment["DIANZI_TEST_RUN_ID"] = "r11_assessment_20261016"
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    command = [str(PYTHON), *arguments]
    started_at, started = now(), time.monotonic()
    result = subprocess.run(
        command,
        cwd=ROOT / "backend",
        env=environment,
        capture_output=True,
        timeout=240,
        check=False,
    )
    for stream, value in (("stdout", result.stdout), ("stderr", result.stderr)):
        output = value.decode("utf-8", errors="replace")
        for secret in (environment["TEST_DATABASE_URL"], url.password or ""):
            if secret:
                output = output.replace(secret, "[redacted]")
        (RUN / f"{label}.{stream}.log").write_text(output, encoding="utf-8")
    record = {
        "label": label,
        "command": command,
        "cwd": str(ROOT / "backend"),
        "started_at": started_at,
        "finished_at": now(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "exit_code": result.returncode,
    }
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as log:
        log.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False))
    print((RUN / f"{label}.stdout.log").read_text(encoding="utf-8")[-3000:])
    return result.returncode


def seal():
    files = sorted(
        path
        for path in RUN.rglob("*")
        if path.is_file()
        and path.name != "artifact_manifest.json"
        and "__pycache__" not in path.parts
    )
    entries = [
        {
            "path": str(path.relative_to(ROOT)).replace("\\", "/"),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in files
    ]
    (RUN / "artifact_manifest.json").write_text(
        json.dumps(entries, indent=2), encoding="utf-8"
    )
    print(f"Sealed {len(entries)} raw artifacts.")


if __name__ == "__main__":
    if sys.argv[1] == "prepare":
        prepare()
    elif sys.argv[1] == "seal":
        seal()
    else:
        raise SystemExit(run(sys.argv[1], sys.argv[2:]))
