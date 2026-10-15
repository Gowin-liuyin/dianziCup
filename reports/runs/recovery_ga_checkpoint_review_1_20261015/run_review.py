"""Run bounded independent checks without persisting private connection material."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(os.environ.get('GA_REVIEW_WORKTREE', 'D:/dianzi-ga-checkpoint-review-1'))
RUN = Path('D:/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
RUN_ID = 'ga_checkpoint_review_20261015'
DATABASE = 'test_dianzi_' + RUN_ID


def now() -> str:
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def private_json(path: str) -> dict[str, str]:
    result = subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--', 'cat', path], capture_output=True, timeout=10, check=True)
    return json.loads(result.stdout)


def main() -> int:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    import psycopg
    from psycopg import sql
    from sqlalchemy.engine import make_url

    label, mode, *command = sys.argv[1:]
    environment = dict(os.environ)
    coverage_root = Path(os.environ['TEMP']) / 'dianzi_ga_checkpoint_review_1_20261015' / 'coverage'
    coverage_root.mkdir(parents=True, exist_ok=True)
    environment.update(COVERAGE_FILE=str(coverage_root / (label + '.coverage')), PYTHONIOENCODING='utf-8', UV_PROJECT_ENVIRONMENT=str(ROOT / 'backend/.venv'))
    secrets = []
    if mode in {'pg', 'minio', 'worker'}:
        connection = private_json('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json')
        base_url = make_url(connection['TEST_DATABASE_URL'])
        assert base_url.host == '127.0.0.1' and base_url.port == 25432
        assert base_url.database == 'test_dianzi_r01_20261014'
        base_dsn = base_url.set(drivername='postgresql').render_as_string(hide_password=False)
        with psycopg.connect(base_dsn, autocommit=True) as client:
            exists = client.execute('SELECT 1 FROM pg_database WHERE datname=%s', (DATABASE,)).fetchone()
            if exists is None:
                client.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(DATABASE)))
        environment.update(TEST_DATABASE_URL=base_url.set(database=DATABASE).render_as_string(hide_password=False), DIANZI_TEST_RUN_ID=RUN_ID, TEST_REDIS_URL=connection['TEST_REDIS_URL'].rsplit('/', 1)[0] + '/10')
        if mode == 'worker':
            environment['DATABASE_URL'] = environment['TEST_DATABASE_URL']
            environment['REDIS_URL'] = environment['TEST_REDIS_URL']
            environment.update(APP_ENV='test', DATA_MODE='fixture')
        secrets += list(connection.values()) + [base_url.password or '', environment['TEST_DATABASE_URL'], environment['TEST_REDIS_URL']]
    if mode == 'minio':
        store = private_json('/tmp/dianzi-minio-r02-20261015/private/connection.json')
        environment.update(TEST_MINIO_ENDPOINT=store['endpoint'], TEST_MINIO_ACCESS_KEY=store['access_key'], TEST_MINIO_SECRET_KEY=store['secret_key'], TEST_MINIO_BUCKET='test-dianzi-r02-ga-checkpoint-review-20261015')
        secrets += list(store.values())
    started = now()
    try:
        result = subprocess.run(command, cwd=ROOT / 'backend', env=environment, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=540)
        output = result.stdout + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = str(error.stdout or '') + str(error.stderr or '')
        code = 124
    for secret in sorted({value for value in secrets if isinstance(value, str)}, key=len, reverse=True):
        if secret:
            output = output.replace(secret, '[redacted connection credential]')
    (RUN / (label + '.log')).write_text(output, encoding='utf-8')
    receipt = dict(label=label, cwd=str(ROOT / 'backend'), command=command, started_at=started, ended_at=now(), exit_code=code, database=DATABASE if mode in {'pg','minio','worker'} else None)
    (RUN / (label + '.command.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))
    print(output[-2500:])
    return code


if __name__ == '__main__':
    raise SystemExit(main())
