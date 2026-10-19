"""Use one private captured DSN and explicitly named independent test databases."""
import json
import os
from pathlib import Path
import subprocess
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from run_command import ROOT, RUN, record

PYTHON=ROOT/'backend/.venv/Scripts/python.exe'
RUN_ID='r06_catalog_gc_e310_20261016'
DATABASE='test_dianzi_'+RUN_ID
captured=subprocess.check_output(['wsl.exe','-d','Ubuntu-22.04','-u','root','--','cat',
    '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'],text=True,timeout=15)
settings=json.loads(captured)
url=make_url(settings['TEST_DATABASE_URL'])
assert url.host in {'127.0.0.1','localhost'} and url.port==25432 and url.database.startswith('test_')
env=os.environ.copy()
env['PYTHONPATH']=os.pathsep.join([str(RUN),str(ROOT/'backend/src'),str(ROOT/'backend/tests/integration'),str(ROOT/'backend'),str(ROOT)])
env['DIANZI_TEST_RUN_ID']=RUN_ID
env['TEST_DATABASE_URL']=url.set(database=DATABASE).render_as_string(hide_password=False)
env['PYTHONDONTWRITEBYTECODE']='1'
env.pop('TEST_REDIS_URL',None)
sys.path.insert(0,str(ROOT))
from scripts.dev import require_isolated_test_database
require_isolated_test_database(env)
admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT',connect_args={'connect_timeout':5},hide_parameters=True)
with admin.connect() as connection:
    assert connection.scalar(text('SELECT current_database()'))=='postgres'
    present=connection.scalar(text('SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:n)'),{'n':DATABASE})
    if not present:
        connection.execute(text('CREATE DATABASE '+DATABASE))
admin.dispose()
engine=create_engine(env['TEST_DATABASE_URL'],connect_args={'connect_timeout':5},hide_parameters=True)
with engine.connect() as connection:
    assert connection.scalar(text('SELECT current_database()'))==DATABASE
    before=inspect(connection).get_table_names()
(RUN/('pg_isolation_'+sys.argv[1]+'.json')).write_text(json.dumps(dict(database=DATABASE,run_id=RUN_ID,port=25432,created=not present,public_tables_before=before,fixture_mode=True,dsn_in_argv=False),indent=2),encoding='utf-8')


def pytest(label,files,extra=()):
    return record(label,[PYTHON,'-m','pytest',*files,*extra,'--no-cov','-q','--tb=short','-p','no:cacheprovider',
        '--basetemp',str(RUN/(label+'_tmp')),'--junitxml',str(RUN/(label+'.xml'))],ROOT/'backend',env)

mode=sys.argv[1]
if mode=='publication':
    files=['test_r07_enrichment_inputs_pg.py','test_r07_composed_claims_pg.py','test_r07_enrichment_publication_pg.py',
        'test_r07_signal_claim_values_pg.py','test_r07_literature_target_scope_pg.py','test_r06_catalog_documents_pg.py',
        'test_r07_publication_acl_lock_fix_pg.py','test_r07_cvss_authority_scope_fix_pg.py','test_r07_publication_rule_provenance_pg.py']
    pytest('pg_publication_95',['tests/integration/'+x for x in files])
    probe=Path('D:/dianzi/reports/runs/recovery_r07_publication_review1_recheck_20261016/test_independent_recheck_v2_pg.py')
    target=RUN/probe.name
    if not target.exists(): target.write_bytes(probe.read_bytes())
    pytest('pg_independent_lock_roster',[str(target)],['--confcutdir',str(ROOT)])
elif mode=='sources':
    files=['test_r06_bulk_source_evidence_pg.py','test_r06_source_worker_pg.py',
        'test_r06_failed_response_persistence_pg.py','test_r06_source_boundary_pg.py',
        'test_r04_source_jobs_pg.py','test_r06_source_worker_api_pg.py','test_r06_document_api_pg.py']
    pytest('pg_sources_bulk_failures',['tests/integration/'+x for x in files])
elif mode=='foundation':
    pytest('pg_t05_t07',['tests/integration/test_t05_persistence_and_raw_store.py','tests/integration/test_t07_jobs_and_outbox.py'])
elif mode=='bulk_auth_security':
    pytest('pg_bulk_auth_security',['tests/security/test_r06_bulk_source_evidence_scope.py','tests/security/test_r02_auth_state_boundaries.py'])
elif mode=='t07_contract':
    pytest('pg_t07_retry_contract',['tests/contract/test_t07_jobs_outbox.py'])
elif mode=='original_fixed_negative':
    pytest('pg_original_r04_fixed_resource',['tests/integration/test_r04_source_documents.py::test_recorded_source_persists_raw_versions_and_verified_facts'])
elif mode=='default':
    pytest('pg_default_product_path',[str(RUN/'test_default_product_path.py')],['--confcutdir',str(ROOT)])
elif mode=='default_v2':
    pytest('pg_default_product_path_v2',[str(RUN/'test_default_product_path_v2.py')],['--confcutdir',str(ROOT)])
elif mode=='default_v3_negative':
    pytest('pg_default_product_path_v3_negative',[str(RUN/'test_default_product_path_v3.py')],['--confcutdir',str(ROOT),'-k','failure'])
elif mode=='adapted_r04':
    record('pg_original_r04_resource_adapted',[PYTHON,str(RUN/'run_legacy_r04.py')],ROOT/'backend',env)
else:
    raise SystemExit('unknown pg mode')
with engine.connect() as connection:
    after=inspect(connection).get_table_names()
    schemas=connection.scalars(text("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'test_%' ORDER BY schema_name")).all()
(RUN/(mode+'_pg_after.json')).write_text(json.dumps(dict(database=DATABASE,public_tables=after,test_schemas=schemas,database_retained=True),indent=2),encoding='utf-8')
engine.dispose()
