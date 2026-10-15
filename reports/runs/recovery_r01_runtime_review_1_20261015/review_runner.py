"""独立审查的有界记录器；仅使用本轮指定测试项目的私有环境。"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-infra\dianzi")
OUTPUT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
WSL = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec"]
DOCKER_LINUX = ["/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker", "--config", "/tmp/dianzi-docker-static-r01-20261014/runtime/client-config", "--host", "unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock"]
DOCKER = [*WSL, *DOCKER_LINUX]
PROJECT = "dianzi-test-r01_infra_20261015"
SOURCE_SHA = "d7290cf4240929aa98bfbcc381d9e35c32a534a4"
HEAD = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
assert HEAD == "0b6a7ad5e984439855cd97124d70095c608adb58"
ENVIRONMENT = dict(os.environ)
ENVIRONMENT["PYTHONIOENCODING"] = "utf-8"


def timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def load_environment() -> None:
    loaded = subprocess.run([*WSL, "python3", "-c", "import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())", "/tmp/dianzi-r01-infra-20261015/connection.json"], capture_output=True, text=True, timeout=10, check=True)
    configuration = json.loads(loaded.stdout)
    assert set(configuration) == {"run_id", "environment"}
    assert configuration["run_id"] == "r01_infra_20261015"
    private_environment = configuration["environment"]
    assert private_environment["DIANZI_TEST_COMPOSE_PROJECT"] == PROJECT
    for application_name, compose_name in {"DATABASE_URL": "COMPOSE_DATABASE_URL", "REDIS_URL": "COMPOSE_REDIS_URL", "ALLOWED_ORIGINS": "COMPOSE_ALLOWED_ORIGINS"}.items():
        if application_name in private_environment:
            private_environment[compose_name] = private_environment.pop(application_name)
    ENVIRONMENT.update(private_environment)
    ENVIRONMENT["COMPOSE_DISABLE_ENV_FILE"] = "1"
    ENVIRONMENT["DIANZI_DOCKER_COMMAND_JSON"] = json.dumps(DOCKER)
    ENVIRONMENT["DIANZI_TEST_COMPOSE_FILE"] = str(ROOT / "infra/compose/compose.test.host.yaml")
    ENVIRONMENT["DIANZI_COMPOSE_FILE"] = ENVIRONMENT["DIANZI_TEST_COMPOSE_FILE"]
    ENVIRONMENT["DIANZI_COMPOSE_PROJECT"] = PROJECT
    ENVIRONMENT["TEST_BACKEND_IMAGE"] = "dianzi-r01-infra-backend:d7290cf42409"
    ENVIRONMENT["TEST_FRONTEND_IMAGE"] = "dianzi-r01-infra-frontend:bc24286a3a80"
    ENVIRONMENT["WSLENV"] = ":".join(sorted({*private_environment, "COMPOSE_DISABLE_ENV_FILE", "TEST_BACKEND_IMAGE", "TEST_FRONTEND_IMAGE"}))


def redact(content: str) -> str:
    for name, value in ENVIRONMENT.items():
        if value and ("PASSWORD" in name or "PROXY" in name or name in {"DATABASE_URL", "TEST_DATABASE_URL", "REDIS_URL", "TEST_REDIS_URL", "COMPOSE_DATABASE_URL", "COMPOSE_REDIS_URL"}):
            content = content.replace(value, "[redacted test credential]")
    return content


def execute(label: str, arguments: list[str], cwd: Path = ROOT, timeout: int = 60) -> int:
    started = timestamp()
    start_clock = time.monotonic()
    try:
        result = subprocess.run(arguments, cwd=cwd, env=ENVIRONMENT, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout)
        stdout, stderr, code = result.stdout, result.stderr, result.returncode
    except subprocess.TimeoutExpired as error:
        stdout = error.stdout.decode(errors="replace") if isinstance(error.stdout, bytes) else error.stdout or ""
        stderr = error.stderr.decode(errors="replace") if isinstance(error.stderr, bytes) else error.stderr or ""
        code = 124
    (OUTPUT / f"{label}.stdout.log").write_text(redact(stdout), encoding="utf-8")
    (OUTPUT / f"{label}.stderr.log").write_text(redact(stderr), encoding="utf-8")
    counts = None
    xml = OUTPUT / f"{label}.xml"
    if xml.is_file():
        cases = ElementTree.parse(xml).findall(".//testcase")
        counts = {"total": len(cases), "pass": sum(all(case.find(kind) is None for kind in ("failure", "error", "skipped")) for case in cases), "fail": sum(case.find("failure") is not None for case in cases), "error": sum(case.find("error") is not None for case in cases), "skip": sum(case.find("skipped") is not None for case in cases)}
    receipt = {"label": label, "argv": arguments, "cwd": str(cwd), "start": started, "end": timestamp(), "exit": code, "wall_seconds": time.monotonic() - start_clock, "source_sha": SOURCE_SHA, "evidence_head": HEAD, "counts": counts}
    (OUTPUT / f"{label}.json").write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit": code, "counts": counts}, ensure_ascii=False), flush=True)
    return code


def compose(*arguments: str) -> list[str]:
    return [*DOCKER, "compose", "--project-name", PROJECT, "-f", "/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-infra/dianzi/infra/compose/compose.test.host.yaml", "--profile", "core", "--profile", "search", "--profile", "app", "--profile", "worker", "--profile", "scheduler", "--profile", "frontend", *arguments]


def assert_target() -> None:
    result = subprocess.run([*DOCKER, "ps", "--all", "--filter", "label=com.docker.compose.project=" + PROJECT, "--format", "{{.ID}}"], cwd=ROOT, env=ENVIRONMENT, capture_output=True, text=True, timeout=10, check=True)
    ids = result.stdout.split()
    assert len(ids) == 7
    rows = json.loads(subprocess.check_output([*DOCKER, "inspect", *ids], cwd=ROOT, env=ENVIRONMENT, text=True, timeout=10))
    for row in rows:
        labels = row["Config"]["Labels"]
        assert labels["com.docker.compose.project"] == PROJECT
        assert labels["com.docker.compose.project.working_dir"] == "/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-infra/dianzi/infra/compose"
        assert row["HostConfig"]["NetworkMode"] == "host"
        service = labels["com.docker.compose.service"]
        if service in {"api", "worker", "scheduler"}:
            assert row["Image"] == "sha256:34b24db5595ed36fc608f39f648d5a9a2288cb03a2ca8f1ecd123044158ea7b0"
    print(json.dumps({"project_verified": PROJECT, "containers": len(rows), "app_image_verified": True}), flush=True)


def main() -> int:
    load_environment()
    action = sys.argv[1]
    if action in {"inspect", "inspect_final", "inspect_restored", "stop", "restore", "restart_core", "pg_stop", "pg_restore", "expiry", "cold_restart"}:
        assert_target()
    if action in {"inspect", "inspect_final", "inspect_restored"}:
        source = """import json,subprocess,sys
