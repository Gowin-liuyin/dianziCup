"""只复核冻结缓存修复；容器操作限已交接的唯一测试项目。"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from xml.etree import ElementTree

ROOT = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-infra-fix\dianzi")
OUTPUT = Path(__file__).resolve().parent
PYTHON = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-infra\dianzi\backend\.venv\Scripts\python.exe")
SOURCE = "32d16a4a055a46da2f2183f367075db686ddd790"
HEAD = "eff45e5f933a002d429ded7557dc29fbf48dd729"
PROJECT = "dianzi-test-r01_infra_20261015"
WSL = ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec"]
DOCKER_LINUX = ["/tmp/dianzi-docker-static-r01-20261014/portable/docker/docker", "--config", "/tmp/dianzi-docker-static-r01-20261014/runtime/client-config", "--host", "unix:///tmp/dianzi-docker-static-r01-20261014/runtime/docker.sock"]
DOCKER = [*WSL, *DOCKER_LINUX]
ENVIRONMENT = dict(os.environ)
ENVIRONMENT["PYTHONIOENCODING"] = "utf-8"
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == HEAD


def timestamp() -> str:
    return datetime.now(timezone(timedelta(hours=8))).isoformat(timespec="seconds")


def load_environment() -> None:
    source = "import pathlib,sys;sys.stdout.write(pathlib.Path(sys.argv[1]).read_text())"
    result = subprocess.run([*WSL, "python3", "-c", source, "/tmp/dianzi-r01-infra-20261015/connection.json"], capture_output=True, text=True, timeout=10, check=True)
    configured = json.loads(result.stdout)
    assert set(configured) == {"run_id", "environment"}
    assert configured["run_id"] == "r01_infra_20261015"
    private_environment = configured["environment"]
    assert private_environment["DIANZI_TEST_COMPOSE_PROJECT"] == PROJECT
    for name, compose_name in {"DATABASE_URL":"COMPOSE_DATABASE_URL", "REDIS_URL":"COMPOSE_REDIS_URL", "ALLOWED_ORIGINS":"COMPOSE_ALLOWED_ORIGINS"}.items():
        if name in private_environment:
            private_environment[compose_name] = private_environment.pop(name)
    ENVIRONMENT.update(private_environment)
    ENVIRONMENT["COMPOSE_DISABLE_ENV_FILE"] = "1"
    ENVIRONMENT["DIANZI_DOCKER_COMMAND_JSON"] = json.dumps(DOCKER)
    ENVIRONMENT["DIANZI_TEST_COMPOSE_FILE"] = str(ROOT / "infra/compose/compose.test.host.yaml")
    ENVIRONMENT["DIANZI_COMPOSE_FILE"] = ENVIRONMENT["DIANZI_TEST_COMPOSE_FILE"]
    ENVIRONMENT["DIANZI_COMPOSE_PROJECT"] = PROJECT
    ENVIRONMENT["TEST_BACKEND_IMAGE"] = "dianzi-r01-infra-backend:d7290cf42409"
    ENVIRONMENT["TEST_FRONTEND_IMAGE"] = "dianzi-r01-infra-frontend:bc24286a3a80"
    ENVIRONMENT["WSLENV"] = ":".join(sorted({*private_environment,"COMPOSE_DISABLE_ENV_FILE","TEST_BACKEND_IMAGE","TEST_FRONTEND_IMAGE"}))


def redact(content: str) -> str:
    for name, value in ENVIRONMENT.items():
        if value and ("PASSWORD" in name or "PROXY" in name or name in {"TEST_DATABASE_URL","TEST_REDIS_URL","COMPOSE_DATABASE_URL","COMPOSE_REDIS_URL"}):
            content = content.replace(value,"[redacted test credential]")
    return content


def execute(label: str, arguments: list[str], cwd: Path = ROOT, timeout: int = 60) -> int:
    started = timestamp()
    clock = time.monotonic()
    try:
        result = subprocess.run(arguments,cwd=cwd,env=ENVIRONMENT,capture_output=True,text=True,encoding="utf-8",errors="replace",timeout=timeout)
        stdout,stderr,code = result.stdout,result.stderr,result.returncode
    except subprocess.TimeoutExpired as error:
        stdout=error.stdout.decode(errors="replace") if isinstance(error.stdout,bytes) else error.stdout or ""
        stderr=error.stderr.decode(errors="replace") if isinstance(error.stderr,bytes) else error.stderr or ""
        code=124
    (OUTPUT/(label+".stdout.log")).write_text(redact(stdout),encoding="utf-8")
    (OUTPUT/(label+".stderr.log")).write_text(redact(stderr),encoding="utf-8")
    counts=None
    xml=OUTPUT/(label+".xml")
    if xml.is_file():
        cases=ElementTree.parse(xml).findall(".//testcase")
        counts={"total":len(cases),"pass":sum(all(case.find(k) is None for k in ("failure","error","skipped")) for case in cases),"fail":sum(case.find("failure") is not None for case in cases),"error":sum(case.find("error") is not None for case in cases),"skip":sum(case.find("skipped") is not None for case in cases)}
    receipt={"label":label,"cwd":str(cwd),"argv":arguments,"start":started,"end":timestamp(),"exit":code,"wall_seconds":time.monotonic()-clock,"source_sha":SOURCE,"evidence_head":HEAD,"counts":counts}
    (OUTPUT/(label+".json")).write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"label":label,"exit":code,"counts":counts}),flush=True)
    return code


def compose(*arguments: str) -> list[str]:
    return [*DOCKER,"compose","--project-name",PROJECT,"-f","/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-infra-fix/dianzi/infra/compose/compose.test.host.yaml","--profile","core","--profile","search","--profile","app","--profile","worker","--profile","scheduler","--profile","frontend",*arguments]


def containers() -> list[dict]:
    ids=subprocess.check_output([*DOCKER,"ps","--all","--filter","label=com.docker.compose.project="+PROJECT,"--format","{{.ID}}"],cwd=ROOT,env=ENVIRONMENT,text=True,timeout=10).split()
    assert len(ids)==7
    rows=json.loads(subprocess.check_output([*DOCKER,"inspect",*ids],cwd=ROOT,env=ENVIRONMENT,text=True,timeout=10))
    for row in rows:
        labels=row["Config"]["Labels"]
        assert labels["com.docker.compose.project"]==PROJECT
        assert labels["com.docker.compose.project.working_dir"]=="/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-infra-fix/dianzi/infra/compose"
        assert labels["com.docker.compose.project.config_files"]=="/mnt/c/Users/yinha/.codex/worktrees/recovery-r01-infra-fix/dianzi/infra/compose/compose.test.host.yaml"
        assert row["HostConfig"]["NetworkMode"]=="host"
        service=labels["com.docker.compose.service"]
        if service in {"api","worker","scheduler"}:
            assert row["Image"]=="sha256:34b24db5595ed36fc608f39f648d5a9a2288cb03a2ca8f1ecd123044158ea7b0"
        if service=="frontend":
            assert row["Image"]=="sha256:de3c406ba2f65e60273a8e545de8ce0eca3bd9b6c54aebd62de33d8bc382c439"
            assert row["Config"]["User"]=="node"
            assert row["HostConfig"]["ReadonlyRootfs"] is True
            for path in ("/app/node_modules/.vite","/app/node_modules/.vite-temp"):
                assert row["HostConfig"]["Tmpfs"][path]=="uid=1000,gid=1000,mode=0700"
    return rows


def snapshot(label: str) -> None:
    started=timestamp()
    rows=containers()
    deadline=time.monotonic()+30
    while not all(row['State']['Status']=='running' and row['State'].get('Health',{}).get('Status')=='healthy' for row in rows):
        if time.monotonic()>=deadline:
            raise AssertionError('container health did not converge within 30 seconds')
        time.sleep(1)
        rows=containers()
    filtered=[{"id":row["Id"],"name":row["Name"],"image_id":row["Image"],"project":row["Config"]["Labels"]["com.docker.compose.project"],"working_dir":row["Config"]["Labels"]["com.docker.compose.project.working_dir"],"config_files":row["Config"]["Labels"]["com.docker.compose.project.config_files"],"user":row["Config"]["User"],"status":row["State"]["Status"],"health":row["State"].get("Health",{}).get("Status"),"read_only":row["HostConfig"]["ReadonlyRootfs"],"tmpfs":row["HostConfig"].get("Tmpfs",{}),"cap_drop":row["HostConfig"]["CapDrop"],"network_mode":row["HostConfig"]["NetworkMode"],"port_bindings":row["HostConfig"]["PortBindings"],"volume_names":[mount["Name"] for mount in row["Mounts"] if mount["Type"]=="volume"]} for row in rows]
    assert all(row["status"]=="running" and row["health"]=="healthy" for row in filtered)
    (OUTPUT/(label+".json")).write_text(json.dumps({"cwd":str(ROOT),"start":started,"end":timestamp(),"exit":0,"source_sha":SOURCE,"evidence_head":HEAD,"containers":filtered},indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"snapshot":label,"healthy":len(filtered)}),flush=True)


def live_probe(label: str) -> int:
    source="""import json,os,time,urllib.request,urllib.error
