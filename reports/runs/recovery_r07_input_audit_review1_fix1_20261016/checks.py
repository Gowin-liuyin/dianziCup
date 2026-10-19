"""Independent checks retain raw failures with an owned test database and exact-value scans."""

import html
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import quote
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = Path('D:/dianzi/backend/.venv/Scripts/python.exe')
RUN_ID = 'r07_audit_review1_fix1_261016'
DATABASE = 'test_dianzi_' + RUN_ID
OWNER = 'independent-review1-fix1:r07:648c71795e1bea34511ec0d04348f35f6463a5e6'
TIMEZONE = ZoneInfo('Asia/Shanghai')


def now():
    return datetime.now(TIMEZONE).isoformat(timespec='seconds')


def original_resource():
    command = ['C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe', '-NoProfile', '-Command', "$taskProtected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; $taskClear=$taskProtected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($taskClear)"]
    protected = subprocess.run(command, capture_output=True, timeout=15, check=True)
    resource = json.loads(protected.stdout)
    original = make_url(resource['TEST_DATABASE_URL'])
    assert original.drivername == 'postgresql+psycopg'
    assert (original.host, original.port, original.database) == ('127.0.0.1', 25432, 'test_dianzi_r01_20261014')
    assert original.username and original.username.startswith('test_') and original.password
    assert datetime.now(TIMEZONE) < datetime.fromisoformat('2026-10-17T21:49:15+08:00')
    return original


def own_resource(original):
    marker = RUN / 'owned_database_v2.json'
    engine = create_engine(original, isolation_level='AUTOCOMMIT', hide_parameters=True)
    try:
        with engine.connect() as connection:
            existing = connection.execute(text("SELECT shobj_description(oid,'pg_database') AS marker, pg_get_userbyid(datdba) AS owner FROM pg_database WHERE datname=:name"), {'name': DATABASE}).mappings().one_or_none()
            if existing is None:
                assert not marker.exists()
                connection.exec_driver_sql('CREATE DATABASE "' + DATABASE + '"')
                connection.exec_driver_sql('COMMENT ON DATABASE "' + DATABASE + "\" IS '" + OWNER + "'")
                marker.write_bytes(json.dumps({'database': DATABASE, 'marker': OWNER}, indent=2).encode())
            else:
                assert marker.exists() and json.loads(marker.read_bytes()) == {'database': DATABASE, 'marker': OWNER}
                assert existing['marker'] == OWNER and existing['owner'] == original.username
    finally:
        engine.dispose()
    return original.set(database=DATABASE)


def scan_values(raw, original, configured):
    identities = [('original_dsn', original.render_as_string(hide_password=False)), ('configured_dsn', configured.render_as_string(hide_password=False)), ('password', original.password)]
    findings = []
    for label, value in identities:
        variants = {value, html.escape(value), quote(value, safe=''), json.dumps(value)[1:-1]}
        matches = sum(raw.count(variant.encode()) for variant in variants if variant)
        if matches:
            findings.append({'kind': label, 'matches': matches})
    username_hits = raw.count(original.username.encode())
    return {'secret_matches': findings, 'username_matches': username_hits}


def execute(label, arguments, services=False, cwd=None):
    environment = os.environ.copy()
    environment.update(PYTHONPATH=os.pathsep.join(map(str, (ROOT / 'backend/src', ROOT / 'backend/tests', ROOT / 'backend/tests/integration', ROOT, RUN))), PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1', DIANZI_ENV='test')
    if label == 'baseline_nvd':
        environment['DIANZI_REVIEW_BASELINE'] = '1'
    original = configured = None
    if services:
        original = original_resource()
        configured = own_resource(original)
        environment.update(TEST_DATABASE_URL=configured.render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID)
    started = now()
    argv = [str(PYTHON), *arguments]
    working = cwd or ROOT / 'backend'
    result = subprocess.run(argv, cwd=working, env=environment, capture_output=True, timeout=600)
    combined = result.stdout + result.stderr
    scans = {}
    if services:
        credential_prefix = ('postgresql+psycopg://' + original.username + ':').encode()
        combined = combined.replace(credential_prefix, b'postgresql+psycopg://[redacted test username]:')
        scans['log'] = scan_values(combined, original, configured)
        assert not scans['log']['secret_matches'], 'secret detected; raw output withheld'
    log = RUN / (label + '.log')
    log.write_bytes(combined)
    xml = RUN / (label + '.xml')
    if services and xml.exists():
        xml.write_bytes(xml.read_bytes().replace(credential_prefix, b'postgresql+psycopg://[redacted test username]:'))
        scans['junit'] = scan_values(xml.read_bytes(), original, configured)
        assert not scans['junit']['secret_matches'], 'secret detected in JUnit'
    suites = [] if not xml.exists() else list(ElementTree.parse(xml).getroot().iter('testsuite'))
    counts = {name: sum(int(suite.attrib.get(name, '0')) for suite in suites) for name in ('tests', 'failures', 'errors', 'skipped')}
    receipt = {'argv': argv, 'cwd': str(working), 'started_at': started, 'ended_at': now(), 'exit_code': result.returncode, 'counts': counts, 'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(), 'exact_value_scans': scans, 'resource': DATABASE if services else None}
    (RUN / (label + '.json')).write_bytes(json.dumps(receipt, indent=2).encode())
    print(json.dumps({'label': label, 'exit_code': result.returncode, 'counts': counts, 'exact_value_scans': scans}), flush=True)
    return result.returncode


if __name__ == '__main__':
    label, *arguments = sys.argv[1:]
    services = '--services' in arguments
    if services:
        arguments.remove('--services')
    raise SystemExit(execute(label, arguments, services))