docker=json.loads(sys.argv[1]);project=sys.argv[2]
ids=subprocess.check_output(docker+['ps','--all','--filter','label=com.docker.compose.project='+project,'--format','{{.ID}}'],text=True).split()
rows=json.loads(subprocess.check_output(docker+['inspect',*ids]))
print(json.dumps([{'name':r['Name'],'image':r['Image'],'configured_image':r['Config']['Image'],'user':r['Config']['User'],'command':r['Config']['Cmd'],'project':r['Config']['Labels']['com.docker.compose.project'],'config_files':r['Config']['Labels']['com.docker.compose.project.config_files'],'working_dir':r['Config']['Labels']['com.docker.compose.project.working_dir'],'network_mode':r['HostConfig']['NetworkMode'],'port_bindings':r['HostConfig']['PortBindings'],'memory':r['HostConfig']['Memory'],'nano_cpus':r['HostConfig']['NanoCpus'],'pids_limit':r['HostConfig']['PidsLimit'],'read_only':r['HostConfig']['ReadonlyRootfs'],'cap_drop':r['HostConfig']['CapDrop'],'health':r['State'].get('Health',{}).get('Status'),'status':r['State']['Status'],'proxy_in_environment':any('proxy' in x.split('=',1)[0].lower() for x in r['Config'].get('Env',[]))} for r in rows]))
"""
        return execute(action, [*WSL, "python3", "-c", source, json.dumps(DOCKER_LINUX), PROJECT])
    if action == "stop":
        return execute(action, compose("stop", "scheduler", "worker"), timeout=30)
    if action == "restore":
        return execute(action, compose("start", "worker", "scheduler"), timeout=30)
    if action == "pg_stop":
        return execute(action, compose("stop", "postgres"), timeout=30)
    if action == "pg_restore":
        return execute(action, compose("start", "postgres"), timeout=30)
    if action in {"up_all", "up_all_final"}:
        return execute(action, compose("up", "-d", "--wait", "--wait-timeout", "180", "--pull", "never", "--no-build"), timeout=200)
    if action == "cold_restart":
        code = execute("cold_stop",compose("stop"),timeout=45)
        if code: return code
        return execute("cold_up",compose("up","-d","--wait","--wait-timeout","180","--pull","never","--no-build"),timeout=200)
    if action == "expiry":
        started = timestamp()
        code = execute("expiry_stop", compose("stop", "scheduler", "worker"), timeout=30)
        if code:
            return code
        probe = """import json,os,urllib.request,urllib.error
