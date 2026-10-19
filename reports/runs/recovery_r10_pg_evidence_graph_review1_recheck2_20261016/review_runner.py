"""Run reviewer commands with private PostgreSQL credentials only in environment."""

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path('D:/wt/r10-graph-recheck2')
RUN = Path(__file__).resolve().parent
PYTHON = ROOT / 'backend/.venv/Scripts/python.exe'
DBNAME = 'test_dianzi_r06_catalog_r10_review3_20261016'
RUNID = 'r06_catalog_r10_review3_20261016'


def run(label, args, cwd=ROOT, env=None):
    started = datetime.datetime.now().astimezone().isoformat()
    result = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    output = result.stdout + result.stderr
    if env and env.get('TEST_DATABASE_URL'):
        from sqlalchemy.engine import make_url
        url = env['TEST_DATABASE_URL']
        output = output.replace(url, '[redacted test connection]')
        password = make_url(url).password
        if password:
            output = output.replace(password, '[redacted test credential]')
    (RUN / f'{label}.log').write_text(output, encoding='utf-8')
    receipt = {'command': [str(arg) for arg in args], 'cwd': str(cwd), 'started_at': started, 'finished_at': datetime.datetime.now().astimezone().isoformat(), 'exit_code': result.returncode, 'code_sha': '08b141bd437c1de70a8435a1f7f6c448a131ed0d'}
    (RUN / f'{label}.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(label, 'exit', result.returncode)
    print(output[-2500:])
    return result.returncode


if __name__ == '__main__':
    label, command, *args = sys.argv[1:]
    environment = os.environ.copy()
    environment['PYTHONIOENCODING'] = 'utf-8'
    environment['PYTHONPATH'] = str(RUN) + os.pathsep + str(ROOT / 'backend/src') + os.pathsep + str(ROOT / 'backend/tests/integration')
    environment['R10_OBSERVATIONS_PATH'] = str(RUN / (label + '_observations.jsonl'))
    temporary = RUN / 'temporary_fixture_objects'
    temporary.mkdir(exist_ok=True)
    environment['TEMP'] = str(temporary)
    environment['TMP'] = str(temporary)
    if command == 'pgpytest':
        from sqlalchemy import create_engine, text
        from sqlalchemy.engine import make_url
        raw = subprocess.run(['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'], capture_output=True, check=True, text=True).stdout
        private = json.loads(raw)
        original_url = make_url(private['TEST_DATABASE_URL'])
        assert original_url.host in ('localhost', '127.0.0.1')
        assert original_url.database.startswith('test_dianzi_')
        assert original_url.username.startswith('test_')
        assert original_url.database != DBNAME
        base = create_engine(original_url, isolation_level='AUTOCOMMIT', connect_args={'connect_timeout': 5})
        with base.connect() as connection:
            assert connection.scalar(text('SELECT current_database()')) == original_url.database
            if not connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': DBNAME}):
                connection.exec_driver_sql('CREATE DATABASE "' + DBNAME + '"')
        base.dispose()
        target = original_url.set(database=DBNAME)
        engine = create_engine(target, connect_args={'connect_timeout': 5})
        with engine.connect() as connection:
            actual_db, actual_user = connection.execute(text('SELECT current_database(), current_user')).one()
            assert actual_db == DBNAME and actual_user == target.username
        engine.dispose()
        environment['TEST_DATABASE_URL'] = target.render_as_string(hide_password=False)
        environment['DIANZI_TEST_RUN_ID'] = RUNID
        environment['DIANZI_TEST_ISOLATION'] = 'container'
        command = 'pytest'
    if command == 'pytest':
        command_args = [str(PYTHON), '-m', 'pytest', '-o', 'addopts=', '-v', *args, f'--junitxml={RUN / (label + ".xml")}']
        sys.exit(run(label, command_args, ROOT / 'backend', environment))
    if command == 'cbm':
        sys.exit(run(label, ['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--', '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', *args], env=environment))
    if command == 'python':
        sys.exit(run(label, [str(PYTHON), *args], ROOT / 'backend', environment))
    if command == 'module':
        sys.exit(run(label, [str(PYTHON), '-m', *args], ROOT / 'backend', environment))

