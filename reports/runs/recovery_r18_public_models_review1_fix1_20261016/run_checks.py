"""Bounded independent offline checks on the exact R18 model source."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path('D:/wt/r18pm-r1f1')
RUN = Path(__file__).resolve().parent
PYTHON = Path('D:/dianzi/backend/.venv/Scripts/python.exe')
SOURCE = '011ea225d18b7511a19d7d6056288f799bb83f20'
ZONE = ZoneInfo('Asia/Shanghai')

def run(name: str, arguments: list[str], timeout_seconds: int) -> int:
    started_at = datetime.now(ZONE)
    environment = dict(os.environ)
    environment['PYTHONPATH'] = str(ROOT / 'sdk/python')
    environment['SDK_TEST_EVIDENCE_DIR'] = str(RUN / (name + '_native_evidence'))
    environment['PYTHONDONTWRITEBYTECODE'] = '1'
    environment['MYPY_CACHE_DIR'] = str(RUN / 'mypy_cache')
    command = [str(PYTHON), *arguments]
    with (RUN / f'{name}.log').open('wb') as output:
        child = subprocess.Popen(command, cwd=ROOT, env=environment, stdout=output, stderr=subprocess.STDOUT)
        try:
            exit_code = child.wait(timeout=timeout_seconds)
            timed_out = False
        except subprocess.TimeoutExpired:
            subprocess.run(['taskkill','/PID',str(child.pid),'/T','/F'],
                           stdout=output,stderr=subprocess.STDOUT,timeout=10,check=False)
            child.wait(timeout=10)
            exit_code = 124
            timed_out = True
    ended_at = datetime.now(ZONE)
    receipt = {'command': command, 'workdir': str(ROOT), 'started_at': started_at.isoformat(),
               'ended_at': ended_at.isoformat(), 'elapsed_seconds': (ended_at-started_at).total_seconds(),
               'exit_code': exit_code, 'timed_out': timed_out, 'timeout_seconds': timeout_seconds,
               'pid': child.pid, 'log': f'{name}.log', 'input_source': SOURCE,
               'data_mode': 'synthetic_fixture', 'external_network': 0, 'product_pg': 'not_run',
               'model_live': 'not_run', 'paid_calls': 0}
    xml = RUN / f'{name}.xml'
    if xml.exists():
        suites = list(ET.parse(xml).getroot().iter('testsuite'))
        totals = {key: sum(int(suite.get(key, '0')) for suite in suites) for key in ('tests','failures','errors','skipped')}
        totals['passed'] = totals['tests'] - totals['failures'] - totals['errors'] - totals['skipped']
        receipt['junit_counts'] = totals
    (RUN / f'{name}.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(receipt), flush=True)
    return exit_code

def pytest_args(name: str, *paths: str) -> list[str]:
    return ['-m','pytest',*paths,'-q','--no-cov','-p','no:cacheprovider',
            f'--basetemp={RUN / (name+"_tmp")}',f'--junitxml={RUN / (name+".xml")}']

checks = {
    'eligibility': (pytest_args('eligibility','sdk/python/tests/test_public_extension_models_fix1.py'),120),
    'new_models': (pytest_args('new_models','sdk/python/tests/test_public_extension_models.py'),120),
    'old_sdk': (pytest_args('old_sdk','sdk/python/tests','--ignore=sdk/python/tests/test_public_extension_models.py','--ignore=sdk/python/tests/test_public_extension_models_fix1.py'),300),
    'old_schema': (pytest_args('old_schema','backend/tests/contract/test_r18_public_extensions.py'),60),
    'independent': (pytest_args('independent',str(RUN/'inputs/test_independent_models.py')),120),
    'complete_support': (pytest_args('complete_support',str(RUN/'inputs/test_complete_support.py')),120),
    'style': (['-m','ruff','check','--config','backend/pyproject.toml','sdk/python/ai_intel_client/models.py','sdk/python/ai_intel_client/__init__.py','sdk/python/tests/test_public_extension_models.py','sdk/python/tests/test_public_extension_models_fix1.py'],60),
    'format': (['-m','ruff','format','--check','--config','backend/pyproject.toml','sdk/python/ai_intel_client/models.py','sdk/python/ai_intel_client/__init__.py','sdk/python/tests/test_public_extension_models.py','sdk/python/tests/test_public_extension_models_fix1.py'],60),
    'typing': (['-m','mypy','--strict','--follow-imports=normal','sdk/python/ai_intel_client/models.py'],120),
}
name=sys.argv[1]
arguments, timeout=checks[name]
raise SystemExit(run(name,arguments,timeout))
