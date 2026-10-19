"""Guard the reviewed sources and freeze only owned review evidence."""
import json,hashlib,subprocess
from review_runner import ROOT,RUN,save,now

initial=json.loads((RUN/'source_audit.json').read_text())
expected={}
oldrun=ROOT/'reports/runs/recovery_r12_conversation_context_20261016'
for group in initial['old_author']:
    if group['manifest']=='material_manifest.json': continue
    original_entries={e['path']:e for e in json.loads((oldrun/group['manifest']).read_text())}
    for row in group['checks']:
        expected[row['path']]=(row['checkout_raw_sha256'],original_entries[row['path']]['clean_filter_blob'])
for row in initial['fix_source_checks']:
    expected[row['path']]=(row['checkout_raw_sha256'],row['expected_blob'])
guard=[]
for relative,(raw,clean) in sorted(expected.items()):
    path=ROOT/relative
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    blob=subprocess.check_output(['git','hash-object','--path='+relative,str(path)],cwd=ROOT).decode().strip()
    row=dict(path=relative,raw_sha256=digest,raw_unchanged=digest==raw,clean_blob=blob,clean_blob_matches=blob==clean)
    assert row['raw_unchanged'] and row['clean_blob_matches']
    guard.append(row)
save('final_source_guard.json',dict(checked_at=now(),protected_count=len(guard),code_commit='1e210090d74d1444101330f0c8b8637ad1dd50a3',files=guard))
report=ROOT/'reports/reviews/recovery/G-D-R12-conversation-context-review-1-recheck.md'
save('freeze_receipt.json',dict(frozen_at=now(),source_commit='1e210090d74d1444101330f0c8b8637ad1dd50a3',material_commit='eb030458009812ec037928e4bc2f1a4cdbe64c46',report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),verdict='limited_ship',business_files_changed=0,business_test_passed_executions=268,production_migration='not_run',public_producer='not_run',pg_slot='released'))
entries=[]
for path in sorted([report,*RUN.rglob('*')]):
    if not path.is_file() or '__pycache__' in path.parts or path.name in {'raw_manifest.json','raw_manifest.sha256'}: continue
    body=path.read_bytes()
    entries.append(dict(path=str(path.relative_to(ROOT)).replace('\\','/'),bytes=len(body),sha256=hashlib.sha256(body).hexdigest()))
save('raw_manifest.json',entries)
manifest_sha=hashlib.sha256((RUN/'raw_manifest.json').read_bytes()).hexdigest()
(RUN/'raw_manifest.sha256').write_text(manifest_sha+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(protected_count=len(guard),review_evidence_files=len(entries),report_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),manifest_sha256=manifest_sha)))
