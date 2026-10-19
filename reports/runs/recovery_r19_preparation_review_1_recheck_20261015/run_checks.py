"""Run fixed-SHA independent checks without touching product code or real holdout."""
import concurrent.futures
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path('D:/wt/r19-preparation-review-fix1')
RUN=ROOT/'reports/runs/recovery_r19_preparation_review_1_recheck_20261015'
PYTHON='D:/dianzi/backend/.venv/Scripts/python.exe'
ZONE=timezone(timedelta(hours=8))

def now():
    return datetime.now(ZONE).isoformat(timespec='seconds')

def run(name,args):
    start=now()
    p=subprocess.run(args,cwd=ROOT,capture_output=True,check=False)
    log=RUN/(name+'.log')
    log.write_bytes(p.stdout+p.stderr)
    return {'name':name,'argv':args,'cwd':str(ROOT),'started_at':start,'ended_at':now(),
            'exit_code':p.returncode,'log':str(log.relative_to(ROOT)),
            'sha256':hashlib.sha256(log.read_bytes()).hexdigest()}

if __name__=='__main__':
    commands=[
        ('annotation_unittest',[PYTHON,'-m','unittest','discover','-s','scripts/annotation/tests','-v']),
        ('plan_pytest',[PYTHON,'-m','pytest','tests/plan/test_verify_plan.py','tests/plan/test_recovery_plan.py','-q']),
        ('ruff',[PYTHON,'-m','ruff','check','scripts/annotation']),
        ('format',[PYTHON,'-m','ruff','format','--check','scripts/annotation']),
        ('mypy',[PYTHON,'-m','mypy','scripts/annotation/prepare.py','--follow-imports=silent','--follow-untyped-imports']),
        ('verify_plan',[PYTHON,'scripts/verify_plan.py']),
        ('real_candidate',[PYTHON,'scripts/annotation/prepare.py','validate','--input','benchmarks/manifests/r19_public_dev_candidate_v1.json']),
        ('diff_check',['git','diff','--check','a0c76800202a9869c4e24918b84893ebcec52a61','22d809f7803d539a2b551eb878ceae5333182d83']),
        ('rg_callers',['rg','-n','validate_candidates|inspect_annotations|scan_leaks|protected_roots|require_external|annotation/prepare.py','scripts','backend/src','frontend/src','docs/runbooks']),
        ('git_identity',['git','log','-4','--format=%H %s']),
    ]
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
        results=list(pool.map(lambda command:run(*command),commands))
    (RUN/'commands.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(results,ensure_ascii=False,indent=2))
