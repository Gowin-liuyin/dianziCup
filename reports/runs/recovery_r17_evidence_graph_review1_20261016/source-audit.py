"""核对独立冻结源码、作者清单及现有调用者，保留检出CRLF与Git blob的区别。"""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path('D:/wt/r17-graph-review1')
RUN=ROOT/'reports/runs/recovery_r17_evidence_graph_review1_20261016'
BASE='8a1b04d48346d8550f0326a77f003246a0ebbab5'
SOURCE='b58aac48eee7e50264e3f51821c8057af36433d7'
REVIEW='370f8736f212adfc6ba05b0221bafa5061962a5c'
def git(*args: str) -> bytes:
    return subprocess.check_output(['git',*args],cwd=ROOT)
def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
def lf(value: bytes) -> bytes:
    return value.replace(b'\r\n',b'\n')
author_path='reports/runs/recovery_r17_evidence_graph_ui_20261016/artifact_manifest.json'
author_raw=(ROOT/author_path).read_bytes()
author_manifest=json.loads(author_raw)
result={'recorded_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'baseline':BASE,'source_freeze':SOURCE,'reviewed_sha':REVIEW,'reviewed_tree':git('rev-parse',f'{REVIEW}^{{tree}}').decode().strip(),'review_sha':'none','author_manifest':{'path':author_path,'checkout_raw_sha256':sha(author_raw),'lf_sha256':sha(lf(author_raw)),'git_blob_sha256':sha(git('show',f'{REVIEW}:{author_path}'))},'source':[],'author_artifacts':[]}
for entry in author_manifest['source']:
    name=entry['path'];raw=(ROOT/name).read_bytes();blob=git('show',f'{SOURCE}:{name}');review_blob=git('show',f'{REVIEW}:{name}')
    result['source'].append({'path':name,'bytes':len(raw),'raw_sha256':sha(raw),'lf_sha256':sha(lf(raw)),'crlf_count':raw.count(b'\r\n'),'git_blob':git('rev-parse',f'{SOURCE}:{name}').decode().strip(),'git_blob_sha256':sha(blob),'matches_source_freeze':lf(raw)==blob,'matches_reviewed_source':blob==review_blob,'author_raw_sha256':entry['raw_sha256'],'author_lf_sha256':entry['lf_sha256'],'matches_author_lf':sha(lf(raw))==entry['lf_sha256'],'matches_author_frozen_sha':sha(blob)==entry['frozen_blob_sha256']})
for section in ['artifacts','evidence']:
    for entry in author_manifest.get(section,[]):
        name=entry['path'];raw=(ROOT/name).read_bytes();blob=git('show',f'{REVIEW}:{name}')
        expected_lf=entry.get('lf_sha256')
        result['author_artifacts'].append({'path':name,'checkout_raw_sha256':sha(raw),'lf_sha256':sha(lf(raw)),'git_blob_sha256':sha(blob),'author_raw_sha256':entry['raw_sha256'],'author_lf_sha256':expected_lf,'matches_author_lf':sha(lf(raw))==expected_lf if expected_lf else sha(blob)==entry['raw_sha256'],'author_raw_matches_blob':sha(blob)==entry['raw_sha256']})
result['authority']=[]
for name in ['AGENTS.md','docs/plan/00_execution_map.md','docs/plan/12_recovery_task_cards_20261014.md','docs/tasks/T40_frontend_shell.md','docs/tasks/T41_sources_events_ui.md','docs/tasks/T43_qa_agents_recommendations_ui.md','docs/plan/03_data_contracts.md','docs/plan/05_api_and_tool_contracts.md','docs/plan/06_testing_and_evaluation.md','contracts/schemas/public_api_v2.json','progress/task_state.json','progress/context_handoff.md','reports/tasks/R17-evidence-graph-ui.md','reports/tasks/R17-evidence-graph-design.md']:
    raw=(ROOT/name).read_bytes();result['authority'].append({'path':name,'raw_sha256':sha(raw),'lf_sha256':sha(lf(raw)),'git_blob_sha256':sha(git('show',f'{REVIEW}:{name}'))})
result['source_diff']=git('diff','--name-only',f'{BASE}..{SOURCE}','--','frontend').decode().splitlines()
result['caller_rg']=subprocess.run(['rg','-n','getEventGraph|GraphExplorerView|parseGraphSnapshot','frontend/src','frontend/e2e'],cwd=ROOT,capture_output=True,text=True,encoding="utf-8").stdout
result['source_diff_check']=subprocess.run(['git','diff','--check',f'{BASE}..{SOURCE}','--','frontend'],cwd=ROOT,capture_output=True,text=True,encoding="utf-8").__dict__.get('returncode')
result['production_fixture_markers']={}
for marker in ['graphFixtureEventId','isolated-graph-fixture-user','合成 Fixture · AI 组件安全事件','R17 隔离合成证据图验收']:
    result['production_fixture_markers'][marker]=any(marker in path.read_text(encoding='utf-8') for path in (RUN/'build/assets').glob('*.js'))
unit=json.loads((RUN/'unit-regression.json').read_text(encoding='utf-8'))
result['unit_counts']={key:unit.get(key) for key in ['numTotalTestSuites','numTotalTests','numPassedTests','numFailedTests','numPendingTests','success']}
result['graph_suites']=[{'name':item['name'],'passed':sum(test['status']=='passed' for test in item['assertionResults']),'failed':sum(test['status']=='failed' for test in item['assertionResults'])} for item in unit['testResults'] if '/features/graph/' in item['name'].replace('\\','/')]
backend=git('show','16803ce:backend/src/ai_intel/knowledge/evidence_graph.py');(RUN/'backend-1_0-frozen-reference.py').write_bytes(backend)
result['backend_reference']={'sha':'16803ce','path':'backend/src/ai_intel/knowledge/evidence_graph.py','blob_sha256':sha(backend),'scope':'1.0 frozen DTO only; 1.1 backend not yet frozen or integrated'}
(RUN/'source-audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert all(item['matches_source_freeze'] and item['matches_reviewed_source'] and item['matches_author_lf'] and item['matches_author_frozen_sha'] for item in result['source'])
assert all(item['matches_author_lf'] for item in result['author_artifacts'])
assert result['source_diff_check']==0
print(json.dumps({'source_files':len(result['source']),'author_artifacts':len(result['author_artifacts']),'reviewed_tree':result['reviewed_tree'],'unit':result['unit_counts'],'graph_suites':result['graph_suites']},ensure_ascii=False))
