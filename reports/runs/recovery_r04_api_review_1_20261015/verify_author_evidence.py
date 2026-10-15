"""Verify both the author's captured bytes and committed normalized Git blobs."""

import hashlib
import json
import subprocess
from pathlib import Path

run = Path(__file__).resolve().parent
root = Path('C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1/dianzi')
author = Path('C:/Users/yinha/.codex/worktrees/recovery-r04-knowledge-api/dianzi')
git = ['git','-C',str(root)]
commit = subprocess.check_output(git + ['rev-parse','bd16aa3'],text=True).strip()
index_path = 'reports/runs/recovery_r04_knowledge_api_20261015/evidence_index.json'
manifest_blob = subprocess.check_output(git + ['show',commit + ':' + index_path])
manifest = json.loads(manifest_blob)
rows = []
allowed_source_paths = {
    'backend/src/ai_intel/api/app.py',
    'backend/src/ai_intel/api/knowledge_read_service.py',
    'backend/src/ai_intel/api/knowledge_routes.py',
    'backend/tests/unit/test_r04_knowledge_api_cursor.py',
    'backend/tests/integration/test_r04_knowledge_api_pg.py',
}
for item in manifest:
    path = item['path']
    if not path.startswith('reports/runs/recovery_r04_knowledge_api_20261015/') and path != 'reports/tasks/R04-knowledge-api.md' and path not in allowed_source_paths:
        raise RuntimeError('author evidence path outside the authorized report boundary')
    captured = (author/path).read_bytes()
    blob = subprocess.check_output(git + ['show',commit + ':' + path])
    rows.append({'path':path,
        'captured_match':hashlib.sha256(captured).hexdigest() == item['captured_sha256'] and len(captured) == item['captured_size_bytes'],
        'git_blob_match':hashlib.sha256(blob).hexdigest() == item['git_blob_sha256'] and len(blob) == item['git_blob_size_bytes'],
        'captured_actual_sha256':hashlib.sha256(captured).hexdigest(),
        'git_blob_actual_sha256':hashlib.sha256(blob).hexdigest()})
product = []
for path in ['backend/src/ai_intel/api/knowledge_read_service.py','backend/src/ai_intel/api/knowledge_routes.py',
             'backend/tests/unit/test_r04_knowledge_api_cursor.py','backend/tests/integration/test_r04_knowledge_api_pg.py']:
    before = subprocess.check_output(git + ['show','6e7c4c7aeea5f9d25deaa4b676b63dda65af477e:' + path])
    reviewed = subprocess.check_output(git + ['show','4934de35a02c1b8841a9e364d31fa281cf3c0f5d:' + path])
    product.append({'path':path,'same_blob_bytes':before==reviewed,'sha256':hashlib.sha256(reviewed).hexdigest()})
result = {'evidence_commit':commit,'earlier_evidence_commit':subprocess.check_output(git+['rev-parse','d97703a9'],text=True).strip(),
    'manifest_git_blob_sha256':hashlib.sha256(manifest_blob).hexdigest(),
    'item_count':len(rows),'captured_mismatch_count':sum(not row['captured_match'] for row in rows),
    'git_blob_mismatch_count':sum(not row['git_blob_match'] for row in rows),
    'rows':rows,'author_to_review_product_blobs':product,
    'scope_note':'integrity only; author tests are not independent reviewer test results'}
(run/'author_evidence_verification.json').write_text(json.dumps(result,indent=2))
print(json.dumps({key:value for key,value in result.items() if key not in {'rows','author_to_review_product_blobs'}}))
raise SystemExit(0 if not result['captured_mismatch_count'] and not result['git_blob_mismatch_count'] and all(p['same_blob_bytes'] for p in product) else 1)
