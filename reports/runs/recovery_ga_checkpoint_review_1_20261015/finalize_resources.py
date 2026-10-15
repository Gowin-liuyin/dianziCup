"""Fresh final resource state; exact identity and secret fragments remain separate."""
import json
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from minio import Minio
from redis import Redis
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

run=Path('/mnt/d/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
config=json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
store=json.loads(Path('/tmp/dianzi-minio-r02-20261015/private/connection.json').read_text())
base=make_url(config['TEST_DATABASE_URL'])
assert base.host=='127.0.0.1' and base.port==25432 and base.database=='test_dianzi_r01_20261014'
cache=Redis.from_url(config['TEST_REDIS_URL'].rsplit('/',1)[0]+'/10')
remaining=len(cache.keys())
cache.close()
engine=create_engine(base.set(database='test_dianzi_ga_checkpoint_review_20261015'))
with engine.connect() as connection:
    database,head=connection.execute(text('SELECT current_database(),(SELECT version_num FROM alembic_version)')).one()
engine.dispose()
client=Minio(store['endpoint'],access_key=store['access_key'],secret_key=store['secret_key'],secure=False)
object_count=sum(1 for _ in client.list_objects('test-dianzi-r02-ga-checkpoint-review-20261015',recursive=True))
secret_patterns=set()
for secret in (base.password or '',store['secret_key']):
    if secret:
        secret_patterns.add(secret.encode())
        secret_patterns.update(secret[i:i+8].encode() for i in range(len(secret)-7))
identity=store['access_key'].encode()
secret_hits=[]
identity_hits=[]
for path in run.rglob('*'):
    if path.is_file():
        value=path.read_bytes()
        if any(secret in value for secret in secret_patterns):secret_hits.append(str(path.relative_to(run)))
        if identity in value:identity_hits.append(str(path.relative_to(run)))
runtime=json.loads((run/'runtime_health.json').read_text())
processes=runtime['processes']
for path in (run/'worker_processes').glob('*processes.json'):
    processes.extend(json.loads(path.read_text())['processes'])
alive=[entry['pid'] for entry in processes if Path('/proc/'+str(entry['pid'])).exists()]
result=dict(recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),database=database,head=head,redis_db=10,remaining_redis_keys=remaining,own_processes_alive=alive,retained_minio_object_count=object_count,secret_exact_or_8char_hit_files=secret_hits,access_identity_exact_hit_files=identity_hits,identity_8char_collisions='original scanner and hash-only classification retained; public path/package fragment matches, not exact access identity')
(run/'resource_closure_after_combined.json').write_text(json.dumps(result,indent=2))
print(json.dumps(result))
assert remaining==0 and not alive and not secret_hits and not identity_hits
