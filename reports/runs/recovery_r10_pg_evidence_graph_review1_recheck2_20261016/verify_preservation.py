"""Check both previous reviewer seals without rewriting any old artifact."""
import hashlib
import json
from pathlib import Path
from review_runner import RUN

receipts = []
for name in ('recovery_r10_pg_evidence_graph_review1_20261016', 'recovery_r10_pg_evidence_graph_review1_recheck_20261016'):
    manifest_path = Path('D:/dianzi/reports/runs')/name/'reviewer_artifact_manifest.json'
    content = manifest_path.read_bytes()
    manifest = json.loads(content)
    for entry in manifest['files']:
        raw = Path(entry['path']).read_bytes()
        assert len(raw) == entry['raw_bytes'] and hashlib.sha256(raw).hexdigest() == entry['raw_sha256'], entry['path']
    receipts.append({'manifest': str(manifest_path), 'bytes': len(content), 'sha256': hashlib.sha256(content).hexdigest(), 'files_verified': len(manifest['files']), 'all_match': True})
(RUN/'original_archive_preservation.json').write_text(json.dumps(receipts, indent=2), encoding='utf-8')
print(json.dumps(receipts, indent=2))
