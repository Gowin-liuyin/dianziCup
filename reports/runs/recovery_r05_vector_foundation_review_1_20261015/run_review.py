"""Run frozen review commands and save redacted receipts without exposing connection secrets."""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
WORKTREE = Path('C:/Users/yinha/.codex/worktrees/recovery-r05-vector-foundation-review-1/dianzi')
BACKEND = WORKTREE / 'backend'
PYTHON = Path('D:/dianzi/backend/.venv/Scripts/python.exe')


def run(name: str, argv: list[str], *, pg: bool = False, live: bool = False, cwd: Path = BACKEND) -> int:
    child_env = dict(os.environ)
    child_env['PYTHONPATH'] = str(BACKEND / 'src')
    child_env['PYTHONDONTWRITEBYTECODE'] = '1'
    child_env['COVERAGE_FILE'] = str(ROOT / (name + '.coverage'))
    child_env['RUFF_CACHE_DIR'] = str(ROOT / 'ruff_cache')
    child_env.pop('TEST_DATABASE_URL', None)
    child_env.pop('DATABASE_URL', None)
    child_env.pop('R05_SEMANTIC_CACHE', None)
    secrets = []
    if pg:
        receipt = subprocess.run(
            ['wsl', '-u', 'root', '--exec', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json'],
            capture_output=True, check=True, text=True,
        )
        connection = json.loads(receipt.stdout)['TEST_DATABASE_URL']
        child_env['TEST_DATABASE_URL'] = connection
        child_env['DIANZI_TEST_RUN_ID'] = 'r05_pgvector_20261015'
        secrets = [connection, unquote(urlsplit(connection).password or '')]
    if live:
        child_env['R05_SEMANTIC_CACHE'] = 'C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime'
    started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    result = subprocess.run(argv, cwd=cwd, env=child_env, capture_output=True, text=True, encoding='utf-8', errors='replace')
    completed = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    output = result.stdout + '\nSTDERR:\n' + result.stderr
    for secret in secrets:
        if secret:
            output = output.replace(secret, '[redacted test credential]')
    (ROOT / (name + '.log')).write_text(output, encoding='utf-8')
    receipt = {'name': name, 'argv': argv, 'cwd': str(cwd), 'started_at': started, 'completed_at': completed,
               'exit_code': result.returncode, 'frozen_sha': 'fd01ea3e0205361c1f446d6fb97694aa3aa715cf',
               'pg_environment': pg, 'live_opt_in': live, 'python_path': child_env['PYTHONPATH']}
    (ROOT / (name + '.command.json')).write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False))
    print(output[-4000:])
    return result.returncode


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('name')
    parser.add_argument('--pg', action='store_true')
    parser.add_argument('--live', action='store_true')
    parser.add_argument('argv', nargs=argparse.REMAINDER)
    args = parser.parse_args()
    argv = args.argv[1:] if args.argv and args.argv[0] == '--' else args.argv
    raise SystemExit(run(args.name, argv, pg=args.pg, live=args.live))