from datetime import UTC,datetime
from sqlalchemy import create_engine,text
opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
deadline=time.monotonic()+30
while True:
 try:
  with opener.open('http://127.0.0.1:25201/',timeout=3) as response: assert response.status==200
  break
 except (urllib.error.URLError,OSError):
  if time.monotonic()>=deadline: raise
  time.sleep(.5)
with opener.open('http://127.0.0.1:28201/v1/health/ready',timeout=6) as response:
 payload=json.load(response);assert response.status==200 and payload['status']=='ready'
 assert all(v['state']=='ready' for v in payload['dependencies'].values())
engine=create_engine(os.environ['TEST_DATABASE_URL'],connect_args={'connect_timeout':3})
with engine.connect() as connection:
 identity=connection.execute(text('SELECT current_database(),current_user')).one();assert identity==('test_dianzi_r01_infra_20261015','test_dianzi_r01_infra')
 version=connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one();assert version=='0005_runtime_observations'
 note=connection.execute(text('SELECT note FROM t03_volume_probe WHERE id=1')).scalar_one();assert note=='survives-down-up'
 rows=connection.execute(text('SELECT component,observed_at FROM runtime_observations ORDER BY component')).all()
 assert {r[0] for r in rows}=={'worker','scheduler'}
 observations={r[0]:r[1].isoformat() for r in rows};ages={r[0]:(datetime.now(UTC)-r[1]).total_seconds() for r in rows};assert all(0<=age<=45 for age in ages.values())
