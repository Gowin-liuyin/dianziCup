"""Verify final authored raw/blob rows and original failure probes without reading excluded cache."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).parent
AUTHOR = Path('D:/wt/r07-idempotency-scope')
MATERIAL = '9982c5ec444cef429cef554bdd2e85253c1afe82'
CODE = 'ba69d6cbc2bc4828a56bdc8c7d2f2c95c4dda5ce'
RAW = 'reports/runs/recovery_r07_idempotency_scope_20261016/raw_manifest.json'
FIX = 'reports/runs/recovery_r07_idempotency_scope_20261016/bytes_fix_manifest.json'
started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
raw_bytes = (ROOT / RAW).read_bytes()
fix_bytes = (ROOT / FIX).read_bytes()
assert hashlib.sha256(raw_bytes).hexdigest() == '2dbdad200695ea322ab104548f068c2fdd86f42d2abc80fb76139d6c3ab1826a'
assert hashlib.sha256(fix_bytes).hexdigest() == '9bc0e8c15649dc7ee919953afb93b1dc04221cc9b257e8b6a89ae46e10f8d5c8'
original, fixed = json.loads(raw_bytes), json.loads(fix_bytes)
excluded = {row['path'] for row in fixed['excluded_generated_cache_rows']}
assert len(excluded) == 5 and all('__pycache__' in Path(path).parts for path in excluded)
assert not subprocess.check_output(['git', 'diff', CODE, MATERIAL, '--', 'backend/src', 'backend/tests', 'backend/migrations', 'contracts', 'backend/pyproject.toml', 'backend/uv.lock'], cwd=ROOT)
rows = []
for group in ('original_material_rows_git_verified', 'additional_material_rows_git_verified'):
    for entry in fixed[group]:
        path = entry['path']
        assert path not in excluded and '__pycache__' not in Path(path).parts
        author = (AUTHOR / path).read_bytes()
        blob = subprocess.check_output(['git', 'show', MATERIAL + ':' + path], cwd=ROOT)
        checkout = (ROOT / path).read_bytes()
        expected = entry['raw_sha256']
        row = {'path': path, 'group': group, 'expected_raw_sha256': expected, 'author_raw_match': hashlib.sha256(author).hexdigest() == expected, 'material_blob_match': hashlib.sha256(blob).hexdigest() == expected, 'checkout_raw_match': hashlib.sha256(checkout).hexdigest() == expected, 'checkout_lf_matches_blob': checkout.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n')}
        assert row['author_raw_match'] and row['material_blob_match'] and row['checkout_lf_matches_blob']
        rows.append(row)
source = []
for entry in original['changed_source']:
    path = entry['path']
    blob = subprocess.check_output(['git', 'show', CODE + ':' + path], cwd=ROOT)
    assert hashlib.sha256(blob).hexdigest() == entry['lf_sha256']
    assert (ROOT / path).read_bytes().replace(b'\r\n', b'\n') == blob
    source.append({'path': path, 'frozen_code_sha256': entry['lf_sha256'], 'code_blob_verified': True, 'review_checkout_lf_verified': True})
probes = []
for entry in original['original_probes']:
    old = Path(entry['original_path']).read_bytes()
    author = (ROOT / entry['copy']).read_bytes()
    own = (RUN / 'probes' / Path(entry['copy']).name).read_bytes()
    assert old == author == own
    assert hashlib.sha256(old).hexdigest() == entry['raw_sha256']
    probes.append({'path': entry['copy'], 'original_sha256': entry['raw_sha256'], 'all_three_raw_identical': True})
baseline = ROOT / 'reports/runs/recovery_r07_idempotency_scope_20261016/baseline_job_service.py'
assert baseline.read_bytes() == subprocess.check_output(['git', 'show', 'e61d9d6dd1215c337755d32d112dfe70f13d9e94:backend/src/ai_intel/enrichment/job_service.py'], cwd=ROOT)
assert hashlib.sha256(baseline.read_bytes()).hexdigest() == '13dd4cfe22ab590bcf74483656d7ef1c9eb745f0bc02909d0876029b5a1daa5e'
result = {'started_at': started, 'ended_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'business_code_sha': CODE, 'material_sha': MATERIAL, 'raw_manifest_sha256': hashlib.sha256(raw_bytes).hexdigest(), 'bytes_fix_manifest_sha256': hashlib.sha256(fix_bytes).hexdigest(), 'original_raw_rows_verified': 48, 'additional_metadata_rows_verified': 10, 'source_lf_rows_verified': len(source), 'excluded_cache_rows': 5, 'excluded_cache_current_content_read': False, 'rows': rows, 'source_rows': source, 'original_probes': probes, 'baseline_raw_sha256': hashlib.sha256(baseline.read_bytes()).hexdigest(), 'checkout_raw_normalization_differences': [row['path'] for row in rows if not row['checkout_raw_match']], 'review_commit_sha': None}
(RUN / 'material_audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: result[key] for key in ('original_raw_rows_verified', 'additional_metadata_rows_verified', 'source_lf_rows_verified', 'excluded_cache_rows', 'excluded_cache_current_content_read', 'checkout_raw_normalization_differences')}))
