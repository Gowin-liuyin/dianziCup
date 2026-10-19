"""Only route frozen tests to this reviewer's marked database and fresh schemas."""

import json
import os
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema
from sqlalchemy.pool import NullPool

import r07_input_audit_helpers as audit_helpers
from ai_intel.infrastructure.database import run_migrations
from checks import DATABASE, OWNER, ROOT, RUN, RUN_ID

SCHEMA_PREFIX = 'test_r07_review1_'


def review_owned_engine(isolated_test_database_url, register_sensitive_failure_value, *, install=True):
    url = make_url(isolated_test_database_url)
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    register_sensitive_failure_value(SecretStr(url.password or ''))
    assert url.drivername == 'postgresql+psycopg'
    assert (url.host, url.port, url.database) == ('127.0.0.1', 25432, DATABASE)
    assert url.username and url.username.startswith('test_')
    assert os.environ['DIANZI_TEST_RUN_ID'] == RUN_ID
    assert json.loads((RUN / 'owned_database_v2.json').read_bytes()) == {'database': DATABASE, 'marker': OWNER}
    base = create_engine(url, hide_parameters=True, poolclass=NullPool, connect_args={'connect_timeout': 5})
    schema = SCHEMA_PREFIX + uuid4().hex
    schema_marker = OWNER + ':' + schema
    with base.begin() as connection:
        assert connection.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")) == OWNER
        count = connection.scalar(text('SELECT count(*) FROM pg_namespace WHERE nspname LIKE :prefix'), {'prefix': SCHEMA_PREFIX + '%'})
        assert count is not None and count < 80
        connection.execute(CreateSchema(schema))
        connection.exec_driver_sql('COMMENT ON SCHEMA "' + schema + "\" IS '" + schema_marker + "'")
    isolated = url.update_query_dict({'options': f'-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=3000'})
    engine = create_engine(isolated, hide_parameters=True, poolclass=NullPool, connect_args={'connect_timeout': 5})
    try:
        run_migrations(isolated.render_as_string(hide_password=False))
        if install and os.environ.get('DIANZI_REVIEW_BASELINE') != '1':
            audit_helpers.install_audit_proposal(engine)
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            assert connection.scalar(text("SELECT obj_description(oid,'pg_namespace') FROM pg_namespace WHERE nspname=:name"), {'name': schema}) == schema_marker
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


def pytest_configure(config):
    audit_helpers.DATABASE = DATABASE
    audit_helpers.SCHEMA_PREFIX = SCHEMA_PREFIX
    audit_helpers.owned_audit_engine = review_owned_engine
    import tests.r07_idempotency_scope_helpers as scope_helpers
    import test_r06_catalog_documents_pg
    import test_r07_enrichment_api_pg
    import test_r07_job_execution_pg
    scope_helpers.scope_engine = audit_helpers.audit_engine
    test_r06_catalog_documents_pg.catalog_engine = audit_helpers.audit_engine
    test_r07_enrichment_api_pg.execution_engine = audit_helpers.default_api_audit_engine
    test_r07_job_execution_pg.execution_engine = audit_helpers.audit_engine


@pytest.fixture
def register_sensitive_failure_value(request):
    keys = set()
    for plugin in request.config.pluginmanager.get_plugins():
        hook = getattr(plugin, 'pytest_runtest_makereport', None)
        if hook is not None:
            key = getattr(hook, '__globals__', {}).get('REGISTERED_FAILURE_CREDENTIALS')
            if key is not None:
                keys.add(key)
    assert keys
    def register(value):
        assert type(value) is SecretStr
        for key in keys:
            request.node.stash.setdefault(key, []).append(value)
    return register


def pytest_sessionstart(session):
    original_text, original_bytes = Path.write_text, Path.write_bytes
    author_run = ROOT / 'reports/runs/recovery_r07_input_audit_20261016'
    original_run = ROOT / 'reports/runs/recovery_r07_enrichment_execution_20261016'
    redirected = {original_run / 'nvd_input_budget_observation.json': RUN / 'nvd_old_case_observation.json', author_run / 'nvd_current_selection_observation.json': RUN / 'nvd_author_test_observation.json'}
    def write_text(path, *args, **kwargs):
        return original_text(redirected.get(path, path), *args, **kwargs)
    def write_bytes(path, *args, **kwargs):
        return original_bytes(redirected.get(path, path), *args, **kwargs)
    Path.write_text, Path.write_bytes = write_text, write_bytes
