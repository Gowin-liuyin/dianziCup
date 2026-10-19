"""Keep author test functions unchanged while isolating their PG resource in a new database."""

import importlib.util
import sys
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend/tests/integration'))


@pytest.fixture
def isolated_test_database_url():
    from scripts.dev import require_isolated_test_database

    return require_isolated_test_database()


@pytest.fixture
def scope_engine(isolated_test_database_url):
    from ai_intel.infrastructure.database import run_migrations

    url = make_url(isolated_test_database_url)
    assert url.database == 'test_dianzi_r07_execution_scope_review1_fix1_20261016'
    base = create_engine(url, connect_args={'connect_timeout': 5})
    schema = 'test_r07_scope_review1_fix1_' + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict({'options': f'-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000'})
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated)
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0019_aggregate_observations'
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


for relative in ('backend/tests/integration/test_r07_idempotency_scope_pg.py', 'backend/tests/security/test_r07_idempotency_scope_security.py'):
    spec = importlib.util.spec_from_file_location('independent_' + Path(relative).stem, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    for name, value in vars(module).items():
        if name.startswith('test_') and callable(value):
            assert name not in globals()
            globals()[name] = value

