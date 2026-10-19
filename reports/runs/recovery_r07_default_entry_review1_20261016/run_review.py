"""Run independent checks without logging credentials or changing author evidence."""

import hashlib
import json
import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
PYTHON = Path('D:/wt/r07-enrichment-jobs/backend/.venv/Scripts/python.exe')
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=str(ROOT / 'backend/src'))
for name in ('DATABASE_URL', 'REDIS_URL', 'TEST_DATABASE_URL', 'TEST_REDIS_URL', 'GENERATION_API_KEY', 'EMBEDDING_API_KEY', 'RERANKER_API_KEY'):
    ENV.pop(name, None)


def record(label, argv, *, env=ENV, cwd=None, timeout=240):
    started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    path = RUN / (label + '.log')
    with path.open('xb') as output:
        result = subprocess.run(argv, cwd=cwd or ROOT / 'backend', env=env, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    receipt = {
        'started_at': started,
        'ended_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),
        'cwd': str(cwd or ROOT / 'backend'), 'argv': list(map(str, argv)),
        'exit_code': result.returncode,
        'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'paid_model_provider_source_http_calls': 0,
        'log_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
    }
    xml = RUN / (label + '.xml')
    if xml.exists():
        suites = ET.parse(xml).getroot().findall('testsuite')
        receipt['junit'] = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    (RUN / (label + '.json')).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'label': label, 'exit_code': result.returncode, 'junit': receipt.get('junit')}), flush=True)
    return result.returncode


def postgres_environment(run_id):
    private = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'], capture_output=True, check=True)
    url = make_url(json.loads(private.stdout)['TEST_DATABASE_URL'])
    assert url.host in {'localhost', '127.0.0.1'} and url.port == 25432
    database = 'test_dianzi_' + run_id
    assert run_id in {'r07_execution_api_review1_20261016', 'r06_catalog_r07_metadata_review1_20261016'}
    engine = create_engine(url, isolation_level='AUTOCOMMIT')
    with engine.connect() as connection:
        if not connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': database}):
            connection.execute(text('CREATE DATABASE "' + database + '"'))
    engine.dispose()
    return dict(ENV, DIANZI_TEST_RUN_ID=run_id, TEST_DATABASE_URL=url.set(database=database).render_as_string(hide_password=False))


def pytest(label, paths, env=ENV):
    return record(label, [str(PYTHON), '-m', 'pytest', *paths, '--no-cov', '-q', '--junitxml=' + str(RUN / (label + '.xml'))], env=env)


if sys.argv[1] == 'pg':
    (ROOT / 'reports/runs/recovery_r07_enrichment_execution_20261016').mkdir(exist_ok=True)
    environment = postgres_environment('r07_execution_api_review1_20261016')
    pytest('independent_default_pg', ['tests/integration/test_r07_job_execution_pg.py', 'tests/integration/test_r07_enrichment_api_pg.py', 'tests/integration/test_r11_default_readers_pg.py'], environment)
    pytest('independent_metadata_pg', ['tests/integration/test_r07_enrichment_job_metadata_pg.py'], postgres_environment('r06_catalog_r07_metadata_review1_20261016'))
elif sys.argv[1] == 'static':
    record('independent_ruff', [str(PYTHON), '-m', 'ruff', 'check', 'src/ai_intel'])
    record('independent_format', [str(PYTHON), '-m', 'ruff', 'format', '--check', 'src/ai_intel'])
    record('independent_mypy', [str(PYTHON), '-m', 'mypy', 'src/ai_intel'])
    pytest('independent_contract133', ['tests/contract/test_r07_enrichment_api_response.py', 'tests/contract/test_r07_enrichment_runtime_policy.py', 'tests/unit/test_r01_worker_configuration.py', 'tests/unit/test_r01_runtime_settings.py', 'tests/unit/test_r04_source_jobs.py'])
