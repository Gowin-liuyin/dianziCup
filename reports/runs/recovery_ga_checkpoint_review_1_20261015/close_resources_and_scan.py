"""Close only reviewer routing leftovers and check evidence for exact private values."""
import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from minio import Minio
from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

RUN=Path('/mnt/d/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
config=json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
store=json.loads(Path('/tmp/dianzi-minio-r02-20261015/private/connection.json').read_text())
base=make_url(config['TEST_DATABASE_URL'])
assert base.host=='127.0.0.1' and base.port==25432 and base.database=='test_dianzi_r01_20261014'
redis=Redis.from_url(config['TEST_REDIS_URL'].rsplit('/',1)[0]+'/10')
owned=set(re.findall(r'ga_checkpoint_[0-9a-f]{32}',(RUN/'runtime_worker.log').read_text()))
removed=0
for key in redis.keys('_kombu.binding.*'):
    if redis.type(key)==b'set':
        members=[member for member in redis.smembers(key) if any(value.encode() in member for value in owned)]
        if members: removed+=redis.srem(key,*members)
        if redis.scard(key)==0: redis.delete(key)
remaining=redis.keys()
redis.close()
engine=create_engine(base.set(database='test_dianzi_ga_checkpoint_review_20261015'))
with engine.connect() as conn:
    database,version=conn.execute(text('SELECT current_database(),(SELECT version_num FROM alembic_version)')).one()
engine.dispose()
minio=Minio(store['endpoint'],access_key=store['access_key'],secret_key=store['secret_key'],secure=False)
objects=list(minio.list_objects('test-dianzi-r02-ga-checkpoint-review-20261015',recursive=True))
private=[base.password or '',store['access_key'],store['secret_key']]
variants=set()
for value in private:
    if value:
        variants.add(value.encode())
        if len(value)>=8: variants.update(value[i:i+8].encode() for i in range(len(value)-7))
hits=[]
files=[]
for path in RUN.rglob('*'):
    if path.is_file() and path.suffix not in {'.coverage'}:
        raw=path.read_bytes()
        if any(value in raw for value in variants): hits.append(str(path.relative_to(RUN)))
        files.append(dict(path=str(path.relative_to(RUN)),sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw)))
runtime=json.loads((RUN/'runtime_health.json').read_text())
processes=runtime['processes']
for path in (RUN/'worker_processes').glob('*processes.json'):
    processes.extend(json.loads(path.read_text())['processes'])
alive=[entry['pid'] for entry in processes if Path('/proc/'+str(entry['pid'])).exists()]
result=dict(recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),database=database,migration=version,redis_db=10,owned_binding_members_removed=removed,remaining_redis_key_count=len(remaining),own_processes_alive=alive,minio_bucket='test-dianzi-r02-ga-checkpoint-review-20261015',retained_object_count=len(objects),retained_reason='fixture PG references and failure evidence retained; no shared resources stopped',private_exact_or_8char_fragment_hit_files=hits,evidence_files=files)
(RUN/'resource_closure_and_secret_scan.json').write_text(json.dumps(result,indent=2))
print(json.dumps({key:result[key] for key in result if key!='evidence_files'}))
assert not hits and not alive and not remaining
