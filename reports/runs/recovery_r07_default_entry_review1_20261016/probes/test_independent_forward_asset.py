"""Forward-only migration and default asset history probes preserve their evidence."""

import sys
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, inspect, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'backend/tests/integration'))

from test_r07_enrichment_api_pg import ORIGIN, application_client, execution_engine
from test_r07_enrichment_job_metadata_pg import NOW, seed_workflow
from test_r07_job_execution_pg import setup

from ai_intel.api.auth_routes import CSRF_HEADER_NAME
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import job_runs, users


@pytest.fixture
def isolated_test_database_url():
    from scripts.dev import require_isolated_test_database

    return require_isolated_test_database()


def test_forward0017_to0019_retains_paid_reservation_and_pg_state(isolated_test_database_url, tmp_path):
    url = make_url(isolated_test_database_url)
    assert url.database.startswith('test_dianzi_r07_execution_api_review1_')
    schema = 'test_independent_r07_forward_' + uuid4().hex
    base = create_engine(url)
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict({'options': '-c search_path=' + schema + ' -c statement_timeout=15000 -c lock_timeout=3000'})
    run_migrations(isolated.render_as_string(hide_password=False), '0017_enrichment_job_workflows')
    engine = create_engine(isolated)
    workflow, parent, child = seed_workflow(engine, tmp_path)
    with engine.begin() as connection:
        connection.execute(update(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child).values(model_call_reserved_at=NOW))
    with engine.connect() as connection:
        original_job_ids = set(connection.scalars(select(job_runs.c.job_id)))
    assert {parent, child} <= original_job_ids
    run_migrations(isolated.render_as_string(hide_password=False), 'head')
    with engine.connect() as connection:
        assert connection.scalar(text('SELECT version_num FROM alembic_version')) == '0019_aggregate_observations'
        assert connection.scalar(select(enrichment_workflows.c.workflow_id)) == workflow
        assert set(connection.scalars(select(job_runs.c.job_id))) == original_job_ids
        row = connection.execute(select(enrichment_job_steps).where(enrichment_job_steps.c.job_id == child)).mappings().one()
        assert row['model_call_reserved_at'] == NOW and row['model_call_completed_at'] is None
        assert row['model_trace'] == []
        assert connection.scalar(select(job_runs.c.status).where(job_runs.c.job_id == parent)) == 'queued'
    assert 'status' not in {row['name'] for row in inspect(engine).get_columns('enrichment_job_steps')}
    (Path(__file__).parent.parent / 'resources/forward_schema.json').write_text(__import__('json').dumps({'data_mode': 'fixture', 'database': url.database, 'schema': schema, 'forward_revisions': ['0017_enrichment_job_workflows', '0019_aggregate_observations'], 'actual_model_calls': 0, 'schema_preserved': True}, indent=2), encoding='utf-8')
    engine.dispose()
    base.dispose()


@pytest.mark.parametrize('prefix', ['/v1', '/api/v1'])
def test_default_asset_current_replay_history_and_acl(execution_engine, tmp_path, prefix):
    _, scope, _, _, _, _ = setup(execution_engine, tmp_path)
    with execution_engine.begin() as connection:
        connection.execute(update(users).where(users.c.user_id == scope.user_id).values(role='tenant_admin', tenant_id='independent-asset-owner'))
    headers = {'origin': ORIGIN, CSRF_HEADER_NAME: 'synthetic-csrf', 'Idempotency-Key': 'independent-asset-first'}
    params = {'display_name': 'Independent asset', 'source_version': 'v1', 'observed_at': datetime.now(UTC).isoformat(), 'manifest_format': 'json_manifest_v1'}
    first_raw = b'{"format_version":1,"components":[{"ecosystem":"pypi","package_name":"langchain","version":"1.0"}]}'
    second_raw = b'{"format_version":1,"components":[{"ecosystem":"pypi","package_name":"langchain","version":"1.1"}]}'
    with application_client(execution_engine, tmp_path, scope) as client:
        first = client.post(prefix + '/asset-imports', params=params, content=first_raw, headers=headers)
        assert first.status_code == 201
        identity, historical = first.json()['asset_id'], first.json()['snapshot']['snapshot_id']
        replay = client.post(prefix + '/asset-imports', params=params, content=first_raw, headers=headers)
        assert replay.status_code == 201 and replay.json()['snapshot']['snapshot_id'] == historical
        second = client.post(prefix + '/asset-imports', params=dict(params, asset_id=identity, source_version='v2'), content=second_raw, headers=dict(headers, **{'Idempotency-Key': 'independent-asset-second'}))
        assert second.status_code == 201
        current = second.json()['snapshot']['snapshot_id']
        assert current != historical
        assert client.get(prefix + '/assets/' + identity).json()['current_snapshot_id'] == current
        assert len(client.get(prefix + '/assets/' + identity + '/snapshots').json()['items']) == 2
        assert client.get(prefix + f'/assets/{identity}/snapshots/{historical}').status_code == 200
        assert client.get(prefix + '/assets?tenant_id=forged').status_code == 422
        with execution_engine.begin() as connection:
            connection.execute(update(users).where(users.c.user_id == scope.user_id).values(tenant_id='independent-asset-other'))
        assert client.get(prefix + '/assets/' + identity).status_code == 404
        assert client.get(prefix + f'/assets/{identity}/snapshots/{historical}').status_code == 404
        assert client.get(prefix + '/assets').json()['items'] == []
