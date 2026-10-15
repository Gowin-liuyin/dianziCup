"""Owned PostgreSQL schemas use the production forward chain and bounded resources."""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import MetaData, Table, create_engine, text
from sqlalchemy.engine import URL, Engine, make_url

from ai_intel.infrastructure.database import run_migrations

RUN_ID = "r11_forward_rules_sbom_20261016"
DATABASE = "test_dianzi_" + RUN_ID
HEAD = "0022_sbom_sidecars"
SCHEMA_PREFIX = "test_r11_forward_"
ALEMBIC_TABLE_CREATE = Table.create


def owned_url() -> URL:
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, DATABASE)
    assert url.username and url.username.startswith("test_")
    assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID
    return url


def forbid_metadata_creation(*arguments: object, **keywords: object) -> None:
    raise AssertionError("production migration must not create tables through metadata")


def forbid_business_table_creation(table, *arguments, **keywords):
    if table.name != "alembic_version":
        raise AssertionError("business tables must be created by forward migrations")
    return ALEMBIC_TABLE_CREATE(table, *arguments, **keywords)


@contextmanager
def migrated_schema(target: str = "head") -> Iterator[tuple[Engine, URL, str]]:
    url = owned_url()
    base = create_engine(url, hide_parameters=True, connect_args={"connect_timeout": 5})
    schema = SCHEMA_PREFIX + uuid4().hex
    with base.begin() as connection:
        count = connection.scalar(
            text(
                "SELECT count(*) FROM information_schema.schemata "
                "WHERE schema_name LIKE 'test_r11_forward_%'"
            )
        )
        assert count is not None and count < 80
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    migration_url = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    runtime_url = url.update_query_dict(
        {
            "options": f"-c search_path={schema},public "
            "-c statement_timeout=15000 -c lock_timeout=5000"
        }
    )
    engine = create_engine(
        runtime_url,
        hide_parameters=True,
        pool_size=8,
        max_overflow=2,
        connect_args={"connect_timeout": 5},
    )
    try:
        with pytest.MonkeyPatch.context() as patch:
            patch.setattr(MetaData, "create_all", forbid_metadata_creation)
            patch.setattr(Table, "create", forbid_business_table_creation)
            run_migrations(migration_url.render_as_string(hide_password=False), target)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == schema
            revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
            assert revision == (HEAD if target == "head" else target)
        receipt = {
            "schema": schema,
            "database": DATABASE,
            "revision": revision,
            "forward_only": True,
            "retained": True,
            "metadata_creation": False,
        }
        evidence = os.environ.get("R11_FORWARD_EVIDENCE_DIR")
        if evidence:
            with (Path(evidence) / "schema_receipts.jsonl").open("a", encoding="utf-8") as output:
                output.write(json.dumps(receipt) + "\n")
        yield engine, migration_url, schema
    finally:
        engine.dispose()
        base.dispose()
