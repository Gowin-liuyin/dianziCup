"""Seal independent cursor review without product keys or object-store access."""
import hashlib
import json
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url

WT=Path('/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-cursor-recheck/dianzi')
RUN=Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_recheck_20261015')
REPORT=Path('/mnt/d/dianzi/reports/reviews/recovery/G-B-R04-pipeline-review-1-recheck.md')
DB='test_dianzi_r04_cursor_review_20261015'
def now():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
started=now()
private=json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
root_url=make_url(private['TEST_DATABASE_URL'])
assert root_url.host=='127.0.0.1' and root_url.port==25432
review_url=root_url.set(database=DB)
engine=create_engine(review_url,connect_args={'connect_timeout':5})
with engine.connect() as connection:
    assert connection.scalar(text('SELECT current_database()'))==DB
    schemas=connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_%'"))
    connections=connection.scalar(text('SELECT count(*) FROM pg_stat_activity WHERE datname=:name AND pid!=pg_backend_pid()'),{'name':DB})
engine.dispose()
(RUN/'resource_close.json').write_text(json.dumps({'started_at':started,'ended_at':now(),'database':DB,'owned_schemas_remaining':schemas,'other_connections_to_owned_db':connections,'database_retained_empty':True,'minio_used':False,'object_buckets_created':0,'external_gets':0,'shared_services_stopped':False,'other_databases_migrated':False,'owned_background_services_started':0},indent=2))
old_test=Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015/recheck_7184/testcopy/test_actual_vendor_pagination.py')
new_test=RUN/'testcopy/test_actual_vendor_pagination.py'
body=Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015/public_inputs/vendor_pagination_page_1.json')
(RUN/'input_identity.json').write_text(json.dumps({'recorded_body_path':str(body),'body_sha256':hashlib.sha256(body.read_bytes()).hexdigest(),'body_bytes':body.stat().st_size,'original_red_test_path':str(old_test),'original_red_test_sha256':hashlib.sha256(old_test.read_bytes()).hexdigest(),'rerun_test_sha256':hashlib.sha256(new_test.read_bytes()).hexdigest(),'test_unchanged':old_test.read_bytes()==new_test.read_bytes()},indent=2))
passwords={value for value in (root_url.password,unquote(root_url.password or '')) if value}
connections_to_scan={private['TEST_DATABASE_URL'],review_url.render_as_string(hide_password=False)}
files=[path for path in RUN.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name not in {'secret_scan.json','manifest.json'}]
files += [path for path in (WT/'backend/src').rglob('*.py') if '__pycache__' not in path.parts]
files.append(REPORT)
matches=[]
for path in files:
    content=path.read_bytes()
    if any(value.encode() in content for value in connections_to_scan):
        matches.append({'file':str(path),'kind':'full_test_database_url'})
    for password in passwords:
        value=password.encode()
        if value in content:
            matches.append({'file':str(path),'kind':'full_test_database_password'})
        if len(value)>=8 and any(value[index:index+8] in content for index in range(len(value)-7)):
            matches.append({'file':str(path),'kind':'eight_byte_password_fragment'})
(RUN/'secret_scan.json').write_text(json.dumps({'started_at':started,'ended_at':now(),'files_scanned':len(files),'scope':'own raw/report and fixed candidate backend/src; only private test PG credential read in memory','product_keys_read':False,'minio_credentials_read':False,'matches':matches},indent=2))
manifest=[]
for path in RUN.rglob('*'):
    if path.is_file() and '__pycache__' not in path.parts and path.name!='manifest.json':
        content=path.read_bytes()
        manifest.append({'path':str(path.relative_to(RUN)),'size_bytes':len(content),'sha256':hashlib.sha256(content).hexdigest()})
report_body=REPORT.read_bytes()
manifest.append({'path':'../../reviews/recovery/G-B-R04-pipeline-review-1-recheck.md','size_bytes':len(report_body),'sha256':hashlib.sha256(report_body).hexdigest()})
(RUN/'manifest.json').write_text(json.dumps({'sealed_at':now(),'head':'8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce','tree':'1b9a94ac49b58ddd12debb40f173749dbd3110a7','files':sorted(manifest,key=lambda row:row['path'])},indent=2))
print(json.dumps({'schemas':schemas,'connections':connections,'secret_matches':len(matches),'manifest_files':len(manifest)}))
