"""Forward-only private databases for the integrated inventory and aggregate service proposals."""
import datetime as dt
import json
import os
import subprocess
import sys
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url
from run_command import ROOT, RUN, record

mode=sys.argv[1]
assert mode in {'inventory','aggregate'}
run_id=('r11_inventory_' if mode=='inventory' else 'r08_aggregate_')+'gc_e310_20261016'
database='test_dianzi_'+run_id
started=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat()
captured=subprocess.check_output(['wsl.exe','-d','Ubuntu-22.04','-u','root','--','cat',
    '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'],text=True,timeout=15)
configuration=json.loads(captured)
url=make_url(configuration['TEST_DATABASE_URL'])
assert url.host in {'127.0.0.1','localhost'} and url.port==25432 and url.database.startswith('test_')
env=os.environ.copy()
env['DIANZI_TEST_RUN_ID']=run_id
env['TEST_DATABASE_URL']=url.set(database=database).render_as_string(hide_password=False)
env['PYTHONPATH']=os.pathsep.join([str(ROOT/'backend/src'),str(ROOT/'backend/tests/integration'),str(ROOT/'backend'),str(ROOT)])
sys.path.insert(0,str(ROOT))
from scripts.dev import require_isolated_test_database
from ai_intel.infrastructure.database import run_migrations
require_isolated_test_database(env)
admin=create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT',hide_parameters=True)
with admin.connect() as connection:
    assert connection.scalar(text('SELECT current_database()'))=='postgres'
    assert not connection.scalar(text('SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:n)'),{'n':database})
    connection.execute(text('CREATE DATABASE '+database))
admin.dispose()
run_migrations(env['TEST_DATABASE_URL'],'0016_source_response_receipts')
engine=create_engine(env['TEST_DATABASE_URL'],hide_parameters=True)
if mode=='inventory':
    from ai_intel.assets.inventory_models import ASSET_TABLES
    from ai_intel.knowledge.models import metadata
    metadata.create_all(engine,tables=list(ASSET_TABLES))
    files=['tests/integration/test_t24_asset_inventory.py']
else:
    from ai_intel.assets.aggregate_persistence_models import aggregate_observations
    aggregate_observations.create(engine)
    files=['tests/integration/test_r08_aggregate_persistence_pg.py','tests/integration/test_r08_cache_ttl_fix1_pg.py']
with engine.connect() as connection:
    assert connection.scalar(text('SELECT current_database()'))==database
    revision=connection.scalar(text('SELECT version_num FROM alembic_version'))
    tables=inspect(connection).get_table_names()
(RUN/(mode+'_database_receipt.json')).write_text(json.dumps(dict(started_at=started,ended_at=dt.datetime.now(dt.timezone(dt.timedelta(hours=8))).isoformat(),database=database,run_id=run_id,port=25432,migration=revision,proposal_tables=tables,production_0018_0019=False,action='create_tables_not_production_migration'),indent=2),encoding='utf-8')
python=ROOT/'backend/.venv/Scripts/python.exe'
record('pg_'+mode,[python,'-m','pytest',*files,'--no-cov','-q','--tb=short','-p','no:cacheprovider',
    '--basetemp',str(RUN/(mode+'_tmp')),'--junitxml',str(RUN/('pg_'+mode+'.xml'))],ROOT/'backend',env)
engine.dispose()
