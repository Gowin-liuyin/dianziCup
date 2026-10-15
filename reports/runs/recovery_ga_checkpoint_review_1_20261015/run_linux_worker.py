"""Isolated Linux worker harness: resource remap and hard process death only."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

SOURCE = Path('/mnt/d/dianzi-ga-checkpoint-review-1')
RUN = Path('/mnt/d/dianzi/reports/runs/recovery_ga_checkpoint_review_1_20261015')
WORK = Path('/tmp/dianzi-ga-checkpoint-review1-20261015')


def at() -> str:
    return datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')


def main() -> int:
    from sqlalchemy.engine import make_url
    from redis import Redis

    config = json.loads(Path('/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json').read_text())
    base = make_url(config['TEST_DATABASE_URL'])
    assert base.host == '127.0.0.1' and base.port == 25432 and base.database == 'test_dianzi_r01_20261014'
    environment = dict(os.environ)
    environment.update(TEST_DATABASE_URL=base.set(database='test_dianzi_ga_checkpoint_review_20261015').render_as_string(hide_password=False), DIANZI_TEST_RUN_ID='ga_checkpoint_review_20261015', TEST_REDIS_URL=config['TEST_REDIS_URL'].rsplit('/',1)[0]+'/10', PYTHONIOENCODING='utf-8', PYTHONPATH=str(SOURCE/'backend/src'), APP_ENV='test', DATA_MODE='fixture')
    Redis.from_url(environment['TEST_REDIS_URL']).ping()
    tests = WORK / 'tests'
    tests.mkdir(exist_ok=True)
    original = (SOURCE/'backend/tests/integration/test_r03_executor_celery.py').read_text()
    copied = original.replace('parents[3] / "reports/runs/recovery_r03_executor_20261015"', 'parents[3] / "reports/runs/recovery_r03_executor_20261015"')
    copied = copied.replace('EVIDENCE = Path(__file__).resolve().parents[3] / "reports/runs/recovery_r03_executor_20261015"', 'EVIDENCE = Path('+repr(str(RUN/'worker_processes'))+')')
    copied = copied.replace('parsed.database == "8"', 'parsed.database == "10"').replace('Redis DB8', 'Redis DB10').replace('"--pool=solo"', '"--pool=prefork"')
    copied = copied.replace('arguments,\n            env=environment,', 'arguments,\n            start_new_session=True,\n            env=environment,')
    copied = copied.replace('dying_worker.terminate()', '__import__("signal"); os.killpg(dying_worker.pid, __import__("signal").SIGKILL)')
    (tests/'test_linux_executor.py').write_text(copied)
    fixture = (SOURCE/'backend/tests/conftest.py').read_text().replace('PROJECT_ROOT = Path(__file__).resolve().parents[2]', 'PROJECT_ROOT = Path('+repr(str(SOURCE))+')')
    (tests/'conftest.py').write_text(fixture)
    (RUN/'worker_resource_adaptation.json').write_text(json.dumps(dict(original_sha256=hashlib.sha256(original.encode()).hexdigest(), adapted_sha256=hashlib.sha256(copied.encode()).hexdigest(), changes=['Redis DB8 safety guard to isolated DB10','evidence output outside source tree','Linux prefork pool instead of native Windows solo','own subprocess group and SIGKILL for forced interruption','fixture project root fixed to clean candidate worktree']), indent=2))
    (RUN/'test_linux_executor.py').write_text(copied)
    command=[sys.executable,'-m','pytest',str(tests/'test_linux_executor.py'),'--no-cov','-v','--junitxml='+str(RUN/'linux_worker.xml')]
    started=at()
    try:
        result=subprocess.run(command,cwd=SOURCE/'backend',env=environment,capture_output=True,text=True,timeout=240)
        output=result.stdout+result.stderr
        code=result.returncode
    except subprocess.TimeoutExpired:
        output='bounded Linux worker check timeout'
        code=124
    secrets=[value for value in config.values() if isinstance(value,str)]+[base.password or '',environment['TEST_DATABASE_URL'],environment['TEST_REDIS_URL']]
    for secret in sorted(set(secrets),key=len,reverse=True):
        if secret:
            output=output.replace(secret,'[redacted connection credential]')
    (RUN/'linux_worker.log').write_text(output)
    receipt=dict(command=command,cwd=str(SOURCE/'backend'),started_at=started,ended_at=at(),exit_code=code,pool='Linux prefork',redis_db=10)
    (RUN/'linux_worker.command.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))
    print(output[-3000:])
    return code


if __name__=='__main__':
    raise SystemExit(main())
