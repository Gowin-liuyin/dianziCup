"""Prepare a new review-only database from the approved loopback test connection."""

import json
from pathlib import Path
import subprocess

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateIndex, CreateTable

from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.infrastructure.database import run_migrations

RUN_ID = "r08_aggregate_review1_recheck1_20261016"
DATABASE_NAME = "test_dianzi_" + RUN_ID


def test_connection():
    result = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, check=True)
    configured = json.loads(result.stdout)
    parsed = make_url(configured["TEST_DATABASE_URL"])
    if (parsed.host != "127.0.0.1" or parsed.port != 25432 or not parsed.database
        or not parsed.database.startswith("test_dianzi_") or not parsed.username
        or not parsed.username.startswith("test_")):
        raise RuntimeError("approved test connection isolation rejected")
    return parsed


def prepare():
    parsed = test_connection()
    engine = create_engine(parsed, isolation_level="AUTOCOMMIT", hide_parameters=True)
    try:
        with engine.connect() as connection:
            exists = connection.execute(text("SELECT 1 FROM pg_database WHERE datname=:name"),
                {"name": DATABASE_NAME}).scalar()
            if exists:
                raise RuntimeError("review database already exists; refusing reuse")
            connection.execute(text(f'CREATE DATABASE "{DATABASE_NAME}"'))
    finally:
        engine.dispose()
    connection_url = parsed.set(database=DATABASE_NAME).render_as_string(hide_password=False)
    run_migrations(connection_url, "0016")
    engine = create_engine(connection_url, hide_parameters=True)
    try:
        aggregate_observations.create(engine)
        with engine.connect() as connection:
            revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar()
            triggers = connection.execute(text("SELECT count(*) FROM pg_trigger WHERE "
                "tgname='r08_aggregate_observations_immutable'")).scalar()
            database = connection.execute(text("SELECT current_database()")).scalar()
            print(json.dumps({"database": database, "revision": revision, "trigger_count": triggers}))
            assert database == DATABASE_NAME and str(revision).startswith("0016") and triggers == 1
        run = Path(__file__).parent
        ddl = str(CreateTable(aggregate_observations).compile(engine)) + ";\n"
        ddl += "\n".join(str(CreateIndex(index).compile(engine)) + ";" for index in aggregate_observations.indexes)
        (run / "review_table_ddl.sql").write_text(ddl, encoding="utf-8")
        (run / "pg_prepare_receipt.json").write_text(json.dumps({"database": database,
            "host": "127.0.0.1", "port": 25432, "revision": revision,
            "own_table_create": "r08_aggregate_observations", "immutable_trigger_count": triggers,
            "production_0019": "not_run"}, indent=2), encoding="utf-8")
        print("Prepared review-only PostgreSQL: 0016 plus one aggregate table; production 0019 not_run.")
    finally:
        engine.dispose()


if __name__ == "__main__":
    try:
        prepare()
    except Exception as failure:
        print("PG preparation blocked; safe exception type=" + type(failure).__name__)
        raise SystemExit(2) from None
