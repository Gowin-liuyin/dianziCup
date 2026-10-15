"""Independent fixed-candidate review; secrets remain in memory and child environment."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

RUN = Path(__file__).resolve().parent
ROOT = Path('D:/dianzi')
WT = Path('C:/Users/yinha/.codex/worktrees/recovery-r02-minio-review/dianzi')
VENV = Path('C:/Users/yinha/.codex/tmp/r02-minio-review1-venv')
SHA = '60fe4c311f98a0692e2207b884d83b676f5fb9c2'


def now() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')


def private(path: str) -> dict[str, str]:
    completed = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                                'cat', path], capture_output=True, text=True, timeout=10)
    if completed.returncode:
        raise RuntimeError('blocked: designated private resource connection unreadable')
    return json.loads(completed.stdout)


def main() -> int:
    label, mode, *args = sys.argv[1:]
    if (RUN / (label + '.command.json')).exists():
        raise FileExistsError('review evidence label already exists')
    env = dict(os.environ, UV_PROJECT_ENVIRONMENT=str(VENV), PYTHONUTF8='1',
               PYTHONIOENCODING='utf-8', PYTHONDONTWRITEBYTECODE='1')
    env['PYTHONPATH'] = os.pathsep.join(str(path) for path in
        (WT / 'backend/src', WT / 'backend/tests', WT / 'backend/tests/integration'))
    sensitive: set[str] = set()
    if mode in ('pytest', 'script'):
        pg = private('/tmp/dianzi-r02_knowledge_20261015/connection.json')
        objects = private('/tmp/dianzi-minio-r02-20261015/private/connection.json')
        env.update(TEST_DATABASE_URL=pg['TEST_DATABASE_URL'], DIANZI_TEST_RUN_ID='r02_knowledge_20261015',
                   TEST_MINIO_ENDPOINT=objects['endpoint'],
                   TEST_MINIO_BUCKET='test-dianzi-r02-review1-20261015',
                   TEST_MINIO_ACCESS_KEY=objects['access_key'], TEST_MINIO_SECRET_KEY=objects['secret_key'])
        sensitive = {pg['TEST_DATABASE_URL'], objects['access_key'], objects['secret_key'],
                     unquote(urlsplit(pg['TEST_DATABASE_URL']).password or '')}
        sensitive.discard('')
        sensitive.update(value[index:index+8] for value in list(sensitive)
                         for index in range(len(value)-7))

    def redact(value: str) -> str:
        for credential in sorted(sensitive, key=len, reverse=True):
            value = value.replace(credential, '[review secret redacted]')
        return value

    with tempfile.TemporaryDirectory(prefix='r02-review-junit-') as temporary:
        xml_path = Path(temporary) / 'review.xml'
        if mode == 'sync':
            command = ['uv', 'sync', '--locked']
        elif mode == 'pytest':
            command = ['uv', 'run', '--locked', 'pytest', *args, f'--junitxml={xml_path}', '-q']
        elif mode == 'script':
            command = ['uv', 'run', '--locked', 'python', *args]
        elif mode == 'cbm':
            source = '/mnt/c/Users/yinha/.codex/worktrees/recovery-r02-minio-review/dianzi/backend/src'
            command = ['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'env',
                       'CBM_CACHE_DIR=/tmp/dianzi-cbm-r02-minio-review1-20261015',
                       'CBM_ALLOWED_ROOT=' + source,
                       '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp', 'cli', '--json', *args]
        else:
            command = ['uv', 'run', '--locked', *args]
        started = now()
        completed = subprocess.run(command, cwd=WT / 'backend', env=env, capture_output=True,
                                   text=True, encoding='utf-8', errors='replace', timeout=300)
        stdout, stderr = redact(completed.stdout), redact(completed.stderr)
        (RUN / (label + '.stdout.log')).write_text(stdout, encoding='utf-8')
        (RUN / (label + '.stderr.log')).write_text(stderr, encoding='utf-8')
        counts = None
        if xml_path.exists():
            raw_xml = xml_path.read_text(encoding='utf-8')
            xml_value = redact(raw_xml)
            (RUN / (label + '.xml')).write_text(xml_value, encoding='utf-8')
            suites = ET.fromstring(xml_value).iter('testsuite')
            counts = dict.fromkeys(('tests', 'failures', 'errors', 'skipped'), 0)
            for suite in suites:
                for key in counts:
                    counts[key] += int(suite.get(key, '0'))
        record = {'started_at': started, 'ended_at': now(), 'exit_code': completed.returncode,
                  'command': [item if not item.startswith('--junitxml=') else '--junitxml=<temporary in-memory-checked copy>' for item in command],
                  'cwd': str(WT / 'backend'), 'candidate_sha': SHA,
                  'candidate_tree': subprocess.check_output(['git', 'rev-parse', 'HEAD^{tree}'], cwd=WT, text=True).strip(),
                  'database_scope': 'r02_knowledge_20261015/head0009',
                  'object_scope': 'test-dianzi-r02-review1-20261015', 'counts': counts,
                  'known_secret_match_after_sanitization': any(value in stdout+stderr for value in sensitive)}
        (RUN / (label + '.command.json')).write_text(json.dumps(record, indent=2), encoding='utf-8')
        print(json.dumps(record))
        print(stdout[-1200:])
        print(stderr[-600:])
        return completed.returncode


if __name__ == '__main__':
    raise SystemExit(main())
