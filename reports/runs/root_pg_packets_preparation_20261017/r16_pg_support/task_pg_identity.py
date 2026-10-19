"""Check the Root-created nonce DB/schema identity using one temporary connection."""

import json
import os
import re

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from pg_review_environment import QUALIFIED


def verify_native_identity(connection):
    with open(os.environ["R18_REVIEW_IDENTITY_FILE"], encoding="utf-8") as stream:
        identity = json.load(stream)
    assert identity["source_sha"] == QUALIFIED
    assert identity["run_id"] == os.environ["DIANZI_TEST_RUN_ID"]
    assert re.fullmatch(r"r16_change_history_http_[a-f0-9]{12}", identity["run_id"])
    assert identity["database"] == "test_dianzi_" + identity["run_id"]
    assert re.fullmatch(r"test_r16_review1_[a-f0-9]{12}", identity["schema"])
    assert connection.scalar(text("SELECT current_database()")) == identity["database"]
    assert connection.scalar(text("SELECT current_user")) == identity["role"]
    assert connection.scalar(text("SELECT current_schema()")) == identity["schema"]
    assert 160000 <= int(connection.scalar(text("SHOW server_version_num"))) < 170000
    role = connection.execute(text("SELECT oid,shobj_description(oid,'pg_authid') FROM pg_roles WHERE rolname=current_user")).one()
    assert tuple(role) == (identity["role_oid"], identity["role_comment"])
    database = connection.execute(text("SELECT oid,shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")).one()
    assert tuple(database) == (identity["database_oid"], identity["database_comment"])
    marker = json.loads(identity["database_comment"])
    assert len(marker) == 9 and marker["run_id"] == identity["run_id"]
    assert marker["product_sha"] == QUALIFIED
    assert marker["owner"].startswith("r16-history-review1:")
    schema = connection.execute(text("SELECT oid,obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname=current_schema()")).one()
    assert tuple(schema) == (identity["schema_oid"], identity["schema_comment"])
    return identity


def pytest_sessionstart(session):
    if session.config.option.collectonly:
        return
    engine = create_engine(os.environ["R18_REVIEW_MIGRATION_DATABASE_URL"], poolclass=NullPool, hide_parameters=True)
    try:
        with engine.connect() as connection:
            verify_native_identity(connection)
    finally:
        engine.dispose()
