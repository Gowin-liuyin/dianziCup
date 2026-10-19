"""Run independent review checks with credentials confined to process environments."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
PYTHON = Path('D:/dianzi/backend/.venv/Scripts/python.exe')
ZONE = timezone(timedelta(hours=8))
RECEIPTS = RUN / 'commands.json'


def now():
    return datetime.now(ZONE).isoformat(timespec='seconds')


def credentials():
    result = subprocess.run(['wsl', '-u', 'root', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'], capture_output=True, text=True, check=True)
    values = json.loads(result.stdout)
    from sqlalchemy.engine import make_url
    url = make_url(values['TEST_DATABASE_URL']).set(database='test_dianzi_r06_catalog_polling_20261015')
    return values, url.render_as_string(hide_password=False)


def main():
    label = sys.argv[1]
    command = sys.argv[2:]
    environment = dict(os.environ, PYTHONPATH=str(ROOT/'backend/src') + os.pathsep + str(ROOT), RAW_CONTENT_DIRECTORY=str(RUN/'raw'), PYTHONDONTWRITEBYTECODE='1')
    secrets = []
    if label.startswith(('pg', 'broker')):
        values, url = credentials()
        environment.update(TEST_DATABASE_URL=url, DIANZI_TEST_RUN_ID='r06_catalog_polling_20261015', TEST_REDIS_URL=values['TEST_REDIS_URL'], NO_PROXY=values['NO_PROXY'])
        secrets.extend([values['postgres_password'], values['redis_password'], values['TEST_DATABASE_URL'], values['TEST_REDIS_URL'], url])
    started = now()
    result = subprocess.run(command, cwd=ROOT/'backend', env=environment, capture_output=True, text=True, timeout=360)
    output = result.stdout + result.stderr
    for secret in sorted(secrets, key=len, reverse=True):
        output = output.replace(secret, '[redacted review credential]')
    (RUN/(label+'.log')).write_text(output, encoding='utf-8')
    receipt = {'label':label, 'command':command, 'cwd':str(ROOT/'backend'), 'started_at':started, 'ended_at':now(), 'exit_code':result.returncode, 'log':label+'.log'}
    previous = json.loads(RECEIPTS.read_text()) if RECEIPTS.exists() else []
    RECEIPTS.write_text(json.dumps(previous+[receipt], ensure_ascii=False, indent=2), encoding='utf-8')
    (RUN/(label+'.command.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))
    print('\n'.join(output.splitlines()[-12:]))
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
