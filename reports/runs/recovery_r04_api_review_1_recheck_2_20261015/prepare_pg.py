"""Create only the explicitly authorized independent PostgreSQL test database."""

import json
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

original = json.loads(Path('/tmp/dianzi-r04-api-20261015/connection.json').read_text())
original_url = make_url(original['TEST_DATABASE_URL'])
target_name = 'test_dianzi_r04_api_review_recheck2_20261015'
assert original_url.database == 'test_dianzi_r04_api_20261015'
admin = create_engine(original_url, isolation_level='AUTOCOMMIT')
with admin.connect() as connection:
    exists = connection.scalar(text('SELECT 1 FROM pg_database WHERE datname=:name'), {'name': target_name})
    if exists:
        raise RuntimeError('independent review database already exists; refusing to reuse unrelated state')
    connection.execute(text('CREATE DATABASE "test_dianzi_r04_api_review_recheck2_20261015"'))
admin.dispose()
private = Path('/tmp/dianzi-r04-api-review-1-recheck-2-20261015')
private.mkdir(mode=0o700, exist_ok=True)
private.chmod(0o700)
destination = private / 'connection.json'
destination.write_text(json.dumps({'DIANZI_TEST_RUN_ID':'r04_api_review_recheck2_20261015',
    'TEST_DATABASE_URL':original_url.set(database=target_name).render_as_string(hide_password=False)}))
destination.chmod(0o600)
review_engine = create_engine(original_url.set(database=target_name))
with review_engine.connect() as connection:
    print(json.dumps({'actual_database':connection.scalar(text('SELECT current_database()')),
        'private_file_mode':oct(destination.stat().st_mode & 0o777),
        'postgres_version':connection.scalar(text('SHOW server_version')),
        'data_mode':'fixture','external_model_calls':0}))
review_engine.dispose()