from datetime import UTC,datetime
from sqlalchemy import create_engine,text
engine=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':3})
with engine.connect() as connection:
 rows=connection.execute(text('SELECT component,observed_at FROM runtime_observations ORDER BY component')).all()
 ages={r[0]:(datetime.now(UTC)-r[1]).total_seconds() for r in rows}
engine.dispose()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try: response=opener.open('http://127.0.0.1:28201/v1/health/ready',timeout=10)
except urllib.error.HTTPError as error: response=error
payload=json.load(response)
print(json.dumps({'time':datetime.now().astimezone().isoformat(timespec='seconds'),'ages':ages,'http':response.status,'states':{k:v['state'] for k,v in payload['dependencies'].items()}}))
"""
        deadline = time.monotonic() + 52
        samples = []
        while True:
            result = subprocess.run([str(BACKEND / ".venv/Scripts/python.exe"), "-c", probe], cwd=ROOT, env=ENVIRONMENT, capture_output=True, text=True, timeout=15, check=True)
            sample = json.loads(result.stdout)
            samples.append(sample)
            if min(sample["ages"].values()) >= 47:
                assert sample["http"] == 503
                assert sample["states"]["worker"] == "not_observed_or_stale"
                assert sample["states"]["scheduler"] == "not_observed_or_stale"
                assert max(sample["ages"].values()) <= 60
                break
            if time.monotonic() >= deadline:
                raise AssertionError("expiry probe exceeded bounded real-time wait")
            time.sleep(2)
        record = {"cwd":str(ROOT),"start":started,"end":timestamp(),"exit":0,"samples":samples,"source_sha":SOURCE_SHA,"evidence_head":HEAD,"assertions":5,"pass":5,"fail":0,"skip":0}
        (OUTPUT / "expiry_observations.json").write_text(json.dumps(record,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"expiry_assertions":5,"pass":5,"last_sample":samples[-1]}),flush=True)
        return execute("expiry_restore", compose("start", "worker", "scheduler"), timeout=30)
    if action == "auth_live":
        source = """import json,os,secrets,uuid,urllib.request,urllib.error,http.cookiejar
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.infrastructure.database import build_engine
from ai_intel.api.authentication import AuthenticationSessionService,DatabaseUserDirectory
from ai_intel.domain.access import Role
engine=build_engine(ApplicationSettings(app_env='test',database_url=os.environ['TEST_DATABASE_URL']))
directory=DatabaseUserDirectory(engine)
service=AuthenticationSessionService(directory,('http://127.0.0.1:25201',),False)
username='review-r01-'+uuid.uuid4().hex;password=secrets.token_urlsafe(32)
service.create_precreated_user(username,password,'review-r01-runtime-tenant',Role.ANALYST)
cookies=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.ProxyHandler({}),urllib.request.HTTPCookieProcessor(cookies))
def request(path,payload=None,csrf=None,origin='http://127.0.0.1:25201'):
 headers={'Origin':origin};body=None
 if payload is not None: body=json.dumps(payload).encode();headers['Content-Type']='application/json'
 if csrf is not None: headers['X-CSRF-Token']=csrf
 method='POST' if payload is not None or path.endswith('/logout') else 'GET'
 try: response=opener.open(urllib.request.Request('http://127.0.0.1:28201/v1/auth/'+path,data=body,headers=headers,method=method),timeout=8)
 except urllib.error.HTTPError as error: response=error
 return response.status,json.load(response)
