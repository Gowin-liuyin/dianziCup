"""Freeze captured bytes and normalized Git blobs; create no commit or index mutation."""

import hashlib
import json
import subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path

root = Path('D:/dianzi')
cases = [
    ('recovery_r04_api_review_1_20261015','G-B-R04-api-review-1.md','4934de35a02c1b8841a9e364d31fa281cf3c0f5d','eecdd8d361898f550795555d3ffd58b8f630dfe7','recovery-r04-api-review-1','needs_changes'),
    ('recovery_r04_api_review_1_recheck_20261015','G-B-R04-api-review-1-recheck.md','95ba6503dcae4b86ea8fdffea150f1b59a941014','25afdc66cbac783fddc748b434a2244d685c96b6','recovery-r04-api-review-1-recheck','needs_changes'),
    ('recovery_r04_api_review_1_recheck_2_20261015','G-B-R04-api-review-1-recheck-2.md','7af91b3796ef14a545ba2413acd8254a7f8a095a','fb6ac8f8c7ac394e4c23c8294b7869397731f785','recovery-r04-api-review-1-recheck-2','limited_technical_pass'),
]
for folder,report_name,sha,tree,worktree_name,status in cases:
    run = root/'reports/runs'/folder
    checkout = Path('C:/Users/yinha/.codex/worktrees')/worktree_name/'dianzi'
    git = ['git','-C',str(checkout)]
    assert subprocess.check_output(git+['rev-parse','HEAD'],text=True).strip() == sha
    assert not subprocess.check_output(git+['status','--porcelain'],text=True).strip()
    paths = [path for path in run.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name not in {'manifest_final.json'}]
    paths.append(root/'reports/reviews/recovery'/report_name)
    entries = []
    for path in sorted(paths):
        relative = path.relative_to(root).as_posix()
        captured = path.read_bytes()
        blob_id = subprocess.check_output(git+['hash-object','-w','--path',relative,'--stdin'],input=captured,stderr=subprocess.DEVNULL).decode().strip()
        blob = subprocess.check_output(git+['cat-file','blob',blob_id])
        entries.append({'path':relative,'captured_sha256':hashlib.sha256(captured).hexdigest(),
            'captured_size_bytes':len(captured),'git_blob_oid':blob_id,
            'git_blob_sha256':hashlib.sha256(blob).hexdigest(),'git_blob_size_bytes':len(blob)})
    result = {'recorded_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
        'code_sha':sha,'tree_sha':tree,'source_tree_clean':True,'status':status,
        'normalization_note':'Git blobs use the frozen worktree attributes/core.autocrlf; capture bytes are unchanged. Legacy receipts log_sha256 hashes decoded subprocess output before Windows newline translation; captured log hashes in this manifest are authoritative for on-disk bytes.',
        'commit_or_index_mutated':False,'files':entries}
    (run/'manifest_final.json').write_text(json.dumps(result,indent=2))
    print(json.dumps({'run':folder,'file_count':len(entries),'sha':sha,'status':status,
        'normalized_different_count':sum(item['captured_sha256']!=item['git_blob_sha256'] for item in entries)}))
