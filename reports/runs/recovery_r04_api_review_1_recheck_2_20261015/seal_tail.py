"""Bind final scan/release receipts without rewriting earlier per-batch evidence manifests."""

import hashlib
import json
import subprocess
from datetime import datetime,timedelta,timezone
from pathlib import Path

run = Path(__file__).resolve().parent
root = Path('D:/dianzi')
git = ['git','-C','C:/Users/yinha/.codex/worktrees/recovery-r04-api-review-1-recheck-2/dianzi']
prior = json.loads((run/'manifest_final.json').read_text())
paths_in_prior = {entry['path'] for entry in prior['files']}
paths = [path for path in run.rglob('*') if path.is_file() and '__pycache__' not in path.parts and path.name != 'manifest_tail.json' and path.relative_to(root).as_posix() not in paths_in_prior]
entries = []
for path in sorted(paths):
    relative = path.relative_to(root).as_posix()
    captured = path.read_bytes()
    blob_id = subprocess.check_output(git+['hash-object','-w','--path',relative,'--stdin'],input=captured,stderr=subprocess.DEVNULL).decode().strip()
    blob = subprocess.check_output(git+['cat-file','blob',blob_id])
    entries.append({'path':relative,'captured_sha256':hashlib.sha256(captured).hexdigest(),'captured_size_bytes':len(captured),
        'git_blob_oid':blob_id,'git_blob_sha256':hashlib.sha256(blob).hexdigest(),'git_blob_size_bytes':len(blob)})
result = {'recorded_at':datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
    'code_sha':'7af91b3796ef14a545ba2413acd8254a7f8a095a','tree_sha':'fb6ac8f8c7ac394e4c23c8294b7869397731f785',
    'scope':'post-report secret scan and review-only resource release metadata','files':entries,
    'source_tree_clean':not subprocess.check_output(git+['status','--porcelain'],text=True).strip(),
    'report_sha256':hashlib.sha256((root/'reports/reviews/recovery/G-B-R04-api-review-1-recheck-2.md').read_bytes()).hexdigest()}
(run/'manifest_tail.json').write_text(json.dumps(result,indent=2))
print(json.dumps({'tail_file_count':len(entries),'source_tree_clean':result['source_tree_clean'],'report_sha256':result['report_sha256']}))
