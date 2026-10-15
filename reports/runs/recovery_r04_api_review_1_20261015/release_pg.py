"""Release only the review-owned database after all tests finish; no forced session termination."""

import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

private = Path('/tmp/dianzi-r04-api-review-1-20261015')
connection = json.loads((private/'connection.json').read_text())
url = make_url(connection['TEST_DATABASE_URL'])
target = 'test_dianzi_r04_api_review_20261015'
assert url.database == target
engine = create_engine(url)
with engine.connect() as session:
    schemas = list(session.scalars(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_r04_api_%'")))
    actual_database = session.scalar(text('SELECT current_database()'))
assert not schemas and actual_database == target
engine.dispose()
admin = create_engine(url.set(database='postgres'),isolation_level='AUTOCOMMIT')
with admin.connect() as session:
    active = session.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=:name'),{'name':target})
    assert active == 0
    session.execute(text('DROP DATABASE "test_dianzi_r04_api_review_20261015"'))
    remaining = session.scalar(text('SELECT count(*) FROM pg_database WHERE datname=:name'),{'name':target})
admin.dispose()
result = {'actual_review_database':target,'review_schema_count_before_release':len(schemas),
    'active_review_connections_before_release':active,'database_count_after_release':remaining,
    'shared_databases_modified':False,'forced_session_termination':False,'downgrade_executed':False,
    'private_credentials_retained':'root0600 for final evidence scan only; no running resources'}
run = Path(__file__).resolve().parent
(run/'resource_release.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
