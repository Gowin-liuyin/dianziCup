"""Run frozen review commands with private test credentials and raw evidence."""

from __future__ import annotations

import importlib.metadata
import json
import os
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

WT = Path('C:/Users/yinha/.codex/worktrees/recovery-r04-sources-review-1/dianzi')
RUN = Path(__file__).resolve().parent
PYTHON = Path('D:/dianzi/backend/.venv/Scripts/python.exe')
RUN_ID = 'r04_sources_review_20261015'
DATABASE = 'test_dianzi_' + RUN_ID
TARGET = '2ff2f999b3824252d54b93af6d1da78ecb6f1427'
ZONE = timezone(timedelta(hours=8))


def now() -> str:
    return datetime.now(ZONE).isoformat(timespec='seconds')


def read_private() -> dict[str, str]:
    result = subprocess.run(
        ['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'cat',
         '/tmp/dianzi-r04_sources_20261015/connection.json'],
        capture_output=True, text=True, check=True, timeout=10,
    )
    return json.loads(result.stdout)


def secrets(source: dict[str, str]) -> list[str]:
    base = make_url(source['TEST_DATABASE_URL'])
    return [source['TEST_DATABASE_URL'], unquote(base.password or ''),
            base.set(database=DATABASE).render_as_string(hide_password=False)]


def scrub(value: str, credentials: list[str]) -> str:
    for credential in credentials:
        if credential:
            value = value.replace(credential, '[REDACTED private review connection]')
    password = credentials[1]
    if len(password) >= 8:
        for index in range(len(password) - 7):
            value = value.replace(password[index:index + 8], '[REDACTED credential fragment]')
    return value


def counts(path: Path) -> dict[str, int] | None:
    if not path.exists():
        return None
    suites = ET.parse(path).getroot()
    children = [suites] if suites.tag == 'testsuite' else list(suites)
    return {key: sum(int(suite.attrib.get(key, 0)) for suite in children)
            for key in ('tests', 'errors', 'failures', 'skipped')}


def run(label: str, command: list[str], cwd: Path, *, pg: bool = False,
        timeout: int = 180) -> int:
    if any((RUN / (label + suffix)).exists() for suffix in ('.log', '.command.json')):
        raise FileExistsError('review evidence label already exists')
    head = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=WT, text=True).strip()
    if head != TARGET:
        raise RuntimeError('frozen worktree changed')
    source = read_private()
    credentials = secrets(source)
    environment = dict(os.environ)
    environment.update(PYTHONPATH=str(WT / 'backend/src'), PYTHONUTF8='1',
                       PYTHONIOENCODING='utf-8')
    environment.pop('DATABASE_URL', None)
    environment.pop('TEST_DATABASE_URL', None)
    if pg:
        environment.update(DIANZI_TEST_RUN_ID=RUN_ID,
                           TEST_DATABASE_URL=credentials[2])
    started = now()
    clock = time.monotonic()
    completed = subprocess.run(command, cwd=cwd, env=environment, capture_output=True,
                               text=True, encoding='utf-8', errors='replace', timeout=timeout)
    ended = now()
    output = scrub(completed.stdout + completed.stderr, credentials)
    (RUN / (label + '.log')).write_text(output, encoding='utf-8')
    xml = RUN / (label + '.xml')
    if xml.exists():
        xml.write_text(scrub(xml.read_text(encoding='utf-8'), credentials), encoding='utf-8')
    receipt = {'command': command, 'cwd': str(cwd), 'started_at': started, 'ended_at': ended,
               'duration_seconds': round(time.monotonic() - clock, 6),
               'exit_code': completed.returncode, 'test_counts': counts(xml),
               'head': head, 'tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'],
                   cwd=WT, text=True).strip(), 'python': sys.version,
               'versions': {name: importlib.metadata.version(name) for name in
                            ('pytest', 'pytest-cov', 'ruff', 'mypy', 'sqlalchemy', 'psycopg')},
               'pg_database_scope': DATABASE if pg else None,
               'other_database_migrated': False}
    (RUN / (label + '.command.json')).write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))
    print(output[-1600:])
    return completed.returncode