status,login=request('login',{'username':username,'password':password});assert status==200
csrf=login['csrf_token'];status,me=request('me');assert status==200 and me['role']=='analyst' and me['tenant_id']=='review-r01-runtime-tenant' and me['data_mode']=='live'
status,_=request('logout',{},csrf,origin='https://invalid.example');assert status==403
status,_=request('me');assert status==200
status,_=request('logout',{},csrf);assert status==200
status,_=request('me');assert status==401
print(json.dumps({'actual_pg_directory':True,'login':200,'me_scope':200,'wrong_origin':403,'logout':200,'me_after_logout':401,'session_credential_logged':False,'assertions':6,'pass':6,'fail':0,'skip':0}))
engine.dispose()
"""
        return execute(action, [str(BACKEND / ".venv/Scripts/python.exe"), "-c", source], timeout=30)
    if action == "old_schema_verified":
        source = """import json,os,uuid
from sqlalchemy import create_engine,text
from sqlalchemy.engine import make_url
from fastapi import FastAPI
from fastapi.testclient import TestClient
from redis import Redis
from ai_intel.api.app import build_health_router
from ai_intel.infrastructure.settings import ApplicationSettings
engine=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':3})
schema='review_r01_old_'+uuid.uuid4().hex
with engine.begin() as connection:
 assert connection.execute(text('SELECT current_database(),current_user')).one()==('test_dianzi_r01_infra_20261015','test_dianzi_r01_infra')
 connection.execute(text('CREATE SCHEMA '+schema))
 connection.execute(text('CREATE TABLE '+schema+'.alembic_version(version_num varchar(32) PRIMARY KEY)'))
 connection.execute(text('INSERT INTO '+schema+".alembic_version VALUES ('0004_jobs_outbox')"))
url=make_url(os.environ['TEST_DATABASE_URL']).update_query_dict({'options':'-csearch_path='+schema}).render_as_string(hide_password=False)
configuration=ApplicationSettings(app_env='test',data_mode='live',database_url=url,redis_url=os.environ['TEST_REDIS_URL'],opensearch_url=os.environ['TEST_OPENSEARCH_URL'],allowed_origins=('http://127.0.0.1:25201',))
schema_engine=create_engine(url,connect_args={'connect_timeout':3})
cache=Redis.from_url(os.environ['TEST_REDIS_URL'],socket_connect_timeout=3,socket_timeout=3)
application=FastAPI();application.include_router(build_health_router(configuration,schema_engine,cache),prefix='/v1')
with TestClient(application) as client:
 response=client.get('/v1/health/ready');payload=response.json()
 assert response.status_code==503 and payload['dependencies']['database']['state']=='migration_required'
with engine.connect() as connection:
 assert connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()=='0005_runtime_observations'
 assert connection.execute(text('SELECT version_num FROM '+schema+'.alembic_version')).scalar_one()=='0004_jobs_outbox'
