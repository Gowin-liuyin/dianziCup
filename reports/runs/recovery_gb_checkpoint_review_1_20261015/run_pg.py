import json
import os
from pathlib import Path
import subprocess
import sys
from uuid import uuid4

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from run_command import run, now

ROOT = Path(os.environ.get('GB_REVIEW_WORKTREE','D:/wt/gb-stage-review'))
RUN = Path(__file__).parent
private = subprocess.run(['wsl','-d','Ubuntu-22.04','-u','root','--exec','cat','/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json'],capture_output=True,text=True,check=True,timeout=15)
base = make_url(json.loads(private.stdout)['TEST_DATABASE_URL'])
assert base.database == 'test_dianzi_r05_pgvector_20261015'
label = sys.argv[1]
mode = label.split('__')[0]
environment = dict(os.environ)
if mode in {'vector_question','question_probes','deleted_evidence'}:
    database = base.database
    cases = ['tests/integration/test_r05_vector_persistence.py','tests/integration/test_r05_question_api_pg.py'] if mode == 'vector_question' else ['-p','conftest',str(RUN / ('test_review_recheck.py' if mode == 'question_probes' else 'test_review_deleted_evidence.py'))]
elif mode in {'source_details','knowledge_api','source_idempotency','source_auth_lock','source_formal'}:
    database = json.loads((RUN / 'pg_allocation.json').read_text(encoding='utf-8'))['database']
    external_test = {'source_details':'test_review_source.py','knowledge_api':'test_review_knowledge_api.py','source_idempotency':'test_review_source_idempotency.py','source_auth_lock':'test_review_source_auth_lock.py','source_formal':'test_review_source_formal.py'}[mode]
    cases = ['-p','conftest',str(RUN / external_test)]
else:
    database = 'test_dianzi_gb_stage_review_20261015_' + uuid4().hex[:8]
    with create_engine(base,isolation_level='AUTOCOMMIT').connect() as connection:
        assert connection.scalar(text('SELECT current_database()')) == base.database
        assert not connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name':database})
        connection.execute(text('CREATE DATABASE "' + database + '"'))
    (RUN / 'pg_allocation.json').write_text(json.dumps({'created_at':now(),'database':database,'old_ga_db_touched':False,'removed_or_downgraded':False},indent=2),encoding='utf-8')
    cases = ['tests/integration/test_r04_source_jobs_pg.py','tests/integration/test_r04_revision_metadata.py','tests/integration/test_r04_review_regressions.py','tests/security/test_r02_auth_state_boundaries.py','tests/security/test_r03_executor_authorization.py','tests/contract/test_t07_jobs_outbox.py']
environment['TEST_DATABASE_URL'] = base.set(database=database).render_as_string(hide_password=False)
environment['DIANZI_TEST_RUN_ID'] = database.removeprefix('test_dianzi_')
environment['COVERAGE_FILE'] = str(RUN / (label + '.coverage'))
environment['PYTHONPATH'] = os.pathsep.join(str(ROOT / path) for path in ['backend/src','backend/tests','backend/tests/integration','.'])
print(json.dumps({'database':database,'scope':'explicitly synthetic IO, real PG with UUID schemas; no paid calls'}))
argv = [str(ROOT / 'backend/.venv/Scripts/python.exe'),'-m','pytest',*cases,'--no-cov','-q','-s','--junitxml=' + str(RUN / (label + '.xml'))]
raise SystemExit(run(label,str(ROOT / 'backend'),argv,environment))
