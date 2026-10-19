"""Scan owned raw, gzip and report bytes against in-memory actual connection values."""

import gzip
import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
REPORT = ROOT / 'reports/reviews/recovery/G-C-R07-default-durable-entry-review-1.md'
private = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'cat', '/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json'], capture_output=True, check=True)
configuration = json.loads(private.stdout)
original = configuration['TEST_DATABASE_URL']
url = make_url(original)
values = {original, url.password}
redis_url = configuration.get('TEST_REDIS_URL')
if redis_url and make_url(redis_url).password:
    values.add(redis_url)
    values.add(make_url(redis_url).password)
for database in ('test_dianzi_r07_execution_api_review1_20261016', 'test_dianzi_r06_catalog_r07_metadata_review1_20261016'):
    values.add(url.set(database=database).render_as_string(hide_password=False))
values = {value.encode() for value in values if value}
paths = sorted(path for path in RUN.rglob('*') if path.is_file() and '__pycache__' not in path.parts)
if REPORT.exists():
    paths.append(REPORT)
root_manifests = [ROOT / 'reports/runs/recovery_r07_enrichment_jobs_20261016/artifact_manifest.json', ROOT / 'reports/runs/recovery_r07_metadata_head_recheck_20261016/artifact_manifest.json']
for manifest_path in root_manifests:
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    for entry in manifest.get('entries', manifest.get('files', [])):
        paths.append(ROOT / entry['path'])
hits = []
for path in sorted(set(paths)):
    raw = path.read_bytes()
    payloads = [raw]
    if path.suffix == '.gz':
        payloads.append(gzip.decompress(raw))
    if any(value in payload for value in values for payload in payloads):
        hits.append(path.relative_to(ROOT).as_posix())
result = {'created_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'scope': 'review owned raw/gzip/report plus frozen author manifest listed bytes', 'value_source': 'existing WSL connection read in memory only; actual PG password and complete original/reviewer database URLs; Redis credentials if present', 'files_scanned': len(set(paths)), 'actual_value_matches': len(hits), 'matched_paths': hits, 'secret_values_written': False, 'external_requests': 0}
(RUN / 'actual_value_scan.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({'files_scanned': result['files_scanned'], 'actual_value_matches': len(hits)}))
assert not hits, 'actual credential value remains; values are never printed'
