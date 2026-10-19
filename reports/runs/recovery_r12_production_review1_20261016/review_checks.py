"""Independent fixed-tree commands and owned-resource review evidence."""

import difflib
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = Path('D:/dianzi/backend/.venv/Scripts/python.exe')
RUN_ID = 'r12_prod_review1_20261016'
DATABASE = 'test_dianzi_r12_prod_review1_20261016'
CODE = 'ed0e14a03a06ed104f23afd0be5407d873ed8edf'
MATERIAL = '8c03ed305f8d40bfcaf4b090e95979e75fba7147'


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + '\n', encoding='utf-8', newline='\n')


def credentials():
    result = subprocess.run([
        'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe',
        '-NoProfile', '-Command',
        "$reviewProtected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
        "$reviewClear=$reviewProtected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($reviewClear)",
    ], capture_output=True, timeout=20, check=True)
    original = make_url(json.loads(result.stdout)['TEST_DATABASE_URL'])
    if (original.host, original.port, original.database) != ('127.0.0.1', 25432, 'test_dianzi_r01_20261014') or not original.username.startswith('test_'):
        raise RuntimeError('rejected resource identity')
    return original


def owned_url():
    original = credentials()
    configured = original.set(database=DATABASE)
    marker = RUN / 'owned_database.json'
    engine = create_engine(original, isolation_level='AUTOCOMMIT', hide_parameters=True)
    try:
        with engine.connect() as connection:
            exists = connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': DATABASE})
            if exists:
                if not marker.exists() or json.loads(marker.read_text())['database'] != DATABASE:
                    raise RuntimeError('database exists without review ownership')
            else:
                connection.exec_driver_sql('CREATE DATABASE "' + DATABASE + '"')
                write_json(marker, {'database': DATABASE, 'created_at': now(), 'owner': RUN_ID})
    finally:
        engine.dispose()
    return configured


def redact(value, secret_values):
    for secret in secret_values:
        if secret:
            value = value.replace(secret, '[redacted test credential]')
    return value


def execute(label, arguments, services=False):
    env = os.environ.copy()
    env.update(PYTHONPATH=str(ROOT / 'backend/src') + os.pathsep + str(ROOT / 'backend'), PYTHONIOENCODING='utf-8')
    secrets = []
    if services:
        url = owned_url()
        clear_url = url.render_as_string(hide_password=False)
        secrets = [clear_url, url.password, quote(url.password or '', safe='')]
        env.update(TEST_DATABASE_URL=clear_url, DIANZI_TEST_RUN_ID=RUN_ID, DIANZI_ENV='test', R12_OPENSEARCH_URL='http://127.0.0.1:29200', R05_SEMANTIC_CACHE='C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime', R12_EVIDENCE_DIR=str(RUN / 'synthetic_source_blobs'))
    argv = [str(PYTHON), *arguments]
    started = now()
    result = subprocess.run(argv, cwd=ROOT / 'backend', env=env, capture_output=True, timeout=300, text=True, encoding='utf-8', errors='replace')
    output = redact(result.stdout + result.stderr, secrets)
    (RUN / (label + '.log')).write_text(output, encoding='utf-8', newline='\n')
    for xml in RUN.glob('*.xml'):
        raw = xml.read_text(encoding='utf-8')
        xml.write_text(redact(raw, secrets), encoding='utf-8', newline='\n')
    write_json(RUN / (label + '.json'), {'argv': argv, 'cwd': str(ROOT / 'backend'), 'started_at': started, 'ended_at': now(), 'exit_code': result.returncode, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'code': CODE, 'resource_database': DATABASE if services else None})
    print(json.dumps({'label': label, 'exit_code': result.returncode}), flush=True)
    return result.returncode


def prepare():
    folder = RUN / 'resource_copy'
    folder.mkdir(exist_ok=True)
    proof = []
    for name in ('test_r12_production_schema.py', 'test_r12_production_indexing.py'):
        source = ROOT / 'backend/tests/integration' / name
        raw = source.read_bytes()
        fixed = subprocess.check_output(['git', 'show', CODE + ':backend/tests/integration/' + name], cwd=ROOT)
        assert raw.replace(b'\r\n', b'\n') == fixed
        (folder / (name + '.original.txt')).write_bytes(raw)
        adapted = raw.decode('utf-8').replace('test_dianzi_r12_runtime_20261016', DATABASE)
        (folder / name).write_text(adapted, encoding='utf-8', newline='\n')
        diff = ''.join(difflib.unified_diff(raw.decode('utf-8').splitlines(True), adapted.splitlines(True), fromfile='fixed/' + name, tofile='owned/' + name))
        (folder / (name + '.resource.diff')).write_text(diff, encoding='utf-8', newline='\n')
        proof.append({'path': str(source.relative_to(ROOT)), 'raw_sha256': hashlib.sha256(raw).hexdigest(), 'git_sha256': hashlib.sha256(fixed).hexdigest(), 'changed': 'database resource guard only' if 'indexing' in name else 'none'})
    write_json(RUN / 'resource_copy_proof.json', proof)


