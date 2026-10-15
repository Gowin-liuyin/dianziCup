"""Independent fixed-SHA checks; credentials stay in process environment only."""
import difflib
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

WT = Path('/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review/dianzi')
RUN = Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015')
UV = '/tmp/dianzi-r01-tls-prefix-runtime-20261015/uv'
DB = 'test_dianzi_r04_pipeline_review_20261015'
VENV = '/tmp/dianzi-r04-pipeline-review-20261015/venv'
GIT = ['git', '--git-dir', '/mnt/d/dianzi/.git/worktrees/dianzi43', '--work-tree', str(WT)]

def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')

def main():
    label, group = sys.argv[1:]
    receipt_path = RUN / (label + '.command.json')
    if receipt_path.exists():
        raise FileExistsError('label already exists')
    private = json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
    root_url = make_url(private['TEST_DATABASE_URL'])
    assert root_url.host == '127.0.0.1' and root_url.port == 25432
    admin = create_engine(root_url, isolation_level='AUTOCOMMIT')
    with admin.connect() as connection:
        if connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': DB}) is None:
            connection.execute(text(f'CREATE DATABASE "{DB}"'))
    admin.dispose()
    url = root_url.set(database=DB).render_as_string(hide_password=False)
    environment = dict(os.environ)
    environment.update(TEST_DATABASE_URL=url, DIANZI_TEST_RUN_ID='r04_pipeline_review_20261015',
        PYTHONUTF8='1', PYTHONIOENCODING='utf-8', UV_PROJECT_ENVIRONMENT=VENV,
        PYTHONPATH=str(RUN / 'testcopy') + ':' + str(WT / 'backend/tests/integration') + ':' + str(WT / 'backend/src'),
        COVERAGE_FILE='/tmp/dianzi-r04-pipeline-review-20261015/' + label + '.coverage')
    copied = RUN / 'testcopy'
    copied.mkdir(exist_ok=True)
    adaptations = []
    targets = ['conftest.py','integration/test_r04_source_documents.py','integration/test_r04_knowledge_api_pg.py','integration/test_r04_api_review_regressions.py']
    for relative in targets:
        source_path = WT / 'backend/tests' / relative
        original = source_path.read_text()
        adapted = original.replace('test_dianzi_r04_source_documents_20261015', DB).replace('test_dianzi_r04_api_20261015', DB)
        adapted = adapted.replace('PROJECT_ROOT = Path(__file__).resolve().parents[2]', f'PROJECT_ROOT = Path({str(WT)!r})')
        adapted = adapted.replace('FIXTURES = Path(__file__).resolve().parents[3] / "fixtures/recorded"', f'FIXTURES = Path({str(WT / "fixtures/recorded")!r})')
        destination = copied / source_path.name
        destination.write_text(adapted)
        adaptations.append({'source': str(source_path), 'copy': str(destination),
            'original_sha256': hashlib.sha256(original.encode()).hexdigest(),
            'copy_sha256': hashlib.sha256(adapted.encode()).hexdigest()})
        (RUN / (source_path.stem + '.adaptation.diff')).write_text(''.join(difflib.unified_diff(original.splitlines(True), adapted.splitlines(True), fromfile=str(source_path), tofile=str(destination))))
    (RUN / 'test_adaptations.json').write_text(json.dumps(adaptations, indent=2))
    groups = {
        'unit': ['tests/unit'],
        'sourcepg': [str(copied / 'test_r04_source_documents.py')],
        'jobpg': ['tests/integration/test_r04_source_jobs_pg.py','tests/integration/test_r03_jobs_pg.py'],
        'apipg': [str(copied / 'test_r04_knowledge_api_pg.py'),str(copied / 'test_r04_api_review_regressions.py')],
        'negative': [str(RUN / 'testcopy/test_pipeline_negatives.py')],
        'contracts': ['tests/contract/test_t09_document_parsing.py','tests/contract/test_t10_cve_nvd_connectors.py','tests/contract/test_t12_vendor_blog_connectors.py','tests/unit/test_t17_relevance_and_event_linking.py'],
        'actual_vendor': [str(RUN / 'testcopy/test_actual_vendor_page.py')],
        'shared': ['tests/integration/test_r04_review_regressions.py'],
    }
    if group == 'static':
        commands = [[UV,'run','--locked','ruff','check','src','tests/unit/test_r04_source_documents.py','tests/unit/test_r04_source_jobs.py','tests/integration/test_r04_source_documents.py','tests/integration/test_r04_source_jobs_pg.py','tests/integration/test_r04_api_review_regressions.py'],
            [UV,'run','--locked','ruff','format','--check','src','tests/unit/test_r04_source_documents.py','tests/unit/test_r04_source_jobs.py','tests/integration/test_r04_source_documents.py','tests/integration/test_r04_source_jobs_pg.py','tests/integration/test_r04_api_review_regressions.py'],
            [UV,'run','--locked','mypy','src']]
    else:
        commands = [[UV,'run','--locked','pytest',*groups[group],'-q',f'--junitxml={RUN / (label + ".xml")}']]
        commands[0] += [f'--cov-report=json:{RUN / (label + ".coverage.json")}'] if group == 'unit' else ['--no-cov']
    receipts=[]
    for index, command in enumerate(commands):
        started=now()
        result=subprocess.run(command,cwd=WT / 'backend',env=environment,capture_output=True,text=True,errors='replace',timeout=360)
        output=result.stdout+result.stderr
        for secret in (url,unquote(root_url.password or '')):
            if secret:
                output=output.replace(secret,'[REDACTED]')
        suffix='' if len(commands)==1 else '_' + str(index + 1)
        (RUN / (label+suffix+'.log')).write_text(output)
        receipts.append({'command':command,'cwd':str(WT / 'backend'),'started_at':started,'ended_at':now(),'exit_code':result.returncode})
        print(output[-1800:])
    counts=None
    if (RUN / (label+'.xml')).exists():
        suites=ElementTree.parse(RUN / (label+'.xml')).getroot()
        counts={name:sum(int(suite.get(name,0)) for suite in suites.iter('testsuite')) for name in ('tests','failures','errors','skipped')}
    receipt={'commands':receipts,'counts':counts,'database_scope':DB,'other_database_migrated':False,
        'head':subprocess.check_output([*GIT,'rev-parse','HEAD'],cwd=WT,text=True).strip(),
        'tree':subprocess.check_output([*GIT,'rev-parse','HEAD^{tree}'],cwd=WT,text=True).strip(),
        'working_diff_sha256':hashlib.sha256(subprocess.check_output([*GIT,'diff','--binary'],cwd=WT)).hexdigest(),
        'coverage_file':environment['COVERAGE_FILE'],'source_state':'fixed candidate; originals unchanged; copied fixtures exact resource adaptations'}
    receipt_path.write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))
    return max(item['exit_code'] for item in receipts)

if __name__ == '__main__':
    raise SystemExit(main())
