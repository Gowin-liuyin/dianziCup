"""Create only this run's test database; connection secrets remain in process memory."""

import json
import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import CompileError, ProgrammingError
from sqlalchemy.schema import CreateIndex, CreateTable

RUN_ID = "r08_cache_ttl_fix1_20261016"
run_directory = Path(__file__).parent
root = run_directory.parents[2]
sys.path.insert(0, str(root / "backend" / "src"))
from ai_intel.assets.aggregate_persistence_models import (
    IMMUTABILITY_FUNCTION_DDL, IMMUTABILITY_TRIGGER_DDL, aggregate_observations,
)
from ai_intel.infrastructure.database import run_migrations

def test_connection() -> str:
    result = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, check=True)
    configured = json.loads(result.stdout)
    database_url = configured.get("TEST_DATABASE_URL")
    if not isinstance(database_url, str):
        raise RuntimeError("blocked: approved test connection field unavailable")
    parsed = make_url(database_url)
    if parsed.host not in ("localhost", "127.0.0.1") or parsed.port != 25432 or not parsed.database or not parsed.database.startswith("test_dianzi_") or not parsed.username or not parsed.username.startswith("test_"):
        raise RuntimeError("blocked: approved test connection does not satisfy isolation")
    unique_database = f"test_dianzi_{RUN_ID}"
    base = create_engine(parsed, isolation_level="AUTOCOMMIT", hide_parameters=True)
    try:
        with base.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": unique_database}).scalar()
            if not exists:
                connection.execute(text(f'CREATE DATABASE "{unique_database}"'))
    finally:
        base.dispose()
    return parsed.set(database=unique_database).render_as_string(hide_password=False)

if __name__ == "__main__":
    try:
        connection_url = test_connection()
        run_migrations(connection_url, "0016")
        engine = create_engine(connection_url, hide_parameters=True)
        with engine.connect() as connection:
            assert connection.execute(text("SELECT current_database()")).scalar() == f"test_dianzi_{RUN_ID}"
        aggregate_observations.create(engine, checkfirst=True)
        with engine.begin() as connection:
            if not connection.execute(text("SELECT 1 FROM pg_trigger WHERE tgname='r08_aggregate_observations_immutable'")).scalar():
                connection.execute(text(IMMUTABILITY_FUNCTION_DDL))
                connection.execute(text(IMMUTABILITY_TRIGGER_DDL))
        ddl = str(CreateTable(aggregate_observations).compile(engine)) + ";\n"
        ddl += "\n".join(str(CreateIndex(index).compile(engine)) + ";" for index in aggregate_observations.indexes)
        ddl += "\n" + IMMUTABILITY_FUNCTION_DDL + ";\n" + IMMUTABILITY_TRIGGER_DDL + ";\n"
        (run_directory / "ddl_proposal.sql").write_text(ddl, encoding="utf-8")
        (run_directory / "pg_prepare_receipt.json").write_text(json.dumps({"database": f"test_dianzi_{RUN_ID}", "host": "loopback", "port": 25432,
            "baseline_revision": "0016", "test_own_table_create": "r08_aggregate_observations", "production_migration_validation": "not_run"}, indent=2), encoding="utf-8")
        engine.dispose()
        print("Prepared isolated R08 test database at revision 0016 plus its own table; no production migration verified.")
    except Exception as failure:
        print("blocked: approved isolated PostgreSQL preparation failed; no connection details emitted")
        print("exception_type=" + type(failure).__name__)
        if isinstance(failure, CompileError):
            print("safe_compile_diagnostic=" + str(failure))
        elif isinstance(failure, ProgrammingError):
            print("safe_sqlstate=" + str(getattr(failure.orig, "sqlstate", "unknown")))
            print("safe_ddl_diagnostic=" + str(getattr(getattr(failure.orig, "diag", None), "message_primary", "unavailable")))
        raise SystemExit(2) from None
