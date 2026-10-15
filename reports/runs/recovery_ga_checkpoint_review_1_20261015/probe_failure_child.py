"""Expose the nested pytest collection cause using only synthetic credentials."""
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo

root=Path('D:/dianzi-ga-checkpoint-review-1')
run=Path('D:/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
with tempfile.TemporaryDirectory(prefix='ga-review-probe-') as temporary:
    path=Path(temporary)/'failure_probe.py'
    path.write_text("import os\ndef test_deliberate_failure():\n    assert False, os.environ['TEST_DATABASE_URL']\n",encoding='utf-8')
    environment=dict(os.environ,TEST_DATABASE_URL='postgresql://test_quality:quality-secret-marker@127.0.0.1:25434/test_dianzi_quality',PYTHONPATH=str(root/'backend/tests'),PYTHONIOENCODING='utf-8')
    command=[sys.executable,'-m','pytest','--noconftest','-p','conftest',str(path),'-o','addopts=','-q','--junitxml='+str(run/'failure_child.xml')]
    started=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    result=subprocess.run(command,cwd=root/'backend',env=environment,capture_output=True,text=True,encoding='utf-8',timeout=30)
    output=result.stdout+result.stderr
    output=output.replace(environment['TEST_DATABASE_URL'],'[redacted synthetic test connection]').replace('quality-secret-marker','[redacted synthetic test credential]')
    (run/'failure_child.log').write_text(output,encoding='utf-8')
    receipt=dict(command=command,cwd=str(root/'backend'),started_at=started,ended_at=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),exit_code=result.returncode)
    (run/'failure_child.command.json').write_text(json.dumps(receipt,indent=2))
    print(output)
