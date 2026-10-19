"""Record independent fix1 commands and keep all secrets only in child environments."""

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
PYTHON = 'D:/wt/r07-enrichment-jobs/backend/.venv/Scripts/python.exe'
ENV = dict(os.environ, PYTHONIOENCODING='utf-8', PYTHONPATH=str(ROOT / 'backend/src'))
for name in ('DATABASE_URL', 'REDIS_URL', 'TEST_DATABASE_URL', 'TEST_REDIS_URL', 'GENERATION_API_KEY', 'EMBEDDING_API_KEY', 'RERANKER_API_KEY'):
    ENV.pop(name, None)


def record(label, argv, env=ENV, cwd=None, timeout=240):
    started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    log = RUN / (label + '.log')
    with log.open('xb') as output:
        result = subprocess.run(argv, cwd=cwd or ROOT / 'backend', env=env, stdout=output, stderr=subprocess.STDOUT, timeout=timeout)
    receipt = {'started_at': started, 'ended_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'cwd': str(cwd or ROOT / 'backend'), 'argv': list(map(str, argv)), 'exit_code': result.returncode, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'external_paid_model_provider_source_http_calls': 0, 'log_sha256': hashlib.sha256(log.read_bytes()).hexdigest()}
    xml = RUN / (label + '.xml')
    if xml.exists():
        suites = ET.parse(xml).getroot().findall('testsuite')
        receipt['junit'] = {key: sum(int(suite.attrib.get(key, 0)) for suite in suites) for key in ('tests', 'failures', 'errors', 'skipped')}
    (RUN / (label + '.json')).write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'label': label, 'exit_code': result.returncode, 'junit': receipt.get('junit')}), flush=True)
    return result.returncode


def postgres_environment(run_id):
    assert run_id in {'r07_execution_api_review1_fix1_20261016', 'r07_execution_scope_review1_fix1_20261016'}
    script = '$resourceEncoded = Get-Content -LiteralPath D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi -Raw; $resourceSecure = ConvertTo-SecureString $resourceEncoded; [Console]::Write((ConvertFrom-SecureString -SecureString $resourceSecure -AsPlainText))'
    private = subprocess.run(['C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe', '-NoProfile', '-Command', script], capture_output=True, check=True, timeout=20)
    url = make_url(json.loads(private.stdout)['TEST_DATABASE_URL'])
    assert url.host in {'localhost', '127.0.0.1'} and url.port == 25432
    assert url.database == 'test_dianzi_r01_20261014' and url.username.startswith('test_')
    database = 'test_dianzi_' + run_id
    engine = create_engine(url, isolation_level='AUTOCOMMIT')
    with engine.connect() as connection:
        if not connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': database}):
            connection.execute(text('CREATE DATABASE "' + database + '"'))
    engine.dispose()
    return dict(ENV, TEST_DATABASE_URL=url.set(database=database).render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=run_id)


def pytest(label, paths, env=ENV):
    return record(label, [PYTHON, '-m', 'pytest', *paths, '--no-cov', '-q', '--junitxml=' + str(RUN / (label + '.xml'))], env)


if sys.argv[1] == 'pg':
    (ROOT / 'reports/runs/recovery_r07_enrichment_execution_20261016').mkdir(exist_ok=True)
    api = postgres_environment('r07_execution_api_review1_fix1_20261016')
    pytest('original_two_probe_pg', [str(RUN / 'probes/test_independent_idempotency_scope.py')], api)
    pytest('author_scope_resource_wrapper_pg', [str(RUN / 'probes/test_author_scope_resource_wrapper.py')], postgres_environment('r07_execution_scope_review1_fix1_20261016'))
    pytest('default_entry_pg35', ['tests/integration/test_r07_job_execution_pg.py', 'tests/integration/test_r07_enrichment_api_pg.py', 'tests/integration/test_r11_default_readers_pg.py', 'tests/integration/test_r07_idempotency_scope_api_pg.py'], api)
elif sys.argv[1] == 'static':
    record('src_ruff', [PYTHON, '-m', 'ruff', 'check', 'src/ai_intel'])
    record('src_format', [PYTHON, '-m', 'ruff', 'format', '--check', 'src/ai_intel'])
    record('src_mypy', [PYTHON, '-m', 'mypy', 'src/ai_intel'])
    pytest('namespace_contract_unit', ['tests/unit/test_r07_idempotency_namespace.py', 'tests/contract/test_r07_idempotency_namespace_contract.py'])
elif sys.argv[1] == 'cbm':
    prefix = ['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json']
    project = 'r07_default_entry_review1_fix1_src'
    record('cbm_index', prefix + ['index_repository', '--repo-path', '/mnt/d/wt/r07-default-entry-review1-fix1/backend/src', '--name', project, '--mode', 'fast'], cwd=ROOT)
    record('cbm_schema', prefix + ['get_graph_schema', '--project', project], cwd=ROOT)
    record('cbm_architecture', prefix + ['get_architecture', '--project', project], cwd=ROOT)
    for function in ('ai_intel.enrichment.job_service.EnrichmentJobService.enqueue', 'ai_intel.enrichment.job_service._enrichment_idempotency_key', 'ai_intel.enrichment.job_service._legacy_parent_receipt', 'ai_intel.enrichment.job_service._validated_parent_workflow'):
        record('cbm_trace_' + function.rsplit('.', 1)[-1], prefix + ['trace_path', '--project', project, '--function-name', project + '.' + function, '--direction', 'inbound', '--depth', '3', '--max-output-tokens', '4000'], cwd=ROOT)
    record('rg_callers', ['rg', '-n', r'EnrichmentJobService|\.enqueue\(|_legacy_parent_receipt|_existing_parent_receipt|_validated_parent_workflow|_enrichment_idempotency_key|build_enrichment_job_service|make_enrichment_job_handlers', 'backend/src'], cwd=ROOT)
    record('frozen_business_diff', ['git', 'diff', 'e61d9d6dd1215c337755d32d112dfe70f13d9e94', 'ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce', '--', 'backend/src', 'backend/migrations', 'backend/pyproject.toml', 'backend/uv.lock', 'contracts', 'frontend'], cwd=ROOT)
elif sys.argv[1] == 'failed_case':
    pytest('author_resource_disconnect_case_recheck', [str(RUN / 'probes/test_author_scope_resource_wrapper.py') + '::test_tampered_v2_record_with_internal_prefix_is_not_accepted_as_an_alias'], postgres_environment('r07_execution_scope_review1_fix1_20261016'))
elif sys.argv[1] == 'boundaries':
    pytest('independent_boundary_pg4', [str(RUN / 'probes/test_independent_fix1_boundaries.py')], postgres_environment('r07_execution_api_review1_fix1_20261016'))
elif sys.argv[1] == 'audit':
    record('material_audit_command', [PYTHON, str(RUN / 'audit_materials.py')], cwd=ROOT)
