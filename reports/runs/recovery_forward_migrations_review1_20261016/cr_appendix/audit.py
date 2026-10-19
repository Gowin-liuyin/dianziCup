"""只核对未提交CR文档与固定迁移/metadata，不连接数据库。"""

import ast
import hashlib
import json
import re
import subprocess
from datetime import datetime
from pathlib import Path
from zipfile import ZipFile
from zoneinfo import ZoneInfo

RUN=Path(__file__).resolve().parent
ROOT=RUN.parents[3]
CR=Path('D:/dianzi/docs/decisions/CR-recovery_0023_0026_integrity_guards.md')
SOURCE='16484eaca45791ed2ec403471561faa10ab6d036'
METADATA='1e210090d74d1444101330f0c8b8637ad1dd50a3'
started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
raw=CR.read_bytes()
(RUN/'cr.original.raw').write_bytes(raw)
with ZipFile(RUN/'cr_original_raw.zip','w') as archive:
    archive.writestr(CR.name,raw)


def norm(source):
    return re.sub(r'\s+',' ',source).strip().rstrip(';')


def source_bytes(revision,path):
    return subprocess.check_output(['git','show',f'{revision}:{path}'],cwd=ROOT)


guard_rows=json.loads((ROOT/'reports/runs/recovery_forward_migrations_0023_0026_20261016/approved_guards.json').read_text())
checked=[]
for row in guard_rows:
    parsed=ast.parse(source_bytes(SOURCE,'backend/migrations/versions/'+row['migration']))
    statements=[node.args[0].value.strip() for node in ast.walk(parsed) if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and node.func.attr=='execute']
    assert row['statement'] in statements
    assert hashlib.sha256(row['statement'].encode()).hexdigest()==row['sha256_utf8']
    checked.append({'migration':row['migration'],'statement_sha256':row['sha256_utf8'],'exact_match':True})
metadata_raw=source_bytes(METADATA,'backend/src/ai_intel/answering/conversation_models.py')
metadata_ast=ast.parse(metadata_raw)
values={node.targets[0].id:ast.literal_eval(node.value) for node in metadata_ast.body if isinstance(node,ast.Assign) and isinstance(node.targets[0],ast.Name) and isinstance(node.value,ast.Constant)}
immutable=[r['statement'] for r in guard_rows if r['migration']=='0024_conversation_context.py' and 'prevent_qa_turn_changes' in r['statement']]
assert {norm(s) for s in immutable}=={norm(values['IMMUTABILITY_FUNCTION_DDL']),norm(values['IMMUTABILITY_TRIGGER_DDL'])}
assert b'search_path' not in metadata_raw
(RUN/'r12_1e210090_metadata.git_lf.py').write_bytes(metadata_raw)
receipt={'started_at':started,'ended_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(),'exit_code':0,'cwd':str(ROOT),'argv':['D:/dianzi/backend/.venv/Scripts/python.exe',str(Path(__file__).resolve())],
         'reviewed_cr_path':str(CR),'cr_sha256_raw':hashlib.sha256(raw).hexdigest(),'cr_sha256_lf_view':hashlib.sha256(raw.replace(b'\r\n',b'\n')).hexdigest(),
         'root_main_head_at_read':subprocess.check_output(['git','rev-parse','HEAD'],cwd='D:/dianzi',text=True).strip(),'cr_status_at_read':subprocess.check_output(['git','status','--short','--','docs/decisions/CR-recovery_0023_0026_integrity_guards.md'],cwd='D:/dianzi',text=True).strip(),
         'reviewed_source':SOURCE,'metadata_reference':METADATA,'metadata_git_lf_sha256':hashlib.sha256(metadata_raw).hexdigest(),'guards':checked,
         'r12_immutability_function_trigger_match':True,'r12_metadata_search_path_guard_present':False,'tests_executed':0,'postgres_connections':0,'original_review_unchanged':True,'finding':{'document_line':10,'severity':'documentation_correction','problem':'metadata guard alignment is broader than evidence; R12 search_path binding is present only in production migration','minimal_fix':'Qualify alignment as the complete turn immutable function/trigger, and explicitly retain the production-only search_path guard difference.'}}
(RUN/'audit_receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
print(json.dumps({'exit_code':0,'cr_sha256_raw':receipt['cr_sha256_raw'],'guard_matches':len(checked),'r12_immutability_match':True,'r12_metadata_search_path_guard_present':False,'tests_executed':0,'postgres_connections':0}))
