"""独立审查命令、隔离输入和脱敏收据；不改作者材料。"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
PYTHON = 'D:/dianzi/backend/.venv/Scripts/python.exe'


def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()


def secret_values():
    result = subprocess.run([
        'C:/Users/yinha/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe',
        '-NoProfile', '-Command',
        "$reviewProtected=Get-Content -LiteralPath 'D:/dianzi-private/test-runtime-resource-reference-20261016.dpapi' -Raw; "
        "$reviewClear=$reviewProtected | ConvertTo-SecureString | ConvertFrom-SecureString -AsPlainText; [Console]::Write($reviewClear)"
    ], capture_output=True, check=True, timeout=15)
    configured = json.loads(result.stdout)['TEST_DATABASE_URL']
    url = make_url(configured)
    assert (url.host, url.port, url.database) == ('127.0.0.1', 25432, 'test_dianzi_r01_20261014')
    assert url.username.startswith('test_')
    return configured, url.password


def main():
    label, *arguments = sys.argv[1:]
    services = '--services' in arguments
    if services:
        arguments.remove('--services')
    environment = os.environ.copy()
    environment.update(PYTHONPATH=os.pathsep.join((str(RUN), str(ROOT/'backend/src'), str(ROOT))), PYTHONIOENCODING='utf-8')
    configured, password = secret_values()
    if services:
        environment.update(TEST_DATABASE_URL=configured, DIANZI_TEST_RUN_ID='r01_20261014', DIANZI_ENV='test')
    started = now()
    result = subprocess.run(arguments, cwd=ROOT/'backend', env=environment, capture_output=True, text=True, encoding='utf-8', errors='replace', timeout=600)
    raw = result.stdout + result.stderr
    scans = []
    values = [configured, password]
    for path in RUN.rglob('owned_database.json'):
        owned = json.loads(path.read_text())['database']
        values.append(make_url(configured).set(database=owned).render_as_string(hide_password=False))
    leaked = any(value and value in raw for value in values)
    for value in values:
        if value:
            raw = raw.replace(value, '[redacted test credential]')
    (RUN/(label+'.log')).write_text(raw, encoding='utf-8', newline='\n')
    for path in RUN.rglob('*.xml'):
        content = path.read_text(encoding='utf-8')
        hit = any(value and value in content for value in values)
        scans.append({'path':str(path.relative_to(RUN)), 'credential_matches':bool(hit)})
        leaked |= hit
        if hit:
            for value in values:
                if value:
                    content = content.replace(value, '[redacted test credential]')
            path.write_text(content, encoding='utf-8', newline='\n')
    receipt = {'argv':arguments,'cwd':str(ROOT/'backend'),'started_at':started,'ended_at':now(),'exit_code':result.returncode,
               'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(), 'credential_scan':{'matches':leaked,'junit':scans}}
    junit = RUN/(label+'.xml')
    if junit.exists():
        suites = ElementTree.parse(junit).getroot().findall('testsuite')
        receipt['counts']={key:sum(int(s.get(key,'0')) for s in suites) for key in ('tests','failures','errors','skipped')}
    (RUN/(label+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(receipt))
    if result.returncode:
        print(raw[-6000:])
    return result.returncode if result.returncode else (1 if leaked else 0)


if __name__=='__main__':
    raise SystemExit(main())
