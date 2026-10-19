"""Record independent runtime, frozen source identity, and actual diff exit codes."""

import datetime
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import ai_intel

ROOT = Path('D:/wt/r10-graph-review1')
RUN = Path(__file__).resolve().parent
BASE = 'cc1b1d302e22048f567475b7084bcd5490761ed2'
CODE = 'b0b7a5b856cc38862f64c01565309564d67c34c0'
FINAL = '16803ce6be9ad6adb6d89f46c594cfa420190c24'
source_path = ROOT / 'backend/tests/integration/test_r10_evidence_graph_pg.py'
copied_path = RUN / 'test_original_graph_pg.py'
original = source_path.read_text(encoding='utf-8')
copy = copied_path.read_text(encoding='utf-8-sig')
assert copy.rstrip() == original.replace('test_dianzi_r06_catalog_r10_graph_20261016', 'test_dianzi_r06_catalog_r10_graph_review1_20261016').rstrip()
receipt = {
    'recorded_at': datetime.datetime.now().astimezone().isoformat(),
    'cwd': str(ROOT), 'python': sys.executable, 'python_version': sys.version,
    'ai_intel_path': ai_intel.__file__, 'code_sha': CODE,
    'versions': {name: importlib.metadata.version(name) for name in ('pytest', 'sqlalchemy', 'psycopg', 'pydantic', 'fastapi', 'ruff', 'mypy')},
    'copy_isolation_change_only': True,
    'original_test_raw_sha256': hashlib.sha256(source_path.read_bytes()).hexdigest(),
    'copied_test_raw_sha256': hashlib.sha256(copied_path.read_bytes()).hexdigest(),
    'diff_checks': [],
}
for label, ref, paths in [('code', CODE, ['backend']), ('material', FINAL, [])]:
    args = ['git', 'diff', '--check', BASE, ref, '--', *paths]
    started = datetime.datetime.now().astimezone().isoformat()
    result = subprocess.run(args, cwd=ROOT, capture_output=True, text=True)
    receipt['diff_checks'].append({'label': label, 'command': args, 'cwd': str(ROOT), 'started_at': started, 'finished_at': datetime.datetime.now().astimezone().isoformat(), 'exit_code': result.returncode, 'output': result.stdout + result.stderr})
receipt['worktree_status'] = subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True)
(RUN / 'metadata_and_diff_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps(receipt, indent=2, ensure_ascii=False))
