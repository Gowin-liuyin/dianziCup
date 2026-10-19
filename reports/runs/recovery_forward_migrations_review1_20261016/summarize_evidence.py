"""独立归并实际测试、旧行、原字节和受保护文件证据。"""

import hashlib
import json
import subprocess
from pathlib import Path
from xml.etree import ElementTree

RUN=Path(__file__).resolve().parent
ROOT=RUN.parents[2]
AUTHOR=ROOT/'reports/runs/recovery_forward_migrations_0023_0026_20261016'
SOURCE='16484eaca45791ed2ec403471561faa10ab6d036'
material=json.loads((AUTHOR/'manifest.json').read_text())
sources=[]
for row in material['source']:
    actual=subprocess.check_output(['git','rev-parse',f"{SOURCE}:{row['path']}"],cwd=ROOT,text=True).strip()
    author=(Path('D:/wt/r07-r12-r10-r18-migrations')/row['path']).read_bytes()
    assert actual==row['git_blob']
    assert hashlib.sha256(author).hexdigest()==row['sha256_raw']
    sources.append({'path':row['path'],'git_blob':actual,'author_raw_matches':True})
history=[]
for prefix in ('pg_author','pg_independent'):
    directory=RUN/prefix
    before=json.loads((directory/'history_0022_before.json').read_text())
    changed=[]
    for revision in ('0023','0024','0025','0026'):
        after=json.loads((directory/f'history_{revision}_after.json').read_text())
        for table in before:
            if before[table]!=after[table]:
                changed.append({'revision':revision,'table':table})
    assert not changed
    history.append({'attempt':prefix,'legacy_tables':len(before),'tables_with_rows':sum(bool(v) for v in before.values()),'rows':sum(len(v) for v in before.values()),'per_column_row_differences':len(changed),'raw_bytes_sha256':hashlib.sha256((directory/'raw_content.bin').read_bytes()).hexdigest()})
original=ROOT/'backend/tests/contract/test_r11_r08_forward_migrations.py'
assert original.read_bytes()==(RUN/'prior_head_original.raw').read_bytes()
protected=['backend/src','backend/tests','backend/migrations','docs','contracts','progress','.gitattributes','backend/pyproject.toml','backend/uv.lock','frontend']
diff=subprocess.check_output(['git','diff','HEAD','--',*protected],cwd=ROOT)
assert not diff
pg=ElementTree.parse(RUN/'pg60.xml').getroot().find('testsuite')
assert pg is not None
names=[t.get('name') for t in pg.findall('testcase')]
old=sum(n.startswith('test_previous_aggregate_') for n in names)
assert old==15 and len(names)-old==45
audit=json.loads((RUN/'material_inventory.json').read_text())
summary={'source_blobs':sources,'manifest_entries':len(audit),'git_lf_mismatches':sum(not r['git_matches'] for r in audit),'checkout_raw_differences':sum(not r['checkout_matches_raw'] for r in audit),'checkout_non_eol_differences':sum(not r['checkout_normalized_matches_git'] for r in audit),'old_history':history,'author_pg_cases':45,'unchanged_previous_aggregate_cases':old,'protected_diff_bytes':len(diff),'original_head_test_unchanged':True,'material_diffcheck_exit':json.loads((RUN/'material_diffcheck.json').read_text())['exit_code'],'code_diffcheck_exit':json.loads((RUN/'code_diffcheck.json').read_text())['exit_code']}
(RUN/'verified_evidence_summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(summary))
