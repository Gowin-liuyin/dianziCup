"""Seal reviewer raw artifacts only after final material and report verification."""
import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from sqlalchemy.engine import make_url
from review_runner import ROOT,RUN,DBNAME

REPORT=Path('D:/dianzi/reports/reviews/recovery/G-C-R10-pg-evidence-graph-review-1-recheck2.md')
DECISION=Path('D:/dianzi/docs/decisions/CR-R10_graph_fix2_review_scope.md')
started=datetime.datetime.now().astimezone().isoformat()
archive=json.loads((RUN/'archive_verification.json').read_text(encoding='utf-8'))
assert '材料封存尚未到达' not in REPORT.read_text(encoding='utf-8')
files=sorted([path for path in RUN.rglob('*') if path.is_file() and '__pycache__' not in path.parts
              and '.pytest_cache' not in path.parts and path.name!='reviewer_artifact_manifest.json']+[REPORT,DECISION])
private=json.loads(subprocess.check_output(['wsl','-d','Ubuntu-22.04','-u','root','--','cat','/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json']))
target=make_url(private['TEST_DATABASE_URL']).set(database=DBNAME)
needles=[private['postgres_password'].encode(),private['TEST_DATABASE_URL'].encode(),target.render_as_string(hide_password=False).encode()]
entries=[]
for path in files:
    content=path.read_bytes()
    assert not any(needle and needle in content for needle in needles),path
    entries.append({'path':str(path),'raw_bytes':len(content),'raw_sha256':hashlib.sha256(content).hexdigest()})
assert subprocess.check_output(['git','status','--short'],cwd=ROOT,text=True)==''
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip()=='08b141bd437c1de70a8435a1f7f6c448a131ed0d'
manifest={'code_sha':'08b141bd437c1de70a8435a1f7f6c448a131ed0d','material_sha':archive['material_sha'],
          'verdict':'Ship','scope':'fixed PostgreSQL read service/router factory and Fix2 targeted recheck only',
          'files':entries,'command':[sys.executable,str(Path(__file__))],'cwd':str(ROOT/'backend'),
          'started_at':started,'finished_at':datetime.datetime.now().astimezone().isoformat(),'exit_code':0,
          'excluded':['manifest itself','__pycache__','.pytest_cache'],'recursive_known_private_credential_scan_matches':0,
          'review_worktree_clean':True,'old_red_results_preserved':True,'business_progress_accepted_push_changed':False,
          'not_checked':['frontend','main App e2e','Neo4j full graph/rebuild','live sources/model/provider','manual semantics','whole R10/G-C']}
path=RUN/'reviewer_artifact_manifest.json'
path.write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
print(json.dumps({'files_sealed':len(entries),'manifest_sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                  'report_sha256':hashlib.sha256(REPORT.read_bytes()).hexdigest(),'report_bytes':REPORT.stat().st_size,
                  'scope_clarification_sha256':hashlib.sha256(DECISION.read_bytes()).hexdigest(),
                  'code_sha':manifest['code_sha'],'material_sha':manifest['material_sha']},indent=2))