def audit():
    manifest_path = 'reports/runs/recovery_r12_runtime_integration_20261016/artifact_manifest.json'
    raw = (ROOT / manifest_path).read_bytes()
    assert hashlib.sha256(raw).hexdigest() == 'bf5aaa6bddc37a70d3a279b58546fd31e2c107775b9d3ab65ac6ff4c700b261d'
    manifest = json.loads(raw)
    entries = []
    for entry in manifest['members']:
        assert not any(name in entry['path'].split('/') for name in ('__pycache__', 'holdout'))
        actual = (ROOT / entry['path']).read_bytes()
        blob = subprocess.check_output(['git', 'show', MATERIAL + ':' + entry['path']], cwd=ROOT)
        entries.append({'path': entry['path'], 'raw_match': len(actual) == entry['bytes'] and hashlib.sha256(actual).hexdigest() == entry['sha256'], 'git_match': len(blob) == entry['bytes'] and hashlib.sha256(blob).hexdigest() == entry['sha256'], 'raw_sha256': hashlib.sha256(actual).hexdigest(), 'git_sha256': hashlib.sha256(blob).hexdigest()})
    delta = subprocess.check_output(['git', 'diff', '--name-only', 'b502b7ea4a2ffdeca24b8edc7fa8a33cc0980457', CODE], cwd=ROOT, text=True).splitlines()
    assert len(delta) == 4
    source = []
    for path in delta:
        blob = subprocess.check_output(['git', 'show', CODE + ':' + path], cwd=ROOT)
        actual = (ROOT / path).read_bytes()
        source.append({'path': path, 'git_sha256': hashlib.sha256(blob).hexdigest(), 'raw_sha256': hashlib.sha256(actual).hexdigest(), 'lf_identity': actual.replace(b'\r\n', b'\n') == blob})
    write_json(RUN / 'material_audit.json', {'at': now(), 'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'count': len(entries), 'raw_failures': sum(not e['raw_match'] for e in entries), 'git_failures': sum(not e['git_match'] for e in entries), 'members': entries, 'source': source})
    print(json.dumps({'material_count': len(entries), 'raw_failures': sum(not e['raw_match'] for e in entries), 'git_failures': sum(not e['git_match'] for e in entries)}))


def cbm():
    project = 'dianzi-r12-production-review1-20261016'
    prefix = ['wsl.exe', '-d', 'Ubuntu-22.04', '--exec', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json']
    calls = [('index', ['index_repository', '--repo-path', '/mnt/d/wt/r12-production-review1/backend/src', '--name', project, '--mode', 'fast', '--persistence', 'false']), ('schema', ['get_graph_schema', '--project', project]), ('architecture', ['get_architecture', '--project', project, '--path', 'ai_intel/retrieval', '--aspects', 'overview', '--format', 'json'])]
    for label, function, direction in [('indexer_in', 'retrieval.indexing.HybridIndexer.refresh_scope', 'inbound'), ('indexer_out', 'retrieval.indexing.HybridIndexer.refresh_scope', 'outbound'), ('migration_in', 'infrastructure.database.run_migrations', 'inbound'), ('api_out', 'api.question_routes.build_question_service', 'outbound'), ('worker_out', 'workers.runtime.consume_job', 'outbound'), ('catalog_out', 'ingestion.catalog_documents.persist_catalog_documents', 'outbound')]:
        calls.append((label, ['trace_path', '--project', project, '--function-name', project + '.ai_intel.' + function, '--direction', direction, '--depth', '2', '--max-output-tokens', '2000', '--format', 'json']))
    for label, args in calls:
        started = now()
        result = subprocess.run(prefix + args, capture_output=True, timeout=60)
        (RUN / ('cbm_' + label + '.log')).write_bytes(result.stdout + result.stderr)
        write_json(RUN / ('cbm_' + label + '.json'), {'argv': prefix + args, 'cwd': str(ROOT), 'started_at': started, 'ended_at': now(), 'exit_code': result.returncode, 'head': MATERIAL})
        print(json.dumps({'cbm': label, 'exit_code': result.returncode}), flush=True)
        if result.returncode:
            raise SystemExit(result.returncode)


def scan():
    original = credentials()
    values = [original.password, original.render_as_string(hide_password=False), original.set(database=DATABASE).render_as_string(hide_password=False), quote(original.password or '', safe='')]
    matches = []
    files = [p for p in RUN.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix != '.pyc']
    report = ROOT / 'reports/reviews/recovery/G-D-R12-production-migration-review-1.md'
    if report.exists():
        files.append(report)
    for path in files:
        raw = path.read_bytes()
        if any(value and value.encode() in raw for value in values):
            matches.append(str(path.relative_to(ROOT)))
    write_json(RUN / 'actual_secret_scan.json', {'at': now(), 'files': len(files), 'matches': matches, 'match_count': len(matches)})
    print(json.dumps({'scan_files': len(files), 'matches': len(matches)}))
    assert not matches


if __name__ == '__main__':
    mode, *args = sys.argv[1:]
    if mode in ('prepare', 'audit', 'cbm', 'scan'):
        globals()[mode]()
    else:
        services = '--services' in args
        if services:
            args.remove('--services')
        raise SystemExit(execute(mode, args, services))
