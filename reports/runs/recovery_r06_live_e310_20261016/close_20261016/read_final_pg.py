"""Read only the exact isolated segment facts and current clock/sample costs."""

import hashlib
import json
import os
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

CLOSE=Path(__file__).resolve().parent
RUN=Path('D:/dianzi-runtime-cache/r06-live-e310-run-20261016/reports/runs/recovery_r06_live_restart_preparation_20261016')
start=json.loads((RUN/'runtime_start.json').read_bytes())
end=json.loads((RUN/'runtime_end.json').read_bytes())
url=make_url(os.environ['DATABASE_URL'])
assert url.host in {'127.0.0.1','localhost'} and url.port==25432 and url.database=='test_dianzi_r06_catalog_live_8a_20261016'
engine=create_engine(url,hide_parameters=True,connect_args={'connect_timeout':3,'options':'-c statement_timeout=3000'})
samples=[]
for _ in range(3):
    before=datetime.now(UTC)
    wall=time.perf_counter()
    with engine.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        tx=connection.scalar(text('select transaction_timestamp()'))
        count=connection.scalar(text("select count(*) from job_runs where job_type='collect_public_source_page'"))
        running=list(connection.execute(text("select job_id,started_at,lease_expires_at from job_runs where job_type='collect_public_source_page' and status='running' order by started_at limit 3")).mappings())
    after=datetime.now(UTC)
    samples.append({'client_before':before.isoformat(),'client_after':after.isoformat(),'pg_transaction_time':tx.isoformat(),'age_at_guard_seconds':(after-tx).total_seconds(),'read_cycle_wall_seconds':time.perf_counter()-wall,'source_jobs':count,'running_count':len(running),'historical_failure_reproduction':False})
with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection,connection.begin():
    connection.execute(text('SET TRANSACTION READ ONLY'))
    schema=connection.scalar(text('select version_num from alembic_version'))
    assert schema=='0016_source_response_receipts'
    counts={name:connection.scalar(text('select count(*) from '+name)) for name in ['documents','document_revisions','evidence','source_response_receipts','source_page_receipts','content_objects','fetch_attempts']}
    jobs=[]
    for row in connection.execute(text("select j.job_id,j.status,j.attempt_count,j.max_attempts,j.error_code,j.created_at,j.started_at,j.finished_at,j.lease_expires_at,p.payload from job_runs j join job_payloads p on p.job_id=j.job_id where j.job_type='collect_public_source_page' order by j.created_at,j.job_id")).mappings():
        payload=json.loads(bytes(row['payload']))
        jobs.append({key:row[key] for key in ['job_id','status','attempt_count','max_attempts','error_code','created_at','started_at','finished_at','lease_expires_at']}|{'source_kind':payload['source_kind'],'remaining_pages':payload['remaining_pages']})
    all_job_types=[dict(row) for row in connection.execute(text('select job_type,status,count(*) jobs from job_runs group by job_type,status order by job_type,status')).mappings()]
    receipts=[dict(row) for row in connection.execute(text('select receipt_id,job_id,source_kind,observed_at,http_status,parse_outcome,error_code,response_content_hash,response_size_bytes,input_cursor_sha256 from source_response_receipts where observed_at>=cast(:since as timestamptz) order by observed_at,receipt_id'),{'since':start['started_at']}).mappings()]
    cursors=[{'source_id':row['source_id'],'generation':row['generation'],'cursor_sha256':hashlib.sha256(json.dumps(row['cursor_json'],sort_keys=True).encode()).hexdigest()} for row in connection.execute(text('select source_id,generation,cursor_json from source_cursors')).mappings()]
    runtime=[dict(row) for row in connection.execute(text('select * from runtime_observations order by component')).mappings()]
    published=dict(connection.execute(text("select count(*) new_revisions,count(*) filter(where source_published_at is null) publication_unknown,count(*) filter(where source_published_at>first_observed_at) future_publication,count(*) filter(where ingested_at-source_published_at>interval '6 hours') older_than_six_hours,extract(epoch from percentile_cont(0.5) within group(order by ingested_at-source_published_at) filter(where source_published_at is not null)) p50_seconds,extract(epoch from percentile_cont(0.95) within group(order by ingested_at-source_published_at) filter(where source_published_at is not null)) p95_seconds,extract(epoch from max(ingested_at-source_published_at) filter(where source_published_at is not null)) max_seconds from document_revisions where ingested_at>=cast(:since as timestamptz) and ingested_at<=cast(:ended as timestamptz)"),{'since':start['started_at'],'ended':end['ended_at']}).mappings().one())
engine.dispose()
result={'read_at':datetime.now(UTC).isoformat(),'read_only':True,'database':'test_dianzi_r06_catalog_live_8a_20261016','schema':schema,'clock_read_cycle_samples_after_stop':samples,'counts_total':counts,'counts_delta_from_segment_start':{key:value-start['initial_history_counts'][key] for key,value in counts.items() if key in start['initial_history_counts']},'source_jobs_total':len(jobs),'new_source_jobs':sum(row['created_at']>=datetime.fromisoformat(start['started_at']) for row in jobs),'jobs':jobs,'all_job_types':all_job_types,'new_segment_response_receipts':receipts,'cursor_hashes_only':cursors,'runtime_observations_last_pg_rows':runtime,'publication_time_new_segment_denominator':published,'actual_wire_count':'unknown','source_cost':'unknown','model_requests':0,'paid_provider_requests':0,'source_submit_requests':0,'source_http_this_read':0,'formal_six_hour_pass':False}
with (CLOSE/'final_pg_receipt.json').open('x',encoding='utf-8') as output:
    json.dump(result,output,indent=2,default=str)
    output.write('\n')
print(json.dumps({'source_jobs':len(jobs),'new_jobs':result['new_source_jobs'],'counts':counts,'delta':result['counts_delta_from_segment_start'],'guard_read_samples':samples,'all_job_types':all_job_types}))
