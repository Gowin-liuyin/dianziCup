"""Real local API, worker and scheduler restart probe with dedicated queue and PG."""
import json
import os
import secrets
import signal
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

SOURCE=Path('/mnt/d/dianzi-ga-checkpoint-review-1')
RUN=Path('/mnt/d/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
WORK=Path('/tmp/dianzi-ga-checkpoint-review1-20261015')

def at():
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')

def main():
    connection=json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
    store=json.loads(Path('/tmp/dianzi-minio-r02-20261015/private/connection.json').read_text())
    base=make_url(connection['TEST_DATABASE_URL'])
    assert base.host=='127.0.0.1' and base.port==25432 and base.database=='test_dianzi_r01_20261014'
    database_url=base.set(database='test_dianzi_ga_checkpoint_review_20261015').render_as_string(hide_password=False)
    redis_url=connection['TEST_REDIS_URL'].rsplit('/',1)[0]+'/10'
    queue='ga_checkpoint_'+uuid4().hex
    env=dict(os.environ,DATABASE_URL=database_url,REDIS_URL=redis_url,APP_ENV='test',DATA_MODE='fixture',OPENSEARCH_URL='http://127.0.0.1:29200',ALLOWED_ORIGINS='["http://127.0.0.1:25312"]',PYTHONPATH=str(SOURCE/'backend/src'),PYTHONIOENCODING='utf-8',CONTENT_STORE_BACKEND='minio',MINIO_ENDPOINT=store['endpoint'],MINIO_BUCKET='test-dianzi-r02-ga-checkpoint-review-20261015',MINIO_ACCESS_KEY=store['access_key'],MINIO_SECRET_KEY=store['secret_key'],MINIO_SECURE='false',GA_QUEUE=queue)
    from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
    from ai_intel.api.auth_state import PgAuthenticationStateStore
    from ai_intel.domain.access import Role
    engine=create_engine(database_url)
    password=secrets.token_urlsafe(32)
    username='ga_runtime_'+uuid4().hex
    service=AuthenticationSessionService(DatabaseUserDirectory(engine),('http://127.0.0.1:25312',),False,state_store=PgAuthenticationStateStore(engine))
    account=service.create_precreated_user(username,password,'ga-runtime-tenant',Role.ANALYST)
    launcher=WORK/'runtime_launcher.py'
    launcher.write_text('import os,sys\nfrom ai_intel.workers.runtime import celery_app\ncelery_app.conf.task_default_queue=os.environ["GA_QUEUE"]\ncelery_app.start(sys.argv[1:])\n')
    processes=[]
    observations=[]
    started=at()
    def start(name,args):
        output=WORK/(name+'.raw.log')
        stream=output.open('wb')
        process=subprocess.Popen(args,cwd=SOURCE/'backend',env=env,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        processes.append((name,process,stream,output,at()))
        return process
    def stop(process):
        if process.poll() is None:
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(timeout=12)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL)
                process.wait(timeout=5)
    def wait(predicate,seconds=40):
        limit=time.monotonic()+seconds
        while time.monotonic()<limit:
            try:
                value=predicate()
                if value: return value
            except httpx.HTTPError: pass
            time.sleep(.3)
        raise AssertionError('bounded runtime observation failed')
    api_args=[sys.executable,'-m','uvicorn','ai_intel.api.app:app','--host','127.0.0.1','--port','28012','--log-level','warning']
    failure=None
    try:
        api=start('api_initial',api_args)
        worker=start('worker',[sys.executable,str(launcher),'worker','--pool=prefork','--concurrency=1','--loglevel=WARNING','--without-gossip','--without-mingle','--without-heartbeat','-Q',queue,'-n','ga_checkpoint@'+queue])
        beat=start('beat',[sys.executable,str(launcher),'beat','--loglevel=WARNING','--schedule',str(WORK/'runtime-beat-state')])
        with httpx.Client(base_url='http://127.0.0.1:28012',timeout=4,trust_env=False) as client:
            wait(lambda: client.get('/v1/health/live').status_code==200)
            ready=wait(lambda: (response if (response:=client.get('/v1/health/ready')).status_code==200 else None))
            observations.append(dict(at=at(),check='all_real_dependencies_ready',response=ready.json()))
            login=client.post('/v1/auth/login',json={'username':username,'password':password},headers={'Origin':'http://127.0.0.1:25312'})
            assert login.status_code==200
            assert client.get('/v1/auth/me').json()['user_id']==account.user_id
            stop(api)
            api=start('api_restarted',api_args)
            wait(lambda: client.get('/v1/health/live').status_code==200)
            identity=client.get('/v1/auth/me')
            assert identity.status_code==200 and identity.json()['user_id']==account.user_id
            observations.append(dict(at=at(),check='cookie_survives_real_api_process_restart',passed=True))
            logout=client.post('/v1/auth/logout',headers={'Origin':'http://127.0.0.1:25312','X-CSRF-Token':identity.json()['csrf_token']})
            assert logout.status_code==200 and client.get('/v1/auth/me').status_code==401
            observations.append(dict(at=at(),check='revocation_visible_after_process_restart',passed=True))
            stop(beat)
            stop(worker)
            stale=wait(lambda: (response if (response:=client.get('/v1/health/ready')).status_code==503 and response.json()['dependencies']['worker']['state']=='not_observed_or_stale' and response.json()['dependencies']['scheduler']['state']=='not_observed_or_stale' else None),seconds=55)
            observations.append(dict(at=at(),check='actual_stopped_worker_scheduler_expire',response=stale.json()))
    except Exception as error:
        failure=type(error).__name__
    finally:
        receipts=[]
        for name,process,stream,output,start_time in reversed(processes):
            stop(process)
            stream.close()
            output_text=output.read_text(errors='replace')
            for secret in sorted({database_url,redis_url,base.password or '',password,store['access_key'],store['secret_key']},key=len,reverse=True):
                if secret: output_text=output_text.replace(secret,'[redacted credential]')
            (RUN/('runtime_'+name+'.log')).write_text(output_text)
            output.unlink()
            receipts.append(dict(name=name,pid=process.pid,started_at=start_time,stopped_at=at(),exit_code=process.returncode))
        from redis import Redis
        cache=Redis.from_url(redis_url)
        keys=[key for key in cache.keys() if queue.encode() in key]
        if keys: cache.delete(*keys)
        cache.close()
        engine.dispose()
        result=dict(started_at=started,ended_at=at(),sha='8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce',cwd=str(SOURCE/'backend'),api_port=28012,redis_db=10,pool='Linux prefork',commands=[api_args,[sys.executable,str(launcher),'worker','--pool=prefork','-Q','[own queue]'],[sys.executable,str(launcher),'beat']],observations=observations,processes=receipts,failure=failure,exit_code=1 if failure else 0)
        (RUN/'runtime_health.json').write_text(json.dumps(result,indent=2))
        print(json.dumps(result))
    return 1 if failure else 0

if __name__=='__main__': raise SystemExit(main())
