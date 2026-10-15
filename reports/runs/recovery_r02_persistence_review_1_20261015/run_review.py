from pathlib import Path
import datetime, json, os, re, subprocess, sys
from urllib.parse import urlsplit, unquote
ROOT=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
WT=Path(r'C:\Users\yinha\.codex\worktrees\recovery-r02-review\dianzi')
name=sys.argv[1]
env=os.environ.copy()
env['UV_PROJECT_ENVIRONMENT']=str(ROOT/'venv')
env['PYTHONDONTWRITEBYTECODE']='1'
env['COVERAGE_FILE']=str(ROOT/(name+'.coverage'))
env['PYTHONPATH']=str(WT/'backend'/'src')+os.pathsep+str(ROOT)
secrets=[]
if sys.argv[2] != 'none':
    config='/tmp/dianzi-r02_'+sys.argv[2]+'_20261015/connection.json'
    completed=subprocess.run(['wsl','-d','Ubuntu-22.04','-u','root','--','python3','-c','import json;from pathlib import Path;print(Path('+repr(config)+').read_text())'],capture_output=True,text=True,check=True)
    settings=json.loads(completed.stdout)
    env.update(settings)
    secrets=[settings['TEST_DATABASE_URL']]
    password=unquote(urlsplit(settings['TEST_DATABASE_URL']).password or '')
    if password:
        secrets.append(password)
        if len(password)>=8:
            secrets.extend(password[i:i+8] for i in range(len(password)-7))
def clean(value):
    for secret in sorted(set(secrets),key=len,reverse=True):
        if secret:
            value=value.replace(secret,'[redacted]')
    return value
args=sys.argv[3:]
command=['uv','run','--locked',*args]
start=datetime.datetime.now().astimezone().isoformat()
result=subprocess.run(command,cwd=WT/'backend',env=env,capture_output=True,text=True,encoding='utf-8',errors='replace')
end=datetime.datetime.now().astimezone().isoformat()
stdout=clean(result.stdout)
stderr=clean(result.stderr)
(ROOT/(name+'.stdout.log')).write_text(stdout,encoding='utf-8')
(ROOT/(name+'.stderr.log')).write_text(stderr,encoding='utf-8')
meta={'start':start,'end':end,'cwd':str(WT/'backend'),'command':command,'exit_code':result.returncode,'fixed_sha':'0fe642b1c9e5fe4dafa2774e9432bd96079c1b72','config_source':sys.argv[2], 'test_run_id':env.get('DIANZI_TEST_RUN_ID'), 'secrets_redacted':True, 'counts': re.findall(r'\d+ (?:passed|failed|error|errors|skipped|deselected)',stdout)}
(ROOT/(name+'.command.json')).write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps(meta,ensure_ascii=False,indent=2))
print(stdout[-4500:])
print(stderr[-1800:])
sys.exit(result.returncode)