def db_create() -> None:
    started = now()
    source = read_private()
    url = make_url(source['TEST_DATABASE_URL'])
    assert url.host == '127.0.0.1' and url.port == 25432
    assert url.database == 'test_dianzi_r04_sources_20261015'
    engine = create_engine(url, isolation_level='AUTOCOMMIT', connect_args={'connect_timeout': 5})
    with engine.connect() as connection:
        existing = connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'),
                                     {'name': DATABASE})
        if existing is not None:
            raise RuntimeError('dedicated review database already exists')
        connection.execute(text(f'CREATE DATABASE "{DATABASE}"'))
        version = connection.scalar(text('SHOW server_version'))
    engine.dispose()
    receipt = {'command': 'CREATE DATABASE dedicated review database via private connection',
               'database': DATABASE, 'server_version': version, 'started_at': started,
               'ended_at': now(), 'exit_code': 0, 'migrations': 'none',
               'other_database_migrated': False, 'cwd': str(WT)}
    (RUN / 'database_create.command.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))


def db_release() -> None:
    source = read_private()
    url = make_url(source['TEST_DATABASE_URL'])
    assert DATABASE == 'test_dianzi_r04_sources_review_20261015'
    engine = create_engine(url, isolation_level='AUTOCOMMIT', connect_args={'connect_timeout': 5})
    started = now()
    with engine.connect() as connection:
        active = connection.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=:name'),
                                   {'name': DATABASE})
        if active:
            raise RuntimeError('dedicated review database still has active sessions')
        connection.execute(text(f'DROP DATABASE "{DATABASE}"'))
    engine.dispose()
    receipt = {'database': DATABASE, 'started_at': started, 'ended_at': now(), 'exit_code': 0,
               'command': 'DROP DATABASE verified exact dedicated review database after tests',
               'cwd': str(WT), 'other_database_touched': False}
    (RUN / 'database_release.command.json').write_text(json.dumps(receipt, indent=2), encoding='utf-8')
    print(json.dumps(receipt))


def main() -> int:
    mode = sys.argv[1]
    if mode == 'create':
        db_create()
        return 0
    if mode == 'release':
        db_release()
        return 0
    label = sys.argv[2]
    if re.fullmatch(r'[a-z0-9_]{1,60}', label) is None:
        raise ValueError('invalid label')
    if mode == 'cbm':
        command = ['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'env',
                   'XDG_CACHE_HOME=/tmp/dianzi-cbm-r04-sources-review-1-20261015',
                   '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp',
                   'cli', *sys.argv[3:]]
        return run(label, command, WT)
    if mode == 'shell':
        return run(label, ['powershell.exe', '-NoProfile', '-Command', sys.argv[3]], WT)
    command = [str(PYTHON), '-m']
    if mode == 'unit':
        command += ['pytest', 'tests/unit', '-q', f'--junitxml={RUN / (label + ".xml")}',
                    f'--cov-report=json:{RUN / (label + ".coverage.json")}']
    elif mode == 'target':
        command += ['pytest', 'tests/unit/test_r04_nvd_actual_schema.py',
                    'tests/unit/test_r04_vendor_advisories.py',
                    'tests/contract/test_t10_cve_nvd_connectors.py',
                    'tests/contract/test_t12_vendor_blog_connectors.py',
                    'tests/contract/test_t13_community_repository_connectors.py',
                    '-q', '--no-cov', f'--junitxml={RUN / (label + ".xml")}']
    elif mode == 'pg':
        command += ['pytest', 'tests/integration/test_r04_revision_metadata.py',
                    'tests/integration/test_r02_schema_migration.py',
                    'tests/integration/test_t05_persistence_and_raw_store.py',
                    '-q', '--no-cov', f'--junitxml={RUN / (label + ".xml")}']
    elif mode in ('ruff', 'format'):
        command += ['ruff', 'check' if mode == 'ruff' else 'format']
        if mode == 'format':
            command += ['--check']
        command += ['src/ai_intel/ingestion/sources/nvd.py',
                    'src/ai_intel/ingestion/sources/vendor_advisories.py',
                    'src/ai_intel/knowledge/models.py', 'src/ai_intel/knowledge/revisions.py',
                    'migrations/versions/0013_revision_source_metadata.py',
                    'tests/unit/test_r04_nvd_actual_schema.py',
                    'tests/unit/test_r04_vendor_advisories.py',
                    'tests/contract/test_t10_cve_nvd_connectors.py',
                    'tests/integration/test_r04_revision_metadata.py',
                    'tests/integration/test_r02_schema_migration.py']
    elif mode == 'mypy':
        command += ['mypy', 'src/ai_intel']
    elif mode == 'independent':
        command += ['pytest', str(RUN / 'test_independent_boundaries.py'),
                    '-q', '--no-cov', f'--junitxml={RUN / (label + ".xml")}']
    else:
        raise ValueError('unsupported mode')
    return run(label, command, WT / 'backend', pg=mode in ('pg', 'independent'))


if __name__ == '__main__':
    raise SystemExit(main())
