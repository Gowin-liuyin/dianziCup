"""核对pointer修复冻结、作者材料和原审查raw；不修改任何被审文件。"""
from __future__ import annotations
import hashlib
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path
ROOT=Path('D:/wt/r17-graph-recheck1')
RUN=ROOT/'reports/runs/recovery_r17_graph_review1_recheck_20261016'
SOURCE='d6537678efe98c38e08b70960a7e5edaac02b108'
REVIEW='65497b14cb5c24c6d780f675a70af3ee4019d8db'
BASE='370f8736f212adfc6ba05b0221bafa5061962a5c'
def sha(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
def git(*args: str) -> bytes:
    return subprocess.check_output(['git',*args],cwd=ROOT)
def check(*args: str) -> dict[str,object]:
    result=subprocess.run(list(args),cwd=ROOT,capture_output=True,encoding='utf-8')
    return {'argv':list(args),'exit_code':result.returncode,'stdout':result.stdout,'stderr':result.stderr}
author_path='reports/runs/recovery_r17_graph_ui_fix1_20261016/artifact_manifest.json'
raw=(ROOT/author_path).read_bytes();author=json.loads(raw);author_blob=git('show',f'{REVIEW}:{author_path}')
receipt={'recorded_at':datetime.now(timezone(timedelta(hours=8))).isoformat(),'review_sha':'none','reviewed_sha':REVIEW,'reviewed_tree':git('rev-parse',f'{REVIEW}^{{tree}}').decode().strip(),'source_sha':SOURCE,'source_tree':git('rev-parse',f'{SOURCE}^{{tree}}').decode().strip(),'author_manifest':{'path':author_path,'checkout_raw_sha256':sha(raw),'lf_sha256':sha(raw.replace(b'\r\n',b'\n')),'blob_sha256':sha(author_blob),'expected_author_body_sha256':'5dbd71022d2197ec7f5aedc0229fec870f790a3773bd030c4bce7867b92055d6'},'source':[],'owned':[]}
for entry in author['source']:
    name=entry['path'];raw=(ROOT/name).read_bytes();blob=git('show',f'{SOURCE}:{name}')
    receipt['source'].append({'path':name,'raw_sha256':sha(raw),'lf_sha256':sha(raw.replace(b'\r\n',b'\n')),'git_blob':git('rev-parse',f'{SOURCE}:{name}').decode().strip(),'blob_sha256':sha(blob),'matches_author_lf':sha(raw.replace(b'\r\n',b'\n'))==entry['lf_sha256'],'matches_freeze':raw.replace(b'\r\n',b'\n')==blob,'matches_material_source':blob==git('show',f'{REVIEW}:{name}')})
for entry in author['evidence']:
    name=entry['path'];raw=(ROOT/name).read_bytes();blob=git('show',f'{REVIEW}:{name}');expected=entry.get('lf_sha256')
    receipt['owned'].append({'path':name,'raw_sha256':sha(raw),'lf_sha256':sha(raw.replace(b'\r\n',b'\n')) if expected else None,'git_blob_sha256':sha(blob),'author_raw_sha256':entry['raw_sha256'],'matches_author':sha(raw.replace(b'\r\n',b'\n'))==expected if expected else sha(blob)==entry['raw_sha256']})
receipt['original_probe']=[]
for name in ['browser-pointer.mjs','browser-pointer/pointer-negative.json','artifact_manifest.json','artifact_manifest.sha256']:
    old=Path('D:/wt/r17-graph-review1/reports/runs/recovery_r17_evidence_graph_review1_20261016')/name;copy=RUN/'original_probe'/name
    receipt['original_probe'].append({'path':name,'original_raw_sha256':sha(old.read_bytes()),'copied_raw_sha256':sha(copy.read_bytes()),'unchanged':old.read_bytes()==copy.read_bytes()})
receipt['code_diff_check']=check('git','diff','--check',f'{BASE}..{REVIEW}','--','frontend','docs/decisions/CR-R17_graph_edge_selection.md','reports/tasks/R17-graph-ui-fix1.md')
receipt['all_material_diff_check']=check('git','diff','--check',f'{BASE}..{REVIEW}')
receipt['callers']=check('rg','-n','GraphExplorerView|findGraphEdgeCandidates|createGraphEdgeCurve|selectEdgeAtPointer','frontend/src','frontend/e2e')
receipt['unit']=json.loads((RUN/'unit.json').read_text(encoding='utf-8'))
receipt['graph_test_count']=sum(len(item['assertionResults']) for item in receipt['unit']['testResults'] if '/features/graph/' in item['name'].replace('\\','/'))
receipt['unit']={key:receipt['unit'].get(key) for key in ['numTotalTests','numPassedTests','numFailedTests','numPendingTests','success']}
receipt['authority']=[]
for name in ['AGENTS.md','docs/plan/00_execution_map.md','docs/plan/12_recovery_task_cards_20261014.md','docs/plan/03_data_contracts.md','docs/plan/05_api_and_tool_contracts.md','docs/plan/06_testing_and_evaluation.md','docs/tasks/T40_frontend_shell.md','docs/tasks/T41_sources_events_ui.md','docs/tasks/T43_qa_agents_recommendations_ui.md','contracts/schemas/public_api_v2.json','progress/task_state.json','progress/context_handoff.md']:
    receipt['authority'].append({'path':name,'raw_sha256':sha((ROOT/name).read_bytes()),'blob_sha256':sha(git('show',f'{REVIEW}:{name}'))})
tests=json.loads((RUN/'author-e2e.json').read_text(encoding='utf-8'));receipt['author_e2e_stats']=tests['stats'];receipt['pointer_attachments']=[]
def collect(node: dict[str, object]) -> None:
    for suite in node.get('suites',[]): collect(suite)
    for spec in node.get('specs',[]):
        for test in spec.get('tests',[]):
            for result in test.get('results',[]):
                for entry in result.get('attachments',[]):
                    if entry['name'] in ['six-kinds-mouse-clicks','thirty-edges-pointer','dense-real-pointer','actual-pointer-coordinates','synthetic-bounded-timing']:
                        import base64
                        content=json.loads(base64.b64decode(entry['body'])) if 'body' in entry else json.loads(Path(entry['path']).read_text(encoding='utf-8'))
                        receipt['pointer_attachments'].append({'spec':spec['title'],'name':entry['name'],'value':content})
collect(tests)
(RUN/'audit.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
assert receipt['author_manifest']['lf_sha256']==receipt['author_manifest']['expected_author_body_sha256']
assert all(entry['matches_author_lf'] and entry['matches_freeze'] and entry['matches_material_source'] for entry in receipt['source'])
assert all(entry['matches_author'] for entry in receipt['owned'])
assert all(entry['unchanged'] for entry in receipt['original_probe'])
assert receipt['code_diff_check']['exit_code']==0
print(json.dumps({'source':len(receipt['source']),'owned':len(receipt['owned']),'reviewed_tree':receipt['reviewed_tree'],'source_tree':receipt['source_tree'],'unit':receipt['unit'],'e2e':receipt['author_e2e_stats'],'all_material_diff_exit':receipt['all_material_diff_check']['exit_code']},ensure_ascii=False))
