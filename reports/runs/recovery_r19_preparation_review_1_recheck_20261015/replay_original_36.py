"""Replay original reviewer CLI argv and expectations against fixed code.

Only executable/cwd and new output paths change. Original explicit synthetic
inputs, old-invalid export, expected exit codes and failure requirements stay.
"""
import hashlib
import json
import subprocess
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT=Path('D:/wt/r19-preparation-review-fix1')
RUN=ROOT/'reports/runs/recovery_r19_preparation_review_1_recheck_20261015'
OLD=Path('D:/wt/r19-preparation-review-1/reports/runs/recovery_r19_preparation_review_1_20261015')
TEST=Path(tempfile.mkdtemp(prefix='r19-fix1-review-original36-synthetic-'))
PYTHON='D:/dianzi/backend/.venv/Scripts/python.exe'
RECORDS=[]
output_map={}
old_first=json.loads((OLD/'boundary_probes.json').read_text(encoding='utf-8'))
old_second=json.loads((OLD/'followup_probes.json').read_text(encoding='utf-8'))
records=old_first['records']+[record for record in old_second['records'] if 'argv' in record]
for original in records:
    name=original['name']
    arguments=original['argv'][2:]
    arguments=list(arguments)
    if '--output' in arguments and name!='output_overwrite':
        index=arguments.index('--output')+1
        old_path=arguments[index]
        if name=='labels_to_review_worktree':
            new_path=ROOT/'reports'/'synthetic_labels_must_not_exist.json'
        elif name=='labels_to_other_registered_worktree':
            new_path=Path('D:/wt/r19-preparation-path-probe-1')/(TEST.name+'.json')
        elif name=='labels_to_product_mount':
            new_path=Path(old_path)
        else:
            new_path=TEST/Path(old_path).name
        output_map[old_path]=str(new_path)
    for index,arg in enumerate(arguments):
        if arg in output_map and name!='orphan_export_revalidate':
            arguments[index]=output_map[arg]
    if name in ('clean_scan','synthetic_holdout_text_leak'):
        public=TEST/'selected_public'
        public.mkdir(exist_ok=True)
        (public/'clean.txt').write_text('No synthetic holdout content here',encoding='utf-8')
        if name=='synthetic_holdout_text_leak':
            (public/'leaked.txt').write_text('SYN-HOLDOUT-FAMILY',encoding='utf-8')
        arguments[arguments.index('--scan-root')+1]=str(public)
    argv=[PYTHON,str(ROOT/'scripts/annotation/prepare.py'),*arguments]
    start=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    result=subprocess.run(argv,cwd=ROOT,capture_output=True,text=True,encoding='utf-8',check=False)
    end=datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    record={'name':name,'argv':argv,'cwd':str(ROOT),'started_at':start,'ended_at':end,
            'expected_exit':original['expected_exit'],'exit_code':result.returncode,
            'stdout':result.stdout,'stderr':result.stderr,
            'expectation_met':result.returncode==original['expected_exit']}
    if '--output' in arguments:
        output=Path(arguments[arguments.index('--output')+1])
        record['output_exists']=output.exists()
    if name.startswith('alias_to_family_cross_split'):
        record['expected_error_code']='FAMILY_SPLIT_LEAK'
    if name in ('labels_to_other_registered_worktree','labels_to_review_worktree','labels_to_product_mount','other_registered_worktree_annotation_input'):
        record['expected_error_code']='HUMAN_OR_HOLDOUT_PATH_MUST_BE_EXTERNAL'
    if name in ('orphan_stale_adjudication_one_label','orphan_stale_adjudication_export','orphan_export_revalidate'):
        record['expected_error_code']='REVIEW_REQUIRES_TWO_CURRENT_LABELS'
    if name=='orphan_duplicate_review_records':
        record['expected_error_code']='DUPLICATE_REVIEW_RECORD'
    if 'expected_error_code' in record:
        record['error_code_matched']=record['expected_error_code'] in result.stderr
    RECORDS.append(record)
output={'started_at':RECORDS[0]['started_at'],'ended_at':RECORDS[-1]['ended_at'],
        'synthetic_fixture_root':str(TEST),'original_inputs_unchanged':True,
        'original_json_receipt_hashes':{name:hashlib.sha256((OLD/name).read_bytes()).hexdigest()
            for name in ('boundary_probes.json','followup_probes.json')},
        'records':RECORDS,'mismatches':[r['name'] for r in RECORDS if not r['expectation_met'] or r.get('error_code_matched') is False]}
(RUN/'original_36_replay.json').write_text(json.dumps(output,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({'executed':len(RECORDS),'mismatches':output['mismatches'],'fixture_root':str(TEST)},ensure_ascii=False))
raise SystemExit(1 if output['mismatches'] else 0)
