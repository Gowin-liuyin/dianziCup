"""Check exact scoped registration without changing candidate state."""
import copy
import hashlib
import importlib.util
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('D:/dianzi-ga-checkpoint-review-1-registration')
BEFORE=Path('D:/dianzi-ga-checkpoint-review-1-final-docs')
RUN=Path('D:/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
def at():return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
def strict(pairs):
    result={}
    for key,value in pairs:
        if key in result:raise ValueError('duplicate JSON key '+key)
        result[key]=value
    return result
def read(path):return json.loads(path.read_text(encoding='utf8'),object_pairs_hook=strict)
started=at()
before=read(BEFORE/'progress/task_state.json')
after=read(ROOT/'progress/task_state.json')
manifest=read(ROOT/'contracts/task_manifest.json')
for key,entry in before['tasks'].items():
    assert {name:value for name,value in entry.items() if name!='slice_acceptance'}=={name:value for name,value in after['tasks'][key].items() if name!='slice_acceptance'}
changed=[]
for key,entry in before['tasks'].items():
    for slice_id,slice_before in entry.get('slice_acceptance',{}).items():
        slice_after=after['tasks'][key]['slice_acceptance'][slice_id]
        if slice_before!=slice_after:
            changed.append(slice_id)
            assert manifest['recovery']['capability_slices'][slice_id]['original_task']==key
            package=slice_id.split(':')[0]
            assert package in {'R01','R02','R03'}
            assert slice_after['status']=='accepted'
            assert slice_after['review_ref']=='reports/reviews/recovery/G-A-checkpoint-review-1.md'
            assert {name:value for name,value in slice_before.items() if name not in {'status','review_ref','evidence','history'}}=={name:value for name,value in slice_after.items() if name not in {'status','review_ref','evidence','history'}}
            old_history=slice_before.get('history',[])
            assert slice_after['history'][:len(old_history)]==old_history
            assert slice_after['history'][-1]['prior_record']=={name:value for name,value in slice_before.items() if name!='history'}
expected=[item for package in ('R01','R02','R03') for item in manifest['recovery']['work_packages'][package]['output_slices']]
assert sorted(changed)==sorted(expected) and len(changed)==13
for package in ('R01','R02','R03'):
    assert before['recovery_tasks'][package]['verification']==after['recovery_tasks'][package]['verification']
    assert after['recovery_tasks'][package]['status']=='accepted'
    assert after['recovery_tasks'][package]['verification']['live']=='not_run'
    assert after['recovery_tasks'][package]['verification']['manual']=='not_run'
for package in before['recovery_tasks']:
    if package not in {'R01','R02','R03'}:assert before['recovery_tasks'][package]==after['recovery_tasks'][package]
assert after['recovery_stage']=='G-B'
receipt=read(ROOT/'reports/runs/recovery_r04_source_jobs_20261015/ga_acceptance_registration.json')
report_blob=subprocess.check_output(['git','show','fa5deb0:reports/reviews/recovery/G-A-checkpoint-review-1.md'],cwd=ROOT)
report_checkout=(ROOT/'reports/reviews/recovery/G-A-checkpoint-review-1.md').read_bytes()
assert hashlib.sha256(report_checkout).hexdigest()==receipt['review_report_sha256']
assert report_blob==report_checkout.replace(b'\r\n',b'\n')
spec=importlib.util.spec_from_file_location('fixed_verify_plan',ROOT/'scripts/verify_plan.py')
module=importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
virtual=copy.deepcopy(after)
for key in virtual['tasks']:
    virtual['tasks'][key]['slice_acceptance']=copy.deepcopy(before['tasks'][key].get('slice_acceptance',{}))
initial=module.check_task_state(virtual,manifest,ROOT)
assert len(initial)==19
result=dict(started_at=started,ended_at=at(),reviewed_sha='fa5deb0d0b519869ca92d34d9ffe7d8e39b06fb4',tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),strict_json='passed',original_T_whole_records_unchanged_except_slice_acceptance=True,changed_slices=changed,exact_manifest_output_slices=True,slice_history_preserved=True,package_verification_unchanged=True,other_recovery_tasks_unchanged=True,next_stage='G-B',fixed_report_windows_checkout_matches_registration_hash=True,report_canonical_git_blob_sha256=hashlib.sha256(report_blob).hexdigest(),report_crlf_normalization_preserves_content=True,initial_package_only_registration_errors_reproduced=len(initial),initial_error_codes=[entry.split(':',1)[0] for entry in initial],final_gate='pure_registration_passed')
(RUN/'registration_fa5_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps(result,ensure_ascii=False))
