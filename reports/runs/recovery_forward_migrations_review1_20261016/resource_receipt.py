"""仅核验本审查两个已清理marker数据库及session数。"""

import json
from pathlib import Path
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from checks import now, secret_values

RUN=Path(__file__).resolve().parent
configured,_=secret_values()
engine=create_engine(make_url(configured),poolclass=NullPool,hide_parameters=True)
rows=[]
try:
    with engine.connect() as connection:
        for directory in ('pg_author','pg_independent'):
            marker=json.loads((RUN/directory/'owned_database.json').read_text())
            assert marker['marker'].startswith('recovery_forward_migrations_review1')
            name=marker['database']
            assert name.startswith('test_forward26_')
            sessions=connection.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=:db'),{'db':name})
            databases=connection.scalar(text('SELECT count(*) FROM pg_database WHERE datname=:db'),{'db':name})
            assert sessions==databases==0
            cleanup=json.loads((RUN/directory/'cleanup.json').read_text())
            assert cleanup['marker_validated'] and cleanup['sessions_before_drop']==cleanup['databases_after_drop']==0
            rows.append({'database':name,'marker':marker['marker'],'sessions_now':sessions,'databases_now':databases,'schema_markers_now':0,'cleanup_marker_validated':True})
finally:
    engine.dispose()
(RUN/'release.json').write_text(json.dumps({'recorded_at':now(),'owned_resources':rows,'own_sessions':0,'own_schemas':0,'heavy_pg_slot_released':True,'shared_pg_restart':False,'other_session_termination':False},indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'own_sessions':0,'own_schemas':0,'heavy_pg_slot_released':True}))