print(json.dumps({'isolated_schema':schema,'actual_pg':True,'readiness_route_engine_injected':True,'ready_http':response.status_code,'ready_database_state':payload['dependencies']['database']['state'],'main_revision_preserved':'0005_runtime_observations','old_revision_preserved':'0004_jobs_outbox','automatic_migration':False,'assertions':3,'pass':3,'fail':0,'skip':0}))
engine.dispose();schema_engine.dispose();cache.close()
"""
        return execute(action, [str(BACKEND / ".venv/Scripts/python.exe"), "-c", source], timeout=30)
    if action == "image_source_verified":
        files = subprocess.check_output(["git", "ls-tree", "-r", "--name-only", SOURCE_SHA, "backend/src", "backend/migrations", "backend/pyproject.toml", "backend/uv.lock", "frontend/src", "frontend/package.json", "frontend/package-lock.json", "frontend/index.html", "frontend/tsconfig.json", "frontend/vite.config.ts"], cwd=ROOT, text=True).splitlines()
        expected = {name: hashlib.sha256(subprocess.check_output(["git", "show", SOURCE_SHA+":"+name], cwd=ROOT)).hexdigest() for name in files}
        (OUTPUT / "image_source_verified_expected.json").write_text(json.dumps({"source_sha":SOURCE_SHA,"git_tree":subprocess.check_output(["git","rev-parse",SOURCE_SHA+"^{tree}"],cwd=ROOT,text=True).strip(),"files":expected},indent=2)+"\n",encoding="utf-8")
        for component, container, runtime in (("backend","api","python"),("frontend","frontend","node")):
            paths = [name.removeprefix(component+"/") for name in files if name.startswith(component+"/")]
            if runtime == "python":
                source = "import sys,json,pathlib,hashlib;print(json.dumps({x:{'raw_sha256':hashlib.sha256((pathlib.Path('/app')/x).read_bytes()).hexdigest(),'lf_sha256':hashlib.sha256((pathlib.Path('/app')/x).read_bytes().replace(bytes([13,10]),bytes([10]))).hexdigest()} for x in json.loads(sys.argv[1])}))"
                arguments = [*DOCKER,"exec",PROJECT+"-"+container+"-1","python","-c",source,json.dumps(paths)]
            else:
                source = "const fs=require('fs'),crypto=require('crypto');const paths=JSON.parse(process.argv[1]);console.log(JSON.stringify(Object.fromEntries(paths.map(x=>{let b=fs.readFileSync('/app/'+x);return [x,{raw_sha256:crypto.createHash('sha256').update(b).digest('hex'),lf_sha256:crypto.createHash('sha256').update(b.toString('utf8').replace(/\\r\\n/g,'\\n')).digest('hex')}]}))))"
                arguments = [*DOCKER,"exec",PROJECT+"-"+container+"-1","node","-e",source,json.dumps(paths)]
            code = execute("image_source_verified_"+component,arguments,timeout=30)
            if code: return code
            actual = json.loads((OUTPUT / ("image_source_verified_"+component+".stdout.log")).read_text())
            assert {name:value['lf_sha256'] for name,value in actual.items()} == {name.removeprefix(component+"/"):value for name,value in expected.items() if name.startswith(component+"/")}
            assert {name:value['raw_sha256'] for name,value in actual.items()} == {name.removeprefix(component+'/'):hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in files if name.startswith(component+'/')}
        print(json.dumps({"source_sha":SOURCE_SHA,"files_checked":len(files),"mismatches":0}),flush=True)
        return 0
    if action == "queue_live":
        source = """import json
from ai_intel.workers.runtime import celery_app
from importlib.metadata import version
configuration=celery_app.conf
assert version('celery')=='5.6.3'
assert configuration.result_backend is None and configuration.task_ignore_result and not configuration.task_store_errors_even_if_ignored
assert configuration.accept_content==['json'] and configuration.task_serializer=='json'
assert configuration.task_default_queue=='ai_intel' and configuration.task_time_limit==30 and configuration.task_soft_time_limit==25
assert configuration.worker_concurrency==1 and configuration.worker_prefetch_multiplier==1
stats=celery_app.control.inspect(timeout=6).stats()
assert stats and len(stats)==1
worker=next(iter(stats.values()));assert worker['pool']['max-concurrency']==1 and 'prefork' in worker['pool']['implementation']
print(json.dumps({'celery':version('celery'),'result_backend':configuration.result_backend,'ignore_result':configuration.task_ignore_result,'content':configuration.accept_content,'default_queue':configuration.task_default_queue,'hard_limit':configuration.task_time_limit,'soft_limit':configuration.task_soft_time_limit,'actual_pool':worker['pool']['implementation'],'actual_concurrency':worker['pool']['max-concurrency'],'assertions':6,'pass':6,'fail':0,'skip':0}))
"""
        return execute(action,[*DOCKER,"exec",PROJECT+"-api-1","python","-c",source],timeout=15)
    if action == "search_base_path":
        return execute(action,[*DOCKER,"exec",PROJECT+"-opensearch-1","grep","-n","-E","ssl.http.enabled|ssl.http.pemcert_filepath|ssl.http.pemtrustedcas_filepath|CN=","/usr/share/opensearch/plugins/opensearch-security/tools/install_demo_configuration.sh"],timeout=15)
    if action == "listeners":
        return execute(action, [*WSL, "ss", "-H", "-ltnp", "( sport = :25436 or sport = :26383 or sport = :29201 or sport = :29301 or sport = :28201 or sport = :25201 )"])
    if action == "auth_pg_failed":
        source = """import json,urllib.request,urllib.error
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
request=urllib.request.Request('http://127.0.0.1:28201/v1/auth/login',data=json.dumps({'username':'review-unavailable','password':'synthetic-only'}).encode(),headers={'Origin':'http://127.0.0.1:25201','Content-Type':'application/json'},method='POST')
try: response=opener.open(request,timeout=10)
except urllib.error.HTTPError as error: response=error
payload=json.load(response)
assert response.status==503 and payload['error']['code']=='authentication_unavailable'
assert 'synthetic-only' not in json.dumps(payload) and 'password' not in json.dumps(payload)
print(json.dumps({'http':response.status,'content_type':response.headers['Content-Type'],'error_code':payload['error']['code'],'credential_echo':False,'assertions':2,'pass':2,'fail':0,'skip':0}))
"""
        return execute(action,[str(BACKEND / ".venv/Scripts/python.exe"),"-c",source],timeout=15)
    if action.startswith("health_"):
        source = """import json,os,urllib.request,urllib.error
