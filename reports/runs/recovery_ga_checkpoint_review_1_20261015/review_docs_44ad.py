"""Strict fixed-document audit and synthetic tests of the archived scan boundary."""
from __future__ import annotations
import gzip
import hashlib
import json
import os
import secrets
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('D:/dianzi-ga-checkpoint-review-1-docs')
PREVIOUS=Path('D:/dianzi-ga-checkpoint-review-1-recheck')
RUN=Path('D:/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
SHA='44ad5db344dfc0a1c8c4e2a5a507bf08cc36ac25'

def at():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def strict(pairs):
    value={}
    for key,item in pairs:
        if key in value:raise ValueError('duplicate JSON key: '+key)
        value[key]=item
    return value
def read(path):return json.loads(path.read_text(encoding='utf-8'),object_pairs_hook=strict)
def git(*args):return subprocess.check_output(['git',*args],cwd=ROOT)

def check_docs():
    started=at()
    before=read(PREVIOUS/'progress/task_state.json')
    after=read(ROOT/'progress/task_state.json')
    manifest=read(ROOT/'contracts/task_manifest.json')
    requirements=read(ROOT/'contracts/requirements.json')
    changed=git('diff','--name-only','b27a79d9bce769564e86034a164010b3fd176080',SHA).decode().splitlines()
    outside=[name for name in changed if not name.startswith(('docs/','reports/','progress/'))]
    assert not outside
    assert before['tasks']==after['tasks']
    accepted_before={key for key,value in before['recovery_tasks'].items() if value['status']=='accepted'}
    accepted_after={key for key,value in after['recovery_tasks'].items() if value['status']=='accepted'}
    assert accepted_before==accepted_after=={'R00'}
    for key in ('R01','R02','R03'):
        assert after['recovery_tasks'][key]['status']=='awaiting_review'
        assert after['recovery_tasks'][key]['verification']['manual']=='not_run'
        assert after['recovery_tasks'][key]['verification']['live']=='not_run'
    original=git('show',SHA+':progress/history/G-A_pre_checkpoint_d9b8d6.md')
    expected=(RUN/'G-A_document_snapshot.md').read_bytes().replace(b'\r\n',b'\n')
    assert original==expected
    needed=[
      'reports/reviews/recovery/G-A-R01-behavior-review-1-final-recheck.md',
      'reports/reviews/recovery/G-A-R01-runtime-review-1-cache-recheck.md',
      'reports/reviews/recovery/G-A-R01-search-TLS-review-1.md',
      'reports/tasks/R01-runtime-recovery.md','reports/tasks/R02.md',
      'reports/runs/recovery_r01_controller_20261014/r02_default_auth_resume.command.json',
      'reports/runs/recovery_r01_controller_20261014/r02_default_auth_resume.xml',
      'reports/runs/recovery_r02_persistence_review_1_20261015/credential_failure.observed.json',
      'reports/runs/recovery_r01_controller_20261014/r02_relations_fix_first.command.json',
      'reports/reviews/recovery/G-A-R02-minio-integrated-review-1.md',
      'reports/reviews/recovery/G-A-R02-dimension-review-1.md']
    assert all((ROOT/name).is_file() for name in needed)
    result=dict(started_at=started,ended_at=at(),sha=SHA,tree=git('rev-parse','HEAD^{tree}').decode().strip(),changed_files=len(changed),outside_document_paths=outside,strict_json='passed',original_tasks_unchanged=True,accepted_recovery_before=sorted(accepted_before),accepted_recovery_after=sorted(accepted_after),r01_r03_scope={key:{field:after['recovery_tasks'][key].get(field) for field in ('status','implementation','verification')} for key in ('R01','R02','R03')},historical_stage_bytes_preserved=True,missing_evidence_resolved=needed,requirements_count=len(requirements['requirements']),original_task_count=len(manifest['tasks']),stage_sha256=hashlib.sha256((ROOT/'reports/stages/recovery/G-A.md').read_bytes()).hexdigest())
    (RUN/'docs_44ad_strict_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({key:result[key] for key in ('sha','tree','changed_files','outside_document_paths','strict_json','original_tasks_unchanged','historical_stage_bytes_preserved')},ensure_ascii=False))

def scanner_probes():
    scanner=ROOT/'reports/runs/recovery_r01_controller_20261014/scan_staged_secrets.py'
    names=('DEEPSEEK_API_KEY','HUNTER_API_KEY','FOFA_API_KEY','QUAKE_API_KEY','ZOOMEYE_API_KEY','TEST_PASSWORD','PG_PASSWORD','MINIO_ACCESS_KEY','MINIO_SECRET_KEY')
    fake={name:secrets.token_hex(32) for name in names}
    fake['MINIO_ACCESS_KEY']='dianzi-r02-'+fake['MINIO_ACCESS_KEY']
    environment=dict(os.environ,PYTHONIOENCODING='utf-8')
    for name,value in fake.items():environment['DIANZI_SCAN_'+name]=value
    results=[]
    def probe(label,files,expected_exit,expected_hits=None):
        directory=Path(tempfile.mkdtemp(prefix='dianzi-ga-docs-scan-'+label+'-'))
        subprocess.run(['git','init','-q',str(directory)],check=True,capture_output=True)
        for name,value in files.items():(directory/name).write_bytes(value)
        subprocess.run(['git','add','--',*files],cwd=directory,check=True,capture_output=True)
        command=[sys.executable,str(scanner)]
        start=at()
        result=subprocess.run(command,cwd=directory,env=environment,capture_output=True,text=True,encoding='utf-8',timeout=30)
        receipt=json.loads(result.stdout) if result.stdout.strip().startswith('{') else None
        assert result.returncode==expected_exit
        if expected_hits is not None:assert receipt['matches']==expected_hits
        assert all(value not in result.stdout+result.stderr for value in fake.values())
        summary=dict(label=label,command=command,cwd=str(directory),started_at=start,ended_at=at(),exit_code=result.returncode,checked_paths=receipt['checked_paths'] if receipt else None,matches=receipt['matches'] if receipt else None,checked_secret_references=receipt['checked_secret_references'] if receipt else None,public_prefix_exclusion=receipt['public_prefix_exclusion'] if receipt else None,diagnostic_type='bounded gzip rejection' if not receipt else None)
        results.append(summary)
    full={name+'.txt':value.encode() for name,value in fake.items()}
    probe('full-nine',full,1,9)
    fragment={name+'.txt':(value.removeprefix('dianzi-r02-') if name=='MINIO_ACCESS_KEY' else value)[3:11].encode() for name,value in fake.items()}
    probe('eight-nine',fragment,1,9)
    probe('gzip',{'secret.txt.gz':gzip.compress(fake['PG_PASSWORD'].encode())},1,1)
    probe('public-prefix',{'public-path.txt':b'dianzi-r02-public-documented-prefix-only'},0,0)
    probe('oversize-gzip',{'bounded.txt.gz':gzip.compress(b'A'*(64*1024*1024+1))},1)
    probe('corrupt-gzip',{'invalid.txt.gz':b'not a gzip stream'},1)
    (RUN/'docs_scanner_synthetic_probes.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(dict(scanner_sha256=hashlib.sha256(scanner.read_bytes()).hexdigest(),checks=len(results),all_expected=True,real_provider_credentials_read=False),ensure_ascii=False))

if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    check_docs()
    scanner_probes()