engine.dispose()
print(json.dumps({'frontend_http':200,'api_http':200,'all_required_dependencies_ready':True,'database':identity[0],'user':identity[1],'migration':version,'persistent_probe_note':note,'observations':observations,'ages_seconds':ages,'assertions':7,'pass':7,'fail':0,'skip':0,'ui_e2e_checked':False}))
"""
    return execute(label,[str(PYTHON),"-c",source],timeout=40)


def cache_probe(label: str) -> int:
    source="const fs=require('fs'),crypto=require('crypto');if(process.getuid()!==1000||process.getgid()!==1000)throw Error('unexpected Node identity');const directories=['/app/node_modules/.vite','/app/node_modules/.vite-temp'].map(path=>{const s=fs.statSync(path);if(s.uid!==1000||s.gid!==1000||(s.mode&511)!==448)throw Error('unexpected cache permission');const name=path+'/review-cache-probe-'+crypto.randomUUID();fs.writeFileSync(name,'synthetic cache probe',{flag:'wx'});if(fs.readFileSync(name,'utf8')!=='synthetic cache probe')throw Error('cache write/read failed');fs.unlinkSync(name);return {path,uid:s.uid,gid:s.gid,mode:(s.mode&511).toString(8),write_read_delete_own_probe:true}});console.log(JSON.stringify({uid:process.getuid(),gid:process.getgid(),directories,assertions:5,pass:5,fail:0,skip:0}))"
    return execute(label,[*DOCKER,"exec",PROJECT+"-frontend-1","node","-e",source],timeout=15)


def main() -> int:
    load_environment()
    action=sys.argv[1]
    if action=="contract":
        return execute(action,["uv","run","--locked","pytest","tests/contract/test_r01_compose_configuration.py","-q","--cov-fail-under=0","--junitxml="+str(OUTPUT/"contract.xml")],cwd=ROOT/"backend",timeout=120)
    if action in {"ruff","format"}:
        args=["ruff","check"] if action=="ruff" else ["ruff","format","--check"]
        return execute(action,["uv","run","--locked",*args,"tests/contract/test_r01_compose_configuration.py"],cwd=ROOT/"backend",timeout=30)
    if action=="before":
        snapshot("before_containers")
        code=cache_probe("before_cache")
        return code or live_probe("before_live")
    if action=="same_restart":
        rows=containers();identifier=next(row["Id"] for row in rows if row["Config"]["Labels"]["com.docker.compose.service"]=="frontend")
        code=execute("same_stop",compose("stop","frontend"),timeout=30)
        if code:return code
        code=execute("same_start",compose("start","frontend"),timeout=30)
        if code:return code
        code=live_probe("same_live")
        if code:return code
        code=cache_probe("same_cache")
        if code:return code
        snapshot("same_containers")
        after=containers();assert next(row["Id"] for row in after if row["Config"]["Labels"]["com.docker.compose.service"]=="frontend")==identifier
        print(json.dumps({'same_frontend_container_id_preserved':True}),flush=True)
        return 0
    if action=="same_finalize":
        code=live_probe('same_live_final')
        if code:return code
        code=cache_probe('same_cache_final')
        if code:return code
        snapshot('same_containers')
        before=json.loads((OUTPUT/'before_containers.json').read_text())['containers']
        after=json.loads((OUTPUT/'same_containers.json').read_text())['containers']
        identifier=lambda rows:next(row['id'] for row in rows if row['name'].endswith('-frontend-1'))
        assert identifier(before)==identifier(after)
        (OUTPUT/'same_container_identity.json').write_text(json.dumps({'source_sha':SOURCE,'evidence_head':HEAD,'frontend_id_before':identifier(before),'frontend_id_after':identifier(after),'same_container':True,'exit':0,'verified_at':timestamp()},indent=2)+'\n',encoding='utf-8')
        print(json.dumps({'same_frontend_container_id_preserved':True}),flush=True)
        return 0
    if action=="cold":
        rows=containers()
        volume_names=sorted({mount["Name"] for row in rows for mount in row["Mounts"] if mount["Type"]=="volume"})
        assert len(volume_names)==4 and all(name.startswith(PROJECT+"_") for name in volume_names)
        (OUTPUT/'cold_volume_names.json').write_text(json.dumps(volume_names,indent=2)+'\n',encoding='utf-8')
        code=execute("cold_down",compose("down"),timeout=60)
        if code:return code
        code=execute("cold_volumes_retained",[*DOCKER,"volume","inspect",*volume_names,"--format","{{.Name}}"],timeout=15)
        if code:return code
        code=execute("cold_up",compose("up","-d","--wait","--wait-timeout","180","--pull","never","--no-build"),timeout=200)
        if code:return code
        code=live_probe("cold_live")
        if code:return code
        code=cache_probe("cold_cache")
        if code:return code
        snapshot("cold_containers")
        started=datetime.fromisoformat(json.loads((OUTPUT/'cold_up.json').read_text())['start'])
        observed=json.loads((OUTPUT/'cold_live.stdout.log').read_text())['observations']
        assert all(datetime.fromisoformat(value)>started for value in observed.values())
        print(json.dumps({'new_pg_worker_scheduler_observations_after_cold_up':True,'volumes_retained':len(volume_names)}),flush=True)
        return 0
    if action=="source_diff":
        return execute(action,["git","diff","--check","0b6a7ad","HEAD","--","infra/compose/compose.yaml","backend/tests/contract/test_r01_compose_configuration.py"],timeout=10)
    if action=="final_scan":
        started=timestamp()
        report=Path(r'D:\dianzi\reports\reviews\recovery\G-A-R01-runtime-review-1-cache-recheck.md')
        files=[path for path in OUTPUT.rglob('*') if path.is_file()]+[report]
        credentials=[value for name,value in ENVIRONMENT.items() if value and ('PASSWORD' in name or name in {'TEST_DATABASE_URL','TEST_REDIS_URL','COMPOSE_DATABASE_URL','COMPOSE_REDIS_URL'})]
        matches=[str(path) for path in files if any(value.encode() in path.read_bytes() for value in credentials)]
        import hashlib
        original=Path(r'D:\dianzi\reports\reviews\recovery\G-A-R01-runtime-review-1.md')
        assert hashlib.sha256(original.read_bytes()).hexdigest()=='5515b541c6431c670e818b1ee66e4a8c857ca0a6edb8818150d09ce142ebf331'
        counts=json.loads((OUTPUT/'contract.json').read_text())['counts']
        result={'cwd':str(ROOT),'start':started,'end':timestamp(),'exit':1 if matches else 0,'source_sha':SOURCE,'evidence_head':HEAD,'files_scanned':len(files),'credential_matches':len(matches),'assigned_test_connection_read':True,'other_secret_material_read':False,'contract_counts':counts,'original_review_unchanged':True,'container_operations_ended':'2026-10-15T01:56:17+08:00','project_control_returned_to_root':True,'verdict':'cache recheck passed; overall R01 not accepted'}
        (OUTPUT/'final_scan.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(result,ensure_ascii=False),flush=True)
        return 1 if matches else 0
    raise ValueError('unknown cache recheck action')


if __name__=='__main__':
    raise SystemExit(main())
