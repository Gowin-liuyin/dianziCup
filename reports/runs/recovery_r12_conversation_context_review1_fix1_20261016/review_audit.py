"""Verify original inputs, authorized fix files and final-only artifact limits independently."""
import hashlib,json,subprocess
from pathlib import Path
from review_runner import ROOT,RUN,save,now

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def blob(path,relative):
    return subprocess.check_output(['git','hash-object','--path='+relative,str(path)],cwd=ROOT).decode().strip()

def audit():
    old=Path('D:/wt/r12-conversation-context')
    prior=Path('D:/wt/r12-conversation-context-review1')
    fix=Path('D:/wt/r12-conversation-context-fix1')
    oldrun='reports/runs/recovery_r12_conversation_context_20261016'
    fixrun='reports/runs/recovery_r12_conversation_context_fix1_20261016'
    priorrun='reports/runs/recovery_r12_conversation_context_review1_20261016'
    results=[]
    authorized={e['path'] for e in json.loads((fix/fixrun/'fix1_source_manifest.json').read_text())}
    for name in ('material_manifest.json','caller_source_manifest.json','implementation_source_manifest.json'):
        checks=[]
        entries=json.loads((old/oldrun/name).read_text())
        for e in entries:
            relative=oldrun+'/'+e['path'] if name=='material_manifest.json' else e['path']
            original=old/relative
            own=ROOT/relative
            original_match=sha(original)==e['sha256']
            changed=relative in authorized
            clean_matches=blob(own,relative)==e['clean_filter_blob'] if 'clean_filter_blob' in e and not changed else None
            checks.append(dict(path=relative,original_author_raw_match=original_match,authorized_change=changed,
                checkout_raw_sha256=sha(own),checkout_raw_match=sha(own)==e['sha256'],unchanged_clean_blob_match=clean_matches))
            assert original_match and (changed or clean_matches is not False)
            if name=='material_manifest.json': assert sha(own)==e['sha256']
        results.append(dict(manifest=name,count=len(entries),checks=checks))
    original_review_entries=json.loads((prior/priorrun/'raw_manifest.json').read_text())
    review_checks=[dict(path=e['path'],raw_match=sha(prior/e['path'])==e['sha256']) for e in original_review_entries]
    assert all(e['raw_match'] for e in review_checks)
    fix_material=json.loads((fix/fixrun/'material_manifest.json').read_text())
    fix_checks=[dict(path=e['path'],author_raw_match=sha(fix/e['path'])==e['sha256'],checkout_raw_match=sha(ROOT/e['path'])==e['sha256'],clean_blob_match=blob(ROOT/e['path'],e['path'])==e['clean_filter_blob']) for e in fix_material]
    assert all(e['author_raw_match'] and e['clean_blob_match'] for e in fix_checks)
    fixed_sources=[]
    for e in json.loads((fix/fixrun/'fix1_source_manifest.json').read_text()):
        own=ROOT/e['path']
        row=dict(path=e['path'],author_raw_match=sha(fix/e['path'])==e['sha256'],checkout_raw_sha256=sha(own),clean_blob=blob(own,e['path']),expected_blob=e['clean_filter_blob'])
        assert row['author_raw_match'] and row['clean_blob']==row['expected_blob']
        fixed_sources.append(row)
    report=fix/'reports/tasks/R12-conversation-context-fix1.md'
    assert sha(report)=='77131b5673d3a42613c773ce6e34c71edfab9dbe3fa8fd551561c45b474c06e2'
    assert sha(fix/fixrun/'material_manifest.json')=='f49a0789874620ebae2a1d040a6e140b8ffb1cbfd621e2376ec6a0e747e47bb2'
    assert sha(RUN/'test_review_negative.py')=='9e813862bbf5def30138a7ea67ae140a4ad5c599c6362f142f91f88d8401e9d7'
    assert blob(RUN/'test_review_negative.py',str((RUN/'test_review_negative.py').relative_to(ROOT)))=='e4214bb50966ce53ef8fb9d34899d4225a14eb05'
    save('source_audit.json',dict(checked_at=now(),old_author=results,original_review_checks=review_checks,fix_material_checks=fix_checks,fix_source_checks=fixed_sources,
        fix_report_author_raw_sha256=sha(report),fix_manifest_sha256=sha(fix/fixrun/'material_manifest.json'),fixed_source_commit='1e210090d74d1444101330f0c8b8637ad1dd50a3',material_commit='eb030458009812ec037928e4bc2f1a4cdbe64c46'))
    print(json.dumps(dict(old173_verified=True,old50_verified=True,old13_author_raw_verified=True,prior_review_files=len(review_checks),fix_material_files=len(fix_checks),fixed_source_files=len(fixed_sources))))
