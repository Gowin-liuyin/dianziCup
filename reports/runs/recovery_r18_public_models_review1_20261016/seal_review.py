"""Seal only this review's owned evidence in its isolated source worktree."""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN=Path(__file__).resolve().parent
WORKTREE=Path('D:/wt/r18pm-r1')
ROOT=Path('D:/dianzi')
REPORT=ROOT/'reports/reviews/recovery/G-E-R18-public-models-review-1.md'
SOURCE='be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958'
ZONE=ZoneInfo('Asia/Shanghai')
start=datetime.now(ZONE)
OWN_RUN=RUN.relative_to(ROOT)
OWN_REPORT=REPORT.relative_to(ROOT)

def git(*arguments: str) -> bytes:
    result=subprocess.run(['git',*arguments],cwd=WORKTREE,capture_output=True,check=False)
    with (RUN/'seal_commands.log').open('ab') as log:
        log.write((json.dumps({'command':['git',*arguments],'cwd':str(WORKTREE),
                              'executed_at':datetime.now(ZONE).isoformat(),'exit_code':result.returncode})+'\n').encode())
        log.write(result.stdout+result.stderr)
    if result.returncode:
        raise RuntimeError(f'git command failed with exit {result.returncode}')
    return result.stdout

assert git('rev-parse','HEAD').decode().strip()==SOURCE
assert not git('status','--porcelain','--untracked-files=no').strip()
git('switch','-c','codex/r18-public-models-review1-material')
paths=[]
for path in RUN.rglob('*'):
    if not path.is_file():
        continue
    relative=path.relative_to(RUN)
    if any(part.endswith('_tmp') or part in {'mypy_cache','__pycache__'} for part in relative.parts):
        continue
    if path.name in {'own_payload_manifest.json','seal_receipt.json','seal_commands.log'}:
        continue
    paths.append(path)
paths.append(REPORT)
payloads=[]
for path in sorted(paths):
    relative=path.relative_to(ROOT)
    payload=path.read_bytes()
    destination=WORKTREE/relative
    if destination.exists():
        raise RuntimeError('New review destination unexpectedly exists')
    destination.parent.mkdir(parents=True,exist_ok=True)
    destination.write_bytes(payload)
    expected_blob=subprocess.run(['git','hash-object','--no-filters','--',str(destination)],
                                 cwd=WORKTREE,capture_output=True,check=True).stdout.decode().strip()
    payloads.append({'path':relative.as_posix(),'raw_sha256':hashlib.sha256(payload).hexdigest(),
                     'size_bytes':len(payload),'git_blob':expected_blob})
manifest={'recorded_at':datetime.now(ZONE).isoformat(),'source_sha':SOURCE,
          'review_status':'needs_changes','review_task':'/root/r18_public_models_first_independent_review',
          'payload_count':len(payloads),'payloads':payloads,
          'excluded_generated_cache_parts':['*_tmp','mypy_cache','__pycache__'],
          'manifest_excludes_itself':True,'report_path':OWN_REPORT.as_posix()}
raw_manifest=(json.dumps(manifest,indent=2)+'\n').encode('utf-8')
(RUN/'own_payload_manifest.json').write_bytes(raw_manifest)
(WORKTREE/OWN_RUN/'own_payload_manifest.json').write_bytes(raw_manifest)
git('add','--',OWN_RUN.as_posix(),OWN_REPORT.as_posix())
changed=git('diff','--cached','--name-only').decode().splitlines()
assert all(path==OWN_REPORT.as_posix() or path.startswith(OWN_RUN.as_posix()+'/') for path in changed)
git('diff','--cached','--check')
git('commit','-m','R18 independent public typed model review needs changes')
commit=git('rev-parse','HEAD').decode().strip()
for item in payloads:
    payload=git('show',commit+':'+item['path'])
    assert hashlib.sha256(payload).hexdigest()==item['raw_sha256']
    assert git('rev-parse',commit+':'+item['path']).decode().strip()==item['git_blob']
assert git('show',commit+':'+OWN_RUN.as_posix()+'/own_payload_manifest.json')==raw_manifest
receipt={'started_at':start.isoformat(),'ended_at':datetime.now(ZONE).isoformat(),'exit_code':0,
         'workdir':str(WORKTREE),'source_sha':SOURCE,'review_material_commit':commit,
         'payload_count':len(payloads),'raw_manifest_sha256':hashlib.sha256(raw_manifest).hexdigest(),
         'report_raw_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),
         'only_own_paths_staged':True,'all_payload_git_raw_sha256_matches':True,'pushed':False,
         'review_status':'needs_changes','log':'seal_commands.log'}
(RUN/'seal_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt))