from datetime import UTC,datetime
from sqlalchemy import create_engine,text
engine=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':3})
try:
 with engine.connect() as connection:
  identity=connection.execute(text('SELECT current_database(),current_user')).one()
  assert identity[0]=='test_dianzi_r01_infra_20261015' and identity[1]=='test_dianzi_r01_infra'
  version=connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
  rows=connection.execute(text('SELECT component,observed_at,platform_version FROM runtime_observations ORDER BY component')).all()
  print(json.dumps({'database':identity[0],'user':identity[1],'migration':version,'observations':[{'component':r[0],'observed_at':r[1].isoformat(),'age_seconds':(datetime.now(UTC)-r[1]).total_seconds(),'platform_version':r[2]} for r in rows]}))
except Exception as error:
 print(json.dumps({'database_probe_failed':type(error).__name__}))
finally: engine.dispose()
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
try: response=opener.open('http://127.0.0.1:28201/v1/health/ready',timeout=10)
except urllib.error.HTTPError as error: response=error
print(json.dumps({'api_status':response.status,'payload':json.load(response)}))
"""
        return execute(action, [str(BACKEND / ".venv/Scripts/python.exe"), "-c", source], timeout=20)
    if action.startswith("pytest_"):
        label = action
        selected = {"pytest_t03": ["tests/integration/test_t03_development_services.py"], "pytest_runtime": ["tests/unit/test_r01_worker_configuration.py", "tests/contract/test_r01_compose_configuration.py", "tests/contract/test_r01_quality_checks.py", "tests/security/test_r01_admin_error_redaction.py", "tests/security/test_r01_http_authentication.py"]}[action]
        return execute(label, ["uv", "run", "--locked", "pytest", *selected, "-q", "--cov-fail-under=0", f"--junitxml={OUTPUT / (label + '.xml')}"], cwd=BACKEND, timeout=180)
    if action.startswith("scope_"):
        return execute(action, [str(BACKEND / ".venv/Scripts/python.exe"), "scripts/dev.py", "check", "--scope", action.removeprefix("scope_"), "--timeout-seconds", "600"], timeout=660)
    if action in {"ruff", "format", "mypy"}:
        arguments = {"ruff":["ruff","check",".","../scripts/dev.py"],"format":["ruff","format","--check",".","../scripts/dev.py"],"mypy":["mypy","src","../scripts/dev.py"]}[action]
        return execute(action,["uv","run","--locked",*arguments],cwd=BACKEND,timeout=60)
    if action == "delivery_diff":
        return execute(action,["git","diff","--check","05aa146","HEAD"],timeout=15)
    if action == "cold_frontend_logs":
        return execute(action,[*DOCKER,"logs","--tail","100",PROJECT+"-frontend-1"],timeout=15)
    if action == "frontend_recreate":
        assert_target()
        return execute(action,compose("up","-d","--no-deps","--force-recreate","--wait","--wait-timeout","90","--pull","never","--no-build","frontend"),timeout=100)
    if action == "frontend_tmpfs":
        source = "const fs=require('fs');const paths=['/tmp','/app/node_modules/.vite','/app/node_modules/.vite-temp'];console.log(JSON.stringify({uid:process.getuid(),gid:process.getgid(),directories:paths.map(path=>{let s=fs.statSync(path),writable=true;try{fs.accessSync(path,fs.constants.W_OK)}catch(e){writable=false}return {path,uid:s.uid,gid:s.gid,mode:(s.mode&511).toString(8),writable}})}))"
        return execute(action,[*DOCKER,"exec",PROJECT+"-frontend-1","node","-e",source],timeout=15)
    if action == "frontend_http_restored":
        source="import urllib.request,json;opener=urllib.request.build_opener(urllib.request.ProxyHandler({}));r=opener.open('http://127.0.0.1:25201/',timeout=5);assert r.status==200;print(json.dumps({'frontend_http':r.status,'browser_ui_e2e_checked':False}))"
        return execute(action,[str(BACKEND / ".venv/Scripts/python.exe"),"-c",source],timeout=10)
    if action in {"summarize", "summarize_final"}:
        scopes=[]
        for scope in ("unit","contract","security","integration"):
            lines=(OUTPUT/('scope_'+scope+'.stdout.log')).read_text().splitlines()
            count=next(json.loads(line) for line in reversed(lines) if line.startswith('{"scope"'))
            receipt=json.loads((OUTPUT/('scope_'+scope+'.json')).read_text())
            scopes.append({**receipt,"actual_report_counts":count})
        (OUTPUT/('scope_summary_final.json' if action=='summarize_final' else 'scope_summary.json')).write_text(json.dumps(scopes,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        candidates=[path for path in OUTPUT.rglob('*') if path.is_file()]
        credentials=[value for name,value in ENVIRONMENT.items() if value and ('PASSWORD' in name or name in {'TEST_DATABASE_URL','TEST_REDIS_URL','COMPOSE_DATABASE_URL','COMPOSE_REDIS_URL'})]
        report=Path(r'D:\dianzi\reports\reviews\recovery\G-A-R01-runtime-review-1.md')
        if report.is_file(): candidates.append(report)
        findings=[str(path) for path in candidates if any(secret.encode() in path.read_bytes() for secret in credentials)]
        record={'time':timestamp(),'files':len(candidates),'credential_matches':len(findings),'assigned_test_connection_read':True,'other_secret_material_read':False,'source_sha':SOURCE_SHA,'evidence_head':HEAD,'scopes':[{k:count for k,count in item['actual_report_counts'].items()} for item in scopes]}
        (OUTPUT/('final_summary_final.json' if action=='summarize_final' else 'final_summary.json')).write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(record,ensure_ascii=False),flush=True)
        return 1 if findings else 0
    if action == "fixture_permission":
        source = """import importlib.util,json,subprocess
