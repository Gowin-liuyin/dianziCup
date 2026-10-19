"""Freeze review evidence hashes and check no private test credentials were written."""

import hashlib
import json
import subprocess
from datetime import datetime,timezone,timedelta
from pathlib import Path

from run_review import credentials

ROOT=Path(__file__).resolve().parents[3]
RUN=Path(__file__).resolve().parent
REPORT=ROOT/'reports/reviews/recovery/G-C-R06-source-polling-review-1.md'
FROZEN='93c458a0f97b65198d1fb690d42634b77342bb3c'
BASE='52433474f66a900c56ee6d5478337b0ec83d6eda'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    records=json.loads((RUN/'commands.json').read_text())
    by_label={row['label']:row for row in records}
    for path in RUN.glob('*.command.json'):
        row=json.loads(path.read_text())
        by_label[row['label']]=row
    commands=sorted(by_label.values(),key=lambda row:row['started_at'])
    (RUN/'commands.json').write_text(json.dumps(commands,ensure_ascii=False,indent=2),encoding='utf-8')
    code=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()
    assert code==FROZEN
    changes=subprocess.check_output(['git','diff','--name-only',BASE,FROZEN],cwd=ROOT,text=True).splitlines()
    assert len(changes)==8
    assert subprocess.check_output(['git','diff','--name-only'],cwd=ROOT,text=True).strip()==''
    snapshot={'baseline':BASE,'code_sha':code,'tracked_worktree_changes':[],'changed_files':[{'path':path,'sha256':digest(ROOT/path)} for path in changes]}
    (RUN/'source_snapshot.json').write_text(json.dumps(snapshot,indent=2),encoding='utf-8')
    values,url=credentials()
    secrets=[values['postgres_password'],values['redis_password'],values['TEST_DATABASE_URL'],values['TEST_REDIS_URL'],url]
    scanned=0
    leaks=[]
    for path in [REPORT,*[path for path in RUN.rglob('*') if path.is_file()]]:
        content=path.read_bytes()
        scanned+=1
        if any(value.encode() in content for value in secrets if value):
            leaks.append(str(path.relative_to(ROOT)))
    assert not leaks, 'private review credential found in evidence file'
    (RUN/'credential_scan.json').write_text(json.dumps({'scanned_file_count':scanned,'private_credentials_found':0,'scope':'all evidence files including preserved derived caches; credentials never printed'},indent=2),encoding='utf-8')
    excluded=['mypy_cache','mypy_cache_own']
    rows=[]
    for path in sorted(RUN.rglob('*')):
        if not path.is_file() or path.name=='manifest.json' or any(part in excluded for part in path.relative_to(RUN).parts):
            continue
        rows.append({'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':path.stat().st_size,'sha256':digest(path)})
    manifest={'created_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),'baseline':BASE,'reviewed_sha':FROZEN,'verdict':'Ship: automatic polling assembly slice only','report':{'path':str(REPORT.relative_to(ROOT)).replace('\\','/'),'sha256':digest(REPORT)},'excluded_generated_cache_directories':excluded,'cache_policy':'preserved after automatic cleanup rejection; not primary evidence','files':rows}
    (RUN/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'report_sha256':digest(REPORT),'manifest_sha256':digest(RUN/'manifest.json'),'evidence_file_count':len(rows),'credential_scan_files':scanned,'private_credentials_found':0}))


if __name__=='__main__':
    try:
        main()
    except Exception as error:
        print(type(error).__name__)
        raise SystemExit(1) from None
