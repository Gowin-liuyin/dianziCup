"""Bind strict contracts, evidence and independent check counts to the frozen tree."""
import hashlib
import json
import subprocess
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT=Path('D:/dianzi-ga-checkpoint-review-1')
LIVE=Path('D:/dianzi')
RUN=LIVE/'reports/runs/recovery_ga_checkpoint_review_1_20261015'

def strict(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key: '+key)
        result[key]=value
    return result

def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'),object_pairs_hook=strict)

def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

contract=read(ROOT/'contracts/task_manifest.json')
requirements=read(ROOT/'contracts/requirements.json')
state=read(ROOT/'progress/task_state.json')
current_state=read(LIVE/'progress/task_state.json')
summaries={}
for path in RUN.glob('*.xml'):
    cases=ET.parse(path).findall('.//testcase')
    summaries[path.name]=dict(tests=len(cases),failed=sum(c.find('failure') is not None for c in cases),errors=sum(c.find('error') is not None for c in cases),skipped=sum(c.find('skipped') is not None for c in cases))
coverage={}
for path in RUN.glob('*coverage.json'):
    coverage[path.name]=read(path)['totals']
paths=['AGENTS.md','docs/plan/00_execution_map.md','docs/plan/11_full_delivery_recovery_20261014.md','docs/plan/12_recovery_task_cards_20261014.md','contracts/task_manifest.json','contracts/requirements.json','progress/task_state.json','progress/context_handoff.md','prompts/12_full_delivery_parallel_push.txt','docs/references/competition_brief.pdf']
bound={name:dict(frozen_sha256=digest(ROOT/name),current_sha256=digest(LIVE/name)) for name in paths if (ROOT/name).is_file() and (LIVE/name).is_file()}
result=dict(recorded_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),tree=subprocess.check_output(['git','rev-parse','HEAD^{tree}'],cwd=ROOT,text=True).strip(),branch=subprocess.check_output(['git','branch','--show-current'],cwd=ROOT,text=True).strip(),status=subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True),strict_json='passed',original_task_count=len(contract['tasks']),requirement_count=len(requirements['requirements']),requirements_keys=list(requirements),recovery_keys=list(contract['recovery']),r00_r03_frozen_states={key:state['recovery_tasks'][key] for key in ['R00','R01','R02','R03']},r00_r03_current_statuses={key:{field:current_state['recovery_tasks'][key].get(field) for field in ['status','implementation','verification']} for key in ['R00','R01','R02','R03']},bound_files=bound,stage_document_sha256=digest(RUN/'G-A_document_snapshot.md'),tests=summaries,coverage=coverage)
(RUN/'snapshot_and_counts.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({key:result[key] for key in ['sha','tree','branch','strict_json','original_task_count','requirement_count','tests','coverage']},ensure_ascii=False,indent=2))
