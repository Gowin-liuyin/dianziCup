"""Seal all recheck raw artifacts and explicit fixture source bytes without secrets."""

import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ROOT = Path('D:/wt/r10-graph-recheck1')
REPORT = Path('D:/dianzi/reports/reviews/recovery/G-C-R10-pg-evidence-graph-review-1-recheck.md')
started = datetime.datetime.now().astimezone().isoformat()
files = sorted([path for path in RUN.rglob('*') if path.is_file() and '__pycache__' not in path.parts and '.pytest_cache' not in path.parts and path.name != 'reviewer_artifact_manifest.json'] + [REPORT])
private = json.loads(subprocess.check_output(['wsl', '-d', 'Ubuntu-22.04', '-u', 'root', '--', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json']))
target = make_url(private['TEST_DATABASE_URL']).set(database='test_dianzi_r06_catalog_r10_review2_20261016')
needles = [private['postgres_password'].encode(), private['TEST_DATABASE_URL'].encode(), target.render_as_string(hide_password=False).encode()]
entries = []
for path in files:
    content = path.read_bytes()
    assert not any(needle and needle in content for needle in needles)
    entries.append({'path': str(path), 'raw_bytes': len(content), 'raw_sha256': hashlib.sha256(content).hexdigest()})
assert subprocess.check_output(['git', 'status', '--short'], cwd=ROOT, text=True) == ''
manifest = {'code_sha': '3516b9109b9b7f2c5691d78ad0439aea4a659f4f', 'material_sha': '29e1ebddca5cbadffc8c6533bdeeb08b8d63e469', 'verdict': 'needs_changes', 'files': entries, 'command': [sys.executable, str(Path(__file__))], 'cwd': str(ROOT / 'backend'), 'started_at': started, 'finished_at': datetime.datetime.now().astimezone().isoformat(), 'exit_code': 0, 'excluded': ['manifest itself', '__pycache__', '.pytest_cache'], 'recursive_known_private_credential_scan_matches': 0, 'review_worktree_clean': True}
path = RUN / 'reviewer_artifact_manifest.json'
path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'files_sealed': len(entries), 'manifest_sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'report_sha256': hashlib.sha256(REPORT.read_bytes()).hexdigest(), 'report_bytes': REPORT.stat().st_size}, indent=2))
