"""Seal raw evidence only after a final scan against the private test connection values."""
import datetime as dt
import hashlib
import json
from pathlib import Path
import subprocess
from run_command import ROOT,RUN

zone=dt.timezone(dt.timedelta(hours=8))
started=dt.datetime.now(zone).isoformat()
report=ROOT/'reports/reviews/recovery/G-C-integrated-e310-validation.md'
head=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
assert head=='e310f7735bd499c4d9fbcefe8a644e2309a16a62'
assert subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).strip()==''
capture=subprocess.check_output(['wsl.exe','-d','Ubuntu-22.04','-u','root','--','cat',
    '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'],text=True,timeout=15)
configuration=json.loads(capture)
private_values=[value.encode() for key,value in configuration.items() if isinstance(value,str) and value and ('password' in key.casefold() or key in {'TEST_DATABASE_URL','TEST_REDIS_URL'})]
files=[report,*sorted(p for p in RUN.rglob('*') if p.is_file() and p.name not in {'artifact_manifest.json','artifact_manifest.sha256','seal_receipt.json'})]
findings=[]
for path in files:
    raw=path.read_bytes()
    if any(value in raw for value in private_values):
        findings.append(str(path.relative_to(ROOT)).replace('\\','/'))
assert not findings, 'private test connection value appeared in owned evidence'
receipt=dict(started_at=started,ended_at=dt.datetime.now(zone).isoformat(),code_sha=head,
    tracked_diff_empty=True,private_connection_value_scan=dict(files=len(files),matches=0,values_never_logged=True),
    report_path=str(report.relative_to(ROOT)).replace('\\','/'),report_raw_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),
    git_commit_push_attempts=0,accepted_changes=0,live_calls=0,scope='limited integrated validation; no stage acceptance')
(RUN/'seal_receipt.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
files.append(RUN/'seal_receipt.json')
entries=[]
for path in sorted(files):
    raw=path.read_bytes()
    item=dict(path=str(path.relative_to(ROOT)).replace('\\','/'),bytes=len(raw),raw_sha256=hashlib.sha256(raw).hexdigest())
    if path.suffix in {'.py','.txt','.log','.json','.xml','.md','.ps1'}:
        item['lf_sha256']=hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest()
    entries.append(item)
manifest=dict(schema_version=1,sealed_at=dt.datetime.now(zone).isoformat(),code_sha=head,
    code_tree=subprocess.check_output(['git','show','-s','--format=%T','HEAD'],cwd=ROOT,text=True).strip(),
    report_raw_sha256=receipt['report_raw_sha256'],artifacts=entries,
    exclusions=['Git ignored backend/.venv and frontend/node_modules','external CBM cache'],
    evidence_note='Raw hashes are physical bytes; LF hashes only representation comparison. No own artifact Git blob exists before any authorized material commit.',
    status='awaiting_review',stage_acceptance=False)
raw=json.dumps(manifest,indent=2).encode('utf-8')
(RUN/'artifact_manifest.json').write_bytes(raw)
hash_value=hashlib.sha256(raw).hexdigest()
(RUN/'artifact_manifest.sha256').write_text(hash_value+'\n',encoding='utf-8')
print(json.dumps(dict(artifacts=len(entries),report_raw_sha256=receipt['report_raw_sha256'],manifest_raw_sha256=hash_value,secret_matches=0,tracked_diff_empty=True)))
