"""封存当前字节、来源引用、真实收据与资源释放；manifest 不自摘要。"""

import hashlib
import json
import subprocess
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from checks import now, secret_values

RUN=Path(__file__).resolve().parent
ROOT=RUN.parents[2]
REPORT=ROOT/'reports/reviews/recovery/G-D-recovery-forward-migrations-review-1.md'
with ZipFile(RUN/'review_original_raw.zip','w',compression=ZIP_DEFLATED) as archive:
    for name in ('r07_frozen.sql','r12_frozen.py','r10_frozen.py','r18_frozen.py'):
        archive.writestr(name,(RUN/'pg_author'/name).read_bytes())
    archive.writestr('prior_head_original.raw',(RUN/'prior_head_original.raw').read_bytes())
configured,password=secret_values()
values=[configured,password]
from sqlalchemy.engine import make_url
for path in RUN.rglob('owned_database.json'):
    owned=json.loads(path.read_text())['database']
    values.append(make_url(configured).set(database=owned).render_as_string(hide_password=False))
files=[]
hits=[]
for path in sorted([REPORT,*RUN.rglob('*')]):
    if not path.is_file() or '__pycache__' in path.parts or path.name in ('manifest.json','manifest_receipt.json','seal.json','seal.log'):
        continue
    raw=path.read_bytes()
    decoded=raw.decode('utf-8',errors='ignore')
    if any(value and value in decoded for value in values):
        hits.append(str(path.relative_to(ROOT)))
    clean=raw.replace(b'\r\n',b'\n') if b'\x00' not in raw and path.suffix!='.zip' else raw
    files.append({'path':str(path.relative_to(ROOT)).replace('\\','/'),'bytes':len(raw),'sha256_raw':hashlib.sha256(raw).hexdigest(),'sha256_lf_view':hashlib.sha256(clean).hexdigest(),'lf_view_is_uncommitted_normalization':True})
assert not hits
protected=subprocess.check_output(['git','diff','HEAD','--','backend','docs','contracts','progress','frontend','.gitattributes'],cwd=ROOT)
assert not protected
labels=('contract18','pg60','independent_pg6','prior_contract7','prior_head_original_red','prior_head_own5','code_diffcheck','material_diffcheck','code_ruff','code_mypy','resource_release')
receipts={label:json.loads((RUN/(label+'.json')).read_text()) for label in labels}
manifest={'recorded_at':now(),'reviewer':'/root/recovery_forward_migrations_first_independent_review','worktree':str(ROOT),'branch':'codex/recovery-forward-migrations-review1',
          'reviewed_material':'2a833225bc5f2dfc720219d6765b034bd6bd6288','reviewed_source':'16484eaca45791ed2ec403471561faa10ab6d036','verdict':'Ship','verdict_scope':'forward migrations 0023–0026 only; no whole R card, R20, G-D, or live acceptance','task_status':'awaiting_review','must_fix':[],
          'should_fix':[{'id':1,'file':'backend/tests/integration/test_recovery_forward_migrations_0023_0026_pg.py','line':153,'issue':'Use an attempt-specific evidence directory for repeated pytest runs; pg_1 fixture artifacts were overwritten by pg_2.'}],
          'verification':{'unit':'not_run','contract':'passed_limited_18_plus_7_plus_own_5','integration':'passed_60_plus_6','security':'passed_migration_boundaries_only','frontend':'not_run','e2e':'not_run','live':'not_run','manual':'not_run','pg_server_restart':'not_run'},
          'receipts':receipts,'verified_summary':json.loads((RUN/'verified_evidence_summary.json').read_text()),'resource_release':json.loads((RUN/'release.json').read_text()),'credential_scan':{'actual_dsn_password_owned_dsn_matches':len(hits),'scope':'all current own run artifacts and own report'},
          'artifacts':files,'manifest_excluded_from_own_hash':True,'later_sealing_receipts_not_retroactively_included':True,
          'raw_evidence_note':'Current raw bytes are recorded. LF view is an explicit uncommitted normalization, not a claim of equal raw bytes or an existing Git blob. Exact prior raw inputs are in review_original_raw.zip and the reviewed material frozen_inputs_raw.zip.',
          'protected_diff_bytes':len(protected),'original_author_pg1_limitation':'Top-level pg_1 log/xml/json preserved; reused fixture filenames retain pg_2 outputs only.',
          'original_head_assertion':'unchanged: original 5 cases ran 4 passed/1 failed, exit1; own head-aware copy 5 passed','material_diffcheck':'exit2 preserved; compiler SQL and old red logs whitespace; no trim or global ignore',
          'cbm_projects':['dianzi-forward-review1-164-20261016','dianzi-forward-review1-assets-164-20261016']}
(RUN/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8',newline='\n')
receipt={'recorded_at':now(),'report_sha256_raw':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'manifest_sha256_raw':hashlib.sha256((RUN/'manifest.json').read_bytes()).hexdigest(),'artifacts':len(files),'credential_matches':len(hits)}
(RUN/'manifest_receipt.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(receipt))
