"""Exercise pgvector SQL in a named synthetic-only database without touching product data."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
DATABASE = "test_dianzi_r05_pgvector_20261015"
SECRET_SOURCE = "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"
SECRET_DESTINATION = "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json"
ZONE = ZoneInfo("Asia/Shanghai")


def now() -> str:
    return datetime.now(ZONE).isoformat(timespec="seconds")


def connect_database(database_name: str) -> psycopg.Connection:
    database_url = make_url(os.environ["TEST_DATABASE_URL"])
    assert database_url.host == "127.0.0.1"
    assert database_url.port == 25432
    assert database_url.database == "test_dianzi_r01_20261014"
    assert database_name in (database_url.database, DATABASE)
    return psycopg.connect(
        host=database_url.host,
        port=database_url.port,
        dbname=database_name,
        user=database_url.username,
        password=database_url.password,
        connect_timeout=10,
        options="-c statement_timeout=10000 -c lock_timeout=5000",
    )


def verify_database() -> None:
    cases = []
    result = {
        "started_at": now(),
        "cwd": os.getcwd(),
        "database": DATABASE,
        "data_mode": "synthetic_runtime_probe",
        "cases": cases,
    }
    with connect_database("test_dianzi_r01_20261014") as connection:
        connection.autocommit = True
        exists = connection.execute(
            "SELECT datname FROM pg_database WHERE datname = %s", (DATABASE,)
        ).fetchone()
        if exists is None:
            connection.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
        cases.append({"id": "PV-C01", "status": "passed", "database_created_or_exists": True})
    with connect_database(DATABASE) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector")
        extension = connection.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()[0]
        assert extension == "0.8.2"
        cases.append({"id": "PV-C02", "status": "passed", "extension_version": extension})
        connection.execute(
            "CREATE TABLE IF NOT EXISTS synthetic_vector_probe "
            "(id integer PRIMARY KEY, embedding vector(3) NOT NULL)"
        )
        connection.execute(
            "INSERT INTO synthetic_vector_probe "
            "VALUES (1,'[1,0,0]'),(2,'[1,1,0]'),(3,'[-1,0,0]') "
            "ON CONFLICT (id) DO NOTHING"
        )
        connection.commit()
        order = connection.execute(
            "SELECT id, embedding <=> '[1,0,0]'::vector AS distance "
            "FROM synthetic_vector_probe ORDER BY distance, id"
        ).fetchall()
        assert [row[0] for row in order] == [1, 2, 3]
        assert order[0][1] == 0.0 and abs(order[1][1] - 0.2928932188134525) < 1e-7
        assert order[2][1] == 2.0
        cases.append({"id": "PV-C03", "status": "passed", "cosine_order_and_distance": order})
        plan = connection.execute(
            "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) "
            "SELECT id FROM synthetic_vector_probe "
            "ORDER BY embedding <=> '[1,0,0]'::vector LIMIT 3"
        ).fetchone()[0]
        assert plan[0]["Plan"]["Actual Rows"] == 3
        cases.append(
            {
                "id": "PV-C04",
                "status": "passed",
                "explain": plan,
                "scope": "actual SQL plan only; not a formal performance result",
            }
        )
        connection.commit()
        for case_id, value, expected_sqlstate in [
            ("PV-C05", "[1,0]", "22000"),
            ("PV-C06", "[NaN,0,0]", "22000"),
            ("PV-C07", "[Infinity,0,0]", "22000"),
        ]:
            try:
                connection.execute(
                    "INSERT INTO synthetic_vector_probe (id,embedding) VALUES (90,%s::vector)",
                    (value,),
                )
            except psycopg.Error as error:
                observed_sqlstate = error.sqlstate
                connection.rollback()
                assert observed_sqlstate == expected_sqlstate
                assert (
                    connection.execute(
                        "SELECT count(*) FROM synthetic_vector_probe WHERE id=90"
                    ).fetchone()[0]
                    == 0
                )
                connection.commit()
                cases.append(
                    {"id": case_id, "status": "passed", "rejected_sqlstate": observed_sqlstate}
                )
            else:
                connection.rollback()
                raise AssertionError(f"{case_id}: invalid vector was accepted")
        connection.execute("INSERT INTO synthetic_vector_probe VALUES (99,'[0,1,0]')")
        connection.rollback()
        assert (
            connection.execute(
                "SELECT count(*) FROM synthetic_vector_probe WHERE id=99"
            ).fetchone()[0]
            == 0
        )
        connection.commit()
        cases.append({"id": "PV-C08", "status": "passed", "rolled_back_row_count": 0})
        connection.execute(
            "CREATE TABLE IF NOT EXISTS synthetic_vector_384_probe "
            "(id integer PRIMARY KEY, embedding vector(384) NOT NULL)"
        )
        vector_384 = "[" + ",".join(["1"] + ["0"] * 383) + "]"
        connection.execute(
            "INSERT INTO synthetic_vector_384_probe VALUES (1,%s::vector) "
            "ON CONFLICT (id) DO NOTHING",
            (vector_384,),
        )
        assert connection.execute(
            "SELECT vector_dims(embedding), embedding <=> embedding "
            "FROM synthetic_vector_384_probe WHERE id=1"
        ).fetchone() == (384, 0.0)
        connection.commit()
        cases.append(
            {"id": "PV-C09", "status": "passed", "dimensions": 384, "self_cosine_distance": 0.0}
        )
    with connect_database(DATABASE) as connection:
        stored = connection.execute(
            "SELECT id, embedding::text FROM synthetic_vector_probe ORDER BY id"
        ).fetchall()
        assert stored == [(1, "[1,0,0]"), (2, "[1,1,0]"), (3, "[-1,0,0]")]
        cases.append({"id": "PV-C10", "status": "passed", "reconnected_committed_rows": stored})
    cases.append(
        {
            "id": "PV-C11",
            "status": "not_run",
            "reason": "shared PostgreSQL restart prohibited; "
            "reconnection is not restart durability",
        }
    )
    result.update(ended_at=now(), exit_code=0, passed_count=10, failed_count=0, not_run_count=1)
    (RUN / "isolated_sql_verification.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False))


def launch_verification() -> int:
    source = subprocess.run(
        ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", SECRET_SOURCE],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    )
    database_url = json.loads(source.stdout)["TEST_DATABASE_URL"]
    child = subprocess.run(
        [sys.executable, str(Path(__file__).resolve()), "--verify"],
        env=dict(os.environ, TEST_DATABASE_URL=database_url),
        capture_output=True,
        text=True,
        timeout=90,
    )
    output = (child.stdout + child.stderr).replace(database_url, "[REDACTED]")
    password = make_url(database_url).password
    if password:
        output = output.replace(password, "[REDACTED]")
        for offset in range(len(password) - 7):
            output = output.replace(password[offset : offset + 8], "[REDACTED-FRAGMENT]")
    (RUN / "isolated_sql_verification.log").write_text(output, encoding="utf-8")
    print(output, end="")
    if child.returncode == 0:
        derived_url = (
            make_url(database_url).set(database=DATABASE).render_as_string(hide_password=False)
        )
        writer = """import json, os, pathlib, stat, sys
p = pathlib.Path(sys.argv[1])
p.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
content = sys.stdin.buffer.read()
if p.exists():
    assert p.stat().st_uid == 0 and stat.S_IMODE(p.stat().st_mode) == 0o600
    assert json.loads(p.read_bytes()) == json.loads(content), 'dedicated secret conflict'
else:
    fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    os.write(fd, content)
    os.close(fd)
"""
        subprocess.run(
            [
                "wsl",
                "-d",
                "Ubuntu-22.04",
                "-u",
                "root",
                "--",
                "python3",
                "-c",
                writer,
                SECRET_DESTINATION,
            ],
            input=json.dumps({"TEST_DATABASE_URL": derived_url}),
            text=True,
            capture_output=True,
            check=True,
            timeout=15,
        )
    return child.returncode


if __name__ == "__main__":
    if "--verify" in sys.argv:
        verify_database()
    else:
        raise SystemExit(launch_verification())