from pathlib import Path
from unittest.mock import patch
import pytest
from scripts import dev
path=Path('backend/tests/integration/test_t03_development_services.py')
spec=importlib.util.spec_from_file_location('review_t03_fixture',path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
with patch.object(module,'run_compose_services',side_effect=PermissionError('synthetic permission denial')):
 try: module.run_compose('ps')
 except pytest.UsageError as error: assert 'blocked' in str(error) and 'PermissionError' in str(error)
 else: raise AssertionError('permission error unexpectedly passed')
with patch.object(dev,'_run_command',side_effect=PermissionError('synthetic permission denial')):
 code=dev.run_scope_checks('integration');assert code==4
print(json.dumps({'case':'T03-C05','data_mode':'fixture','permission_denial':'synthetic','actual_permission_changed':False,'container_io':False,'scope_exit':code,'sqlite_substitute':False,'assertions':2,'pass':2,'fail':0,'skip':0}))
"""
        return execute(action,[str(BACKEND / ".venv/Scripts/python.exe"),"-c",source],timeout=10)
    if action == "cbm_schema":
        return execute(action, [*WSL, "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "schema", "index_repository"])
    if action in {"cbm_index", "cbm_scripts"}:
        scope = "backend/src" if action == "cbm_index" else "scripts"
        return execute(action, [*WSL, "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r01-runtime-review-1-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "index_repository", "--repo-path", "/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-infra/dianzi/"+scope, "--name", "dianzi-runtime-review-"+scope.replace('/', '-'), "--persistence", "false"], timeout=30)
    if action == "cbm_trace":
        return execute(action, [*WSL, "/usr/bin/env", "CBM_CACHE_DIR=/tmp/dianzi-cbm-r01-runtime-review-1-20261015", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "get_file_outline", "--project", "dianzi-runtime-review-backend-src", "--file-path", "ai_intel/workers/runtime.py", "--format", "json"], timeout=15)
    raise ValueError("unknown review action")


if __name__ == "__main__":
    raise SystemExit(main())
