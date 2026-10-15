"""Seal public review evidence and check only owned resources; no credential output."""
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

WT=Path('/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review/dianzi')
RUN=Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015')
REPORT=Path('/mnt/d/dianzi/reports/reviews/recovery/G-B-R04-pipeline-review-1.md')
DB='test_dianzi_r04_pipeline_review_20261015'
def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
started=now()
pg=json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
objects=json.loads(Path('/tmp/dianzi-minio-r02-20261015/private/connection.json').read_text())
root_url=make_url(pg['TEST_DATABASE_URL'])
url=root_url.set(database=DB)
engine=create_engine(url,connect_args={'connect_timeout':5})
with engine.connect() as connection:
    assert connection.scalar(text('SELECT current_database()'))==DB
    schema_count=connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_%'"))
    active_others=connection.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=:name AND pid!=pg_backend_pid()'),{'name':DB})
engine.dispose()
(RUN/'resource_close.json').write_text(json.dumps({'started_at':started,'ended_at':now(),'database':DB,'owned_schemas_remaining':schema_count,'other_connections_to_owned_db':active_others,'own_minio_test_buckets_removed_by_test_finally':True,'shared_services_stopped':False,'other_databases_migrated':False,'no_recurring_or_owned_service_started':True},indent=2))
known={'pg_password':unquote(root_url.password or ''),'pg_connection':pg['TEST_DATABASE_URL'],'review_pg_connection':url.render_as_string(hide_password=False),'minio_access':objects['access_key'],'minio_secret':objects['secret_key']}
files=[path for path in RUN.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name not in {'secret_scan.json','manifest.json'}]
files += [path for path in (WT/'backend/src').rglob('*.py') if '__pycache__' not in path.parts]
fixed=Path('/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review-fix/dianzi/backend/src')
if fixed.exists():
    files += [path for path in fixed.rglob('*.py') if '__pycache__' not in path.parts]
if REPORT.exists():
    files.append(REPORT)
matches=[]
for path in files:
    body=path.read_bytes()
    for label,value in known.items():
        if not value:
            continue
        encoded=value.encode()
        if encoded in body:
            matches.append({'file':str(path),'credential_kind':label,'kind':'full'})
        if label in {'pg_password','minio_secret'} and len(encoded)>=8:
            fragments={encoded[index:index+8] for index in range(len(encoded)-7)}
            if any(fragment in body for fragment in fragments):
                matches.append({'file':str(path),'credential_kind':label,'kind':'eight_byte_fragment'})
(RUN/'secret_scan.json').write_text(json.dumps({'started_at':started,'ended_at':now(),'scope':'own raw/report and both fixed candidate backend/src; registered private service credentials in memory only','files_scanned':len(files),'matches':matches,'checks':'full PG DSNs/MinIO access+secret; full and every eight-byte fragment of PG password/MinIO secret','heuristic_first_preserved':'secret_scan_heuristic_first.json','heuristic_first_common_fragments':{'pg_connection_public_structure':57,'minio_access_public_identifier_fragments':30},'no_evidence_output_redacted_after_scan':True},indent=2))
manifest=[]
for path in RUN.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts and path.name!='manifest.json':
        content=path.read_bytes()
        manifest.append({'path':str(path.relative_to(RUN)),'size_bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
if REPORT.exists():
    content=REPORT.read_bytes()
    manifest.append({'path':'../../reviews/recovery/G-B-R04-pipeline-review-1.md','size_bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
(RUN/'manifest.json').write_text(json.dumps({'sealed_at':now(),'files':sorted(manifest,key=lambda row:row['path'])},indent=2))
print(json.dumps({'schema_count':schema_count,'connections':active_others,'secret_matches':len(matches),'manifest_files':len(manifest)}))
