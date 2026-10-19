"""Reuse sealed first-review probes without changing their bytes or expectations."""
from __future__ import annotations
import hashlib
import json
import subprocess
from pathlib import Path

WORKTREE=Path('D:/wt/r18pm-r1f1')
RUN=Path(__file__).resolve().parent
FIRST='a7bee69be46d3b9ecc611f188723a81cb2569dd2'
FIRST_RUN='reports/runs/recovery_r18_public_models_review1_20261016/'
SOURCE='011ea225d18b7511a19d7d6056288f799bb83f20'

def read_first(name: str) -> bytes:
    return subprocess.run(['git','show',FIRST+':'+FIRST_RUN+name],cwd=WORKTREE,
                          capture_output=True,check=True).stdout

(RUN/'inputs').mkdir()
probes=[]
for name in ('test_independent_models.py','test_complete_support.py'):
    raw=read_first(name)
    (RUN/'inputs'/name).write_bytes(raw)
    probes.append({'path':name,'sha256':hashlib.sha256(raw).hexdigest(),
                   'first_review_commit':FIRST,'bytes_unchanged':True})
(RUN/'probe_inputs.json').write_text(json.dumps(probes,indent=2)+'\n',encoding='utf-8',newline='\n')
runner=read_first('run_checks.py').decode()
runner=runner.replace("ROOT = Path('D:/wt/r18pm-r1')","ROOT = Path('D:/wt/r18pm-r1f1')")
runner=runner.replace('be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958',SOURCE)
runner=runner.replace("str(RUN/'test_independent_models.py')","str(RUN/'inputs/test_independent_models.py')")
runner=runner.replace("str(RUN/'test_complete_support.py')","str(RUN/'inputs/test_complete_support.py')")
runner=runner.replace("'--ignore=sdk/python/tests/test_public_extension_models.py'",
                      "'--ignore=sdk/python/tests/test_public_extension_models.py','--ignore=sdk/python/tests/test_public_extension_models_fix1.py'")
runner=runner.replace("checks = {","checks = {\n    'eligibility': (pytest_args('eligibility','sdk/python/tests/test_public_extension_models_fix1.py'),120),")
runner=runner.replace("'sdk/python/tests/test_public_extension_models.py'],60)",
                      "'sdk/python/tests/test_public_extension_models.py','sdk/python/tests/test_public_extension_models_fix1.py'],60)")
(RUN/'run_checks.py').write_text(runner,encoding='utf-8',newline='\n')
capture=read_first('capture.py').decode().replace('D:/wt/r18pm-r1','D:/wt/r18pm-r1f1')
capture=capture.replace('be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958',SOURCE)
capture=capture.replace('dianzi-r18pm-review1-cbm-20261016','dianzi-r18pm-review1-fix1-cbm-20261016')
capture=capture.replace('dianzi-r18pm-review1-20261016','dianzi-r18pm-review1-fix1-20261016')
capture=capture.replace("'1315194a8ee421b7f1131a901221f31f4cacb536'","'be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958'")
(RUN/'capture.py').write_text(capture,encoding='utf-8',newline='\n')
print(json.dumps({'source':SOURCE,'probes':probes,'runner':str(RUN/'run_checks.py')}))
