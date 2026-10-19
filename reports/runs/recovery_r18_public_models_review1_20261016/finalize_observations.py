"""Preserve observable findings, fixed binding contract, and own process cleanup."""
from __future__ import annotations
import copy
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('D:/wt/r18pm-r1')
RUN=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'sdk/python'))
from test_independent_models import STACK, SAMPLES, parse_public

ZONE=ZoneInfo('Asia/Shanghai')
started_at=datetime.now(ZONE)
binding_commit='d8847a8026e2c38272ca9e1a67419d5d5941d763'
binding_path='docs/decisions/CR-R18_public_read_identity_bindings.md'
binding=subprocess.run(['git','show',binding_commit+':'+binding_path],cwd=ROOT,capture_output=True,check=True).stdout
(RUN/'CR-R18_public_read_identity_bindings.committed.md').write_bytes(binding)
initial=(RUN/'CR-R18_public_read_identity_bindings.root_snapshot.md').read_bytes()
observations=[]
for confirmation in ('unknown','conflict'):
    payload=copy.deepcopy(STACK)
    payload['result']['results'][0]['status']='excluded_with_evidence'
    payload['risk_summary'].update(confirmation=confirmation,findings=[])
    parsed=parse_public('StackCheckEnvelope',payload)
    observations.append({'trigger':'complete_'+confirmation,'input':payload,'observed_acceptance':True,
                         'serialized_output':json.loads(parsed.wire_json())})
for gap in ('supported_without_grade','excluded_without_citations','excluded_without_assessment',
            'partial_unknown_none_confirmed','partial_missing_grade_none_confirmed'):
    payload=copy.deepcopy(STACK)
    payload['risk_summary']['findings']=[]
    assessment=payload['result']['results'][0]
    if gap=='excluded_without_citations':
        assessment.update(status='excluded_with_evidence',citations=[])
    elif gap=='excluded_without_assessment':
        assessment.update(status='excluded_with_evidence',assessment_id=None)
    elif gap.startswith('partial'):
        payload['risk_summary'].update(coverage='partial',unknown_component_indices=[0])
        if gap=='partial_unknown_none_confirmed':
            assessment.update(status='insufficient_evidence',reason_code='missing_version')
    parsed=parse_public('StackCheckEnvelope',payload)
    observations.append({'trigger':gap,'input':payload,'observed_acceptance':True,
                         'serialized_output':json.loads(parsed.wire_json())})
pids=[]
for name in ('new_models','old_sdk','old_schema','independent','complete_support','typing','style','format'):
    receipt=json.loads((RUN/(name+'.json')).read_bytes())
    pids.append({'check':name,'pid':receipt['pid']})
ownership_script=r"""$ownParentIds = 44604,37104,44356,13620,29228,28312,49728,26308
$parents = @(Get-Process -Id $ownParentIds -ErrorAction SilentlyContinue | Select-Object Id, ProcessName)
$fixtures = @(Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*D:\wt\r18pm-r1\sdk\python\tests\fixtures*' -or $_.CommandLine -like '*D:\dianzi\reports\runs\recovery_r18_public_models_review1_20261016\old_sdk_native_evidence*') } | Select-Object ProcessId, Name)
@{ existing_parent_processes=$parents; owned_fixture_processes=$fixtures } | ConvertTo-Json -Depth 5 -Compress"""
cleanup_command=['powershell.exe','-NoProfile','-Command',ownership_script]
cleanup_result=subprocess.run(cleanup_command,cwd=ROOT,capture_output=True,check=True,timeout=60)
(RUN/'own_process_cleanup.log').write_bytes(cleanup_result.stdout+cleanup_result.stderr)
cleanup=json.loads(cleanup_result.stdout)
leftovers=cleanup['owned_fixture_processes']
result={'source':'be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958','started_at':started_at.isoformat(),
        'ended_at':datetime.now(ZONE).isoformat(),'exit_code':0,'observations':observations,
        'binding_commit':binding_commit,'binding_raw_sha256':hashlib.sha256(binding).hexdigest(),
        'initial_snapshot_exactly_equal_to_commit':initial==binding,
        'initial_snapshot_content_equal_after_line_endings':initial.replace(b'\r\n',b'\n')==binding.replace(b'\r\n',b'\n'),
        'test_parent_processes':pids,'cleanup_command':cleanup_command,
        'currently_existing_parent_processes':cleanup['existing_parent_processes'],
        'own_fixture_processes_remaining':leftovers,
        'cleanup_action':'none_required' if not leftovers else 'inspect_owned_processes',
        'checked_process_scope':'exact review worktree fixture/native-evidence paths; no other owner process terminated'}
(RUN/'observations.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='observations'}))