elif sys.argv[1] == 'cbm':
    prefix = ['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json']
    project = 'r07_default_entry_review1_src_root'
    record('cbm_src_index', prefix + ['index_repository', '--repo-path', '/mnt/d/wt/r07-default-entry-review1/backend/src', '--name', project, '--mode', 'fast'], cwd=ROOT)
    record('cbm_src_schema', prefix + ['get_graph_schema', '--project', project], cwd=ROOT)
    record('cbm_src_architecture', prefix + ['get_architecture', '--project', project], cwd=ROOT)
    for function in ('ai_intel.api.enrichment_routes.build_enrichment_router', 'ai_intel.enrichment.runtime_policy.build_enrichment_job_service', 'ai_intel.workers.runtime.consume_job', 'ai_intel.enrichment.job_service.EnrichmentJobService.execute_step', 'ai_intel.enrichment.job_service.EnrichmentJobService.publish', 'ai_intel.infrastructure.models.generation.GenerationClient.generate'):
        record('cbm_trace_' + function.rsplit('.', 1)[-1], prefix + ['trace_path', '--project', project, '--function-name', project + '.' + function, '--direction', 'inbound', '--depth', '3', '--max-output-tokens', '3500'], cwd=ROOT)
    assets = 'r07_default_entry_review1_assets_root'
    record('cbm_assets_index', prefix + ['index_repository', '--repo-path', '/mnt/d/wt/r07-default-entry-review1/backend/src/ai_intel/assets', '--name', assets, '--mode', 'fast'], cwd=ROOT)
    record('cbm_assets_schema', prefix + ['get_graph_schema', '--project', assets], cwd=ROOT)
    record('cbm_assets_architecture', prefix + ['get_architecture', '--project', assets], cwd=ROOT)
elif sys.argv[1] == 'probes':
    pytest('independent_negative_pg', [str(RUN / 'probes/test_independent_entry.py')], postgres_environment('r07_execution_api_review1_20261016'))
elif sys.argv[1] == 'related':
    pytest('independent_related194', ['tests/unit/test_r07_job_execution_helpers.py', 'tests/contract/test_r07_job_execution_views.py', 'tests/security/test_r07_job_execution_boundaries.py', 'tests/contract/test_r07_enrichment_api_response.py', 'tests/contract/test_r07_enrichment_runtime_policy.py', 'tests/contract/test_r07_enrichment_job_request.py', 'tests/contract/test_r07_enrichment_execution_policy.py', 'tests/unit/test_r01_worker_configuration.py', 'tests/unit/test_r01_runtime_settings.py', 'tests/unit/test_r04_source_jobs.py'])
elif sys.argv[1] == 'extra':
    pytest('independent_forward_asset_pg', [str(RUN / 'probes/test_independent_forward_asset.py')], postgres_environment('r07_execution_api_review1_20261016'))
elif sys.argv[1] == 'audit':
    record('frozen_evidence_audit', [str(PYTHON), str(RUN / 'audit_evidence.py')], cwd=ROOT)
elif sys.argv[1] == 'recheck':
    record('latest_business_source_unchanged', ['git', 'diff', '--exit-code', '1f0522e3f3fb9547ea55136efa64fc589466c992', 'e61d9d6dd1215c337755d32d112dfe70f13d9e94', '--', 'backend/src', 'backend/migrations'], cwd=ROOT)
    record('latest_metadata_compatibility_diff', ['git', 'diff', '1b894daaa4523f37600c8ff8f9990c5df534a3fa', 'e61d9d6dd1215c337755d32d112dfe70f13d9e94', '--', 'backend/tests/integration/test_r07_enrichment_job_metadata_pg.py', 'docs/decisions/CR-R07_metadata_head_test_compatibility.md'], cwd=ROOT)
    pytest('independent_metadata_final_pg', ['tests/integration/test_r07_enrichment_job_metadata_pg.py'], postgres_environment('r06_catalog_r07_metadata_review1_20261016'))
    pytest('independent_forward_asset_pg_v2', [str(RUN / 'probes/test_independent_forward_asset.py')], postgres_environment('r07_execution_api_review1_20261016'))
elif sys.argv[1] == 'trace':
    prefix = ['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json']
    project = 'r07_default_entry_review1_src_root'
    for function in ('ai_intel.enrichment.job_service.EnrichmentJobService.initialize', 'ai_intel.enrichment.job_service.EnrichmentJobService.execute_step', 'ai_intel.enrichment.job_service.EnrichmentJobService.publish', 'ai_intel.api.app.create_application'):
        record('cbm_outbound_' + function.rsplit('.', 1)[-1], prefix + ['trace_path', '--project', project, '--function-name', project + '.' + function, '--direction', 'outbound', '--depth', '3', '--max-output-tokens', '5000'], cwd=ROOT)
    record('source_registration_crosscheck', ['rg', '-n', 'build_enrichment_job_service|make_enrichment_job_handlers|build_enrichment_router|build_job_router|build_graph_router|build_inventory_router|celery_app.task|service.initialize|service.execute_step|service.publish', 'backend/src/ai_intel/api', 'backend/src/ai_intel/enrichment', 'backend/src/ai_intel/workers'], cwd=ROOT)
elif sys.argv[1] == 'scope':
    pytest('independent_idempotency_scope_pg', [str(RUN / 'probes/test_independent_idempotency_scope.py')], postgres_environment('r07_execution_api_review1_20261016'))
