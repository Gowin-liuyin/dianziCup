"""Check frozen raw evidence and Git blobs without editing original bytes."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
SOURCE = Path('D:/wt/r07-enrichment-jobs')
RUN = Path(__file__).parent
MATERIAL = '1b894daaa4523f37600c8ff8f9990c5df534a3fa'
CODE = '1f0522e3f3fb9547ea55136efa64fc589466c992'
REL = 'reports/runs/recovery_r07_enrichment_jobs_20261016/artifact_manifest.json'
started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
manifest_bytes = (SOURCE / REL).read_bytes()
assert hashlib.sha256(manifest_bytes).hexdigest() == '7d710ba8be7898f96d7aec796ef02a5fdbdf22ed9f476f5a2487152d928965e1'
manifest = json.loads(manifest_bytes)
assert len(manifest['entries']) == 144
evidence = []
for entry in manifest['entries']:
    relative = entry['path']
    source = (SOURCE / relative).read_bytes()
    blob = subprocess.check_output(['git', 'show', MATERIAL + ':' + relative], cwd=ROOT)
    checkout = (ROOT / relative).read_bytes()
    expected = entry['raw_sha256']
    evidence.append({'path': relative, 'raw_expected_sha256': expected, 'source_raw_sha256': hashlib.sha256(source).hexdigest(), 'material_blob_sha256': hashlib.sha256(blob).hexdigest(), 'review_checkout_sha256': hashlib.sha256(checkout).hexdigest(), 'raw_source_match': hashlib.sha256(source).hexdigest() == expected, 'raw_blob_match': hashlib.sha256(blob).hexdigest() == expected, 'raw_checkout_match': hashlib.sha256(checkout).hexdigest() == expected, 'lf_checkout_matches_blob': checkout.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n')})
commits = ['281371b072a696d972aa3c38519b8646393c98e2', '595e42a91a830f78fd11d0e4fc7a79a1aaf767cb', 'b18349962cb6bee251d0f1d57310366c49175239', CODE]
files = sorted({path for sha in commits for path in subprocess.check_output(['git', 'show', '--name-only', '--format=', sha], cwd=ROOT, text=True).splitlines() if path})
source_rows = []
for relative in files:
    blob = subprocess.check_output(['git', 'show', CODE + ':' + relative], cwd=ROOT)
    checkout = (ROOT / relative).read_bytes()
    source_rows.append({'path': relative, 'git_blob_id': subprocess.check_output(['git', 'rev-parse', CODE + ':' + relative], cwd=ROOT, text=True).strip(), 'code_blob_sha256': hashlib.sha256(blob).hexdigest(), 'checkout_raw_sha256': hashlib.sha256(checkout).hexdigest(), 'checkout_lf_sha256': hashlib.sha256(checkout.replace(b'\r\n', b'\n')).hexdigest(), 'lf_matches_frozen_code_blob': checkout.replace(b'\r\n', b'\n') == blob.replace(b'\r\n', b'\n')})
result = {'started_at': started, 'ended_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'), 'code_sha': CODE, 'material_sha': MATERIAL, 'review_commit_sha': None, 'source_manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(), 'raw_evidence_count': len(evidence), 'source_mismatches': sum(not item['raw_source_match'] for item in evidence), 'blob_mismatches': sum(not item['raw_blob_match'] for item in evidence), 'checkout_raw_mismatches': [item['path'] for item in evidence if not item['raw_checkout_match']], 'evidence_rows': evidence, 'business_commit_filelist': files, 'source_rows': source_rows}
(RUN / 'source_evidence_audit.json').write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
print(json.dumps({key: result[key] for key in ('source_manifest_sha256', 'raw_evidence_count', 'source_mismatches', 'blob_mismatches', 'checkout_raw_mismatches')}))
assert result['source_mismatches'] == result['blob_mismatches'] == 0
assert all(item['lf_checkout_matches_blob'] for item in evidence)
assert all(item['lf_matches_frozen_code_blob'] for item in source_rows)
