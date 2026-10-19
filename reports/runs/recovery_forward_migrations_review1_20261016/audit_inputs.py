"""从Git对象与压缩包校验精确字节；独立编译冻结metadata。"""

import ast
import difflib
import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import Column, MetaData, Table, Text
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import AddConstraint, CreateIndex, CreateTable

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
AUTHOR = ROOT/'reports/runs/recovery_forward_migrations_0023_0026_20261016'
SOURCE = '16484eaca45791ed2ec403471561faa10ab6d036'
MATERIAL = '2a833225bc5f2dfc720219d6765b034bd6bd6288'


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def git_bytes(revision, path):
    return subprocess.check_output(['git','show',f'{revision}:{path}'],cwd=ROOT)


manifest = json.loads((AUTHOR/'manifest.json').read_text())
rows=[]
for item in manifest['source']+manifest['artifacts']:
    path=item['path']
    raw=(ROOT/path).read_bytes()
    git=git_bytes(SOURCE if item in manifest['source'] else MATERIAL,path)
    row={'path':path,'checkout_raw':digest(raw),'git_lf':digest(git),'expected_raw':item['sha256_raw'],'expected_git_lf':item['sha256_git_lf'],
         'git_matches':digest(git)==item['sha256_git_lf'],'checkout_matches_raw':digest(raw)==item['sha256_raw'],'checkout_normalized_matches_git':raw.replace(b'\r\n',b'\n')==git}
    if item in manifest['source']:
        row['author_worktree_raw']=digest((Path('D:/wt/r07-r12-r10-r18-migrations')/path).read_bytes())
    rows.append(row)
assert all(row['git_matches'] for row in rows)
(RUN/'material_inventory.json').write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8',newline='\n')
inputs=[]
with ZipFile(AUTHOR/'frozen_inputs_raw.zip') as archive:
    assert len(archive.namelist())==4
    for item in json.loads((AUTHOR/'frozen_inputs.json').read_text()):
        raw=archive.read(item['raw_archive_entry'])
        git=git_bytes(item['revision'],item['path'])
        assert digest(raw)==item['sha256_raw']
        assert digest(git)==item['sha256_git_lf']
        assert raw.replace(b'\r\n',b'\n')==git
        assert subprocess.check_output(['git','rev-parse',f"{item['revision']}:{item['path']}"],cwd=ROOT,text=True).strip()==item['git_blob']
        label=item['label']
        inputs.append({**item,'zip_raw_match':True,'git_lf_match':True,'raw_equals_lf':raw==git})
        target=RUN/'pg_author'
        target.mkdir(exist_ok=True)
        (target/item['snapshot']).write_bytes(raw)
        if label=='r07':
            continue
        parsed=ast.parse(raw.decode('utf-8'))
        parsed.body=[node for node in parsed.body if not(isinstance(node,ast.ImportFrom) and node.module and node.module.startswith('ai_intel'))]
        metadata=MetaData()
        Table('users',metadata,Column('user_id',Text,primary_key=True))
        Table('grounded_answers',metadata,Column('answer_id',Text,primary_key=True))
        namespace={'metadata':metadata}
        exec(compile(parsed,str(target/item['snapshot']),'exec'),namespace)
        tables=[t for t in metadata.sorted_tables if t.name not in ('users','grounded_answers')]
        ddl=[str(CreateTable(t).compile(dialect=postgresql.dialect())).strip() for t in tables]
        for table in tables:
            for constraint in sorted(table.foreign_key_constraints,key=lambda c:c.name or ''):
                if constraint.use_alter:
                    ddl.append(str(AddConstraint(constraint).compile(dialect=postgresql.dialect())))
            for index in sorted(table.indexes,key=lambda i:i.name):
                ddl.append(str(CreateIndex(index).compile(dialect=postgresql.dialect())))
        compiled=';\n\n'.join(ddl)+';\n'
        expected=(AUTHOR/(label+'_metadata.sql')).read_bytes().replace(b'\r\n',b'\n')
        assert compiled.encode()==expected
        (target/(label+'_metadata.sql')).write_bytes(compiled.encode())
(RUN/'frozen_inputs_verified.json').write_text(json.dumps(inputs,indent=2)+'\n',encoding='utf-8',newline='\n')
(RUN/'pg_author/approved_guards.json').write_bytes((AUTHOR/'approved_guards.json').read_bytes())
original=ROOT/'backend/tests/contract/test_r11_r08_forward_migrations.py'
raw=original.read_bytes()
text=raw.decode().replace('\r\n','\n')
adapted=text.replace('MIGRATIONS = Path(__file__).resolve().parents[2] / "migrations"',f'MIGRATIONS = Path({str(ROOT/"backend/migrations")!r})').replace('assert scripts.get_heads() == ["0019_aggregate_observations"]','assert scripts.get_heads() == ["0026_api_key_credentials"]').replace('== [\n        "0019_aggregate_observations",','== [\n'+''.join('        "'+s+'",\n' for s in ('0026_api_key_credentials','0025_graph_projection','0024_conversation_context','0023_enrichment_input_audit','0022_sbom_sidecars','0021_condition_assessments','0020_hybrid_retrieval'))+'        "0019_aggregate_observations",')
(RUN/'test_previous_forward_contract.py').write_text(adapted,encoding='utf-8',newline='\n')
(RUN/'prior_head_original.raw').write_bytes(raw)
(RUN/'prior_head_adaptation.diff').write_text(''.join(difflib.unified_diff(text.splitlines(True),adapted.splitlines(True),fromfile=str(original),tofile=str(RUN/'test_previous_forward_contract.py'))),encoding='utf-8',newline='\n')
print(json.dumps({'source_and_artifact_entries':len(rows),'git_mismatches':sum(not r['git_matches'] for r in rows),'checkout_raw_differences':sum(not r['checkout_matches_raw'] for r in rows),'frozen_inputs':len(inputs),'independent_compiler_matches':3}))
