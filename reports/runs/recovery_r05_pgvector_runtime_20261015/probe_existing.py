"""Only inspect the authorized PostgreSQL before preparing a separate test database."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")
SECRET_PATH = "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"


def now() -> str:
    return datetime.now(ZONE).isoformat(timespec="seconds")


def inspect_database() -> None:
    database_url = make_url(os.environ["TEST_DATABASE_URL"])
    assert database_url.host == "127.0.0.1"
    assert database_url.port == 25432
    assert database_url.database == "test_dianzi_r01_20261014"
    result = {"started_at": now(), "cwd": os.getcwd(), "mode": "read_only"}
    with psycopg.connect(
        host=database_url.host,
        port=database_url.port,
        dbname=database_url.database,
        user=database_url.username,
        password=database_url.password,
        connect_timeout=10,
        options="-c default_transaction_read_only=on -c statement_timeout=10000",
    ) as connection:
        for name, query in {
            "server": "SELECT version(), current_database(), inet_server_port()",
            "available_vector": "SELECT name, default_version, installed_version "
            "FROM pg_available_extensions WHERE name = 'vector'",
            "installed_extensions": "SELECT extname, extversion FROM pg_extension ORDER BY extname",
        }.items():
            result[name] = connection.execute(query).fetchall()
    result.update(ended_at=now(), exit_code=0)
    (RUN / "existing_database_probe.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


def launch_probe() -> int:
    result = subprocess.run(
        ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", SECRET_PATH],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    secret_values = json.loads(result.stdout)
    database_url = secret_values["TEST_DATABASE_URL"]
    environment = dict(os.environ, TEST_DATABASE_URL=database_url)
    child = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--database-probe"],
        env=environment,
        capture_output=True,
        text=True,
        timeout=45,
    )
    output = child.stdout + child.stderr
    output = output.replace(database_url, "[REDACTED]")
    password = make_url(database_url).password
    if password:
        output = output.replace(password, "[REDACTED]")
        for offset in range(len(password) - 7):
            output = output.replace(password[offset : offset + 8], "[REDACTED-FRAGMENT]")
    (RUN / "existing_database_probe.log").write_text(output, encoding="utf-8")
    print(output, end="")
    return child.returncode


if __name__ == "__main__":
    if "--database-probe" in sys.argv:
        inspect_database()
    else:
        raise SystemExit(launch_probe())
