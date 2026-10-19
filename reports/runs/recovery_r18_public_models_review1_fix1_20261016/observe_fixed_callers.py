"""Record actual fixed model imports, rejected risks, valid partial scopes and cleanup."""
from __future__ import annotations
import copy
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('D:/wt/r18pm-r1f1')
RUN=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'sdk/python'))
sys.path.insert(0,str(RUN/'inputs'))
import ai_intel_client.models as model_module
from ai_intel_client.cli import legacy_stack_exit_code
from ai_intel_client.models import StackCheckResult
from pydantic import TypeAdapter, ValidationError
from test_independent_models import ASSESSMENT, SAMPLES, STACK, parse_public

start=datetime.now(ZoneInfo('Asia/Shanghai'))
assert Path(model_module.__file__).resolve()==ROOT/'sdk/python/ai_intel_client/models.py'
rejected=[]
for confirmation in ('unknown','conflict'):
    for wrapped in (False,True):
        envelope=copy.deepcopy(STACK)
        envelope['result']['results'][0]['status']='excluded_with_evidence'
        envelope['risk_summary'].update(confirmation=confirmation,findings=[])
        payload={**copy.deepcopy(SAMPLES['TaskResultEnvelope']),'result':envelope} if wrapped else envelope
        name='TaskResultEnvelope' if wrapped else 'StackCheckEnvelope'
        try:
            TypeAdapter(getattr(model_module,name)).validate_json(json.dumps(payload))
        except ValidationError:
            rejected.append({'trigger':'complete_'+confirmation,'caller':name,'input':payload,'rejected':True})
        else:
            raise AssertionError('frozen prior failure was not corrected')
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
    try:
        parse_public('StackCheckEnvelope',payload)
    except ValidationError:
        rejected.append({'trigger':gap,'caller':'StackCheckEnvelope','input':payload,'rejected':True})
    else:
        raise AssertionError('frozen prior qualification failure was not corrected')
valid_complete=parse_public('StackCheckEnvelope',copy.deepcopy(STACK))
assert valid_complete.risk_summary.findings[0].severity=='medium'
assert valid_complete.risk_summary.confirmation=='none_confirmed'
legacy_exit=legacy_stack_exit_code(StackCheckResult.model_validate_json(valid_complete.result.wire_json()))
assert legacy_exit==2
partial=copy.deepcopy(STACK)
partial['result']['results'][0].update(status='insufficient_evidence',reason_code='missing_version')
partial['result']['results'].append(copy.deepcopy(ASSESSMENT))
partial['risk_summary'].update(confirmation='unknown',coverage='partial',evaluated_components=1,
                               unknown_component_indices=[0],findings=[])
valid_partial=parse_public('StackCheckEnvelope',partial)
assert valid_partial.risk_summary.evaluated_components==1 and len(valid_partial.result.results)==2
ownership_script=r"""$ownParentIds = 35444,33208,48464,37476,23680,51436,54372,52172,20260
$parents = @(Get-Process -Id $ownParentIds -ErrorAction SilentlyContinue | Select-Object Id, ProcessName)
$fixtures = @(Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*D:\wt\r18pm-r1f1\sdk\python\tests\fixtures*' -or $_.CommandLine -like '*D:\dianzi\reports\runs\recovery_r18_public_models_review1_fix1_20261016\old_sdk_native_evidence*') } | Select-Object ProcessId, Name)
$sockets = @(Get-NetTCPConnection -OwningProcess $ownParentIds -ErrorAction SilentlyContinue | Select-Object OwningProcess, State, LocalAddress, LocalPort)
@{ existing_parent_processes=$parents; owned_fixture_processes=$fixtures; own_parent_tcp_sockets=$sockets } | ConvertTo-Json -Depth 5 -Compress"""
command=['powershell.exe','-NoProfile','-Command',ownership_script]
cleanup=subprocess.run(command,cwd=ROOT,capture_output=True,check=True,timeout=60)
(RUN/'own_process_cleanup.log').write_bytes(cleanup.stdout+cleanup.stderr)
ownership=json.loads(cleanup.stdout)
result={'source':'011ea225d18b7511a19d7d6056288f799bb83f20','workdir':str(ROOT),
        'started_at':start.isoformat(),'ended_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),
        'exit_code':0,'actual_models_import':model_module.__file__,'rejected_prior_cases':rejected,
        'valid_partial_smaller_count':json.loads(valid_partial.wire_json()),'valid_medium_below_high_threshold':True,
        'legacy_cli_exit':legacy_exit,'cleanup_command':command,'ownership':ownership,
        'cleanup_action':'none_required' if not ownership['owned_fixture_processes'] else 'inspect_owned_processes',
        'other_owner_processes_terminated':0}
(RUN/'observations.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({key:value for key,value in result.items() if key not in {'rejected_prior_cases','valid_partial_smaller_count','cleanup_command'}}))
