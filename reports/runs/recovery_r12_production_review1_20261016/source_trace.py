"""Cross-check static tool paths with actual fixed-tree business callers."""

import hashlib
import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.infrastructure import database

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
assert Path(database.__file__).resolve() == ROOT / 'backend/src/ai_intel/infrastructure/database.py'
assert database.MIGRATIONS_DIR.resolve() == ROOT / 'backend/migrations'

queries = [
    ('retrieval_callers', ['rg', '-n', 'HybridIndexer|HybridRetriever|refresh_scope|hybrid_index|run_migrations|EventEvidenceRetriever', 'backend/src', '-g', '*.py']),
    ('worker_handlers', ['rg', '-n', 'EXECUTION_HANDLERS|SOURCE_JOB_TYPE|consume_job|execute_job|handlers.get', 'backend/src/ai_intel/workers', '-g', '*.py']),
    ('catalog_publication', ['rg', '-n', 'scope_epochs|persist_catalog_documents|outbox|save_change_publication|bump_scope_epoch', 'backend/src/ai_intel/ingestion/catalog_documents.py', 'backend/src/ai_intel/knowledge/revisions.py', 'backend/src/ai_intel/knowledge/persistence.py', 'backend/src/ai_intel/events/persistence.py']),
]
for label, argv in queries:
    started = datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()
    result = subprocess.run(argv, cwd=ROOT, capture_output=True)
    (RUN / (label + '.log')).write_bytes(result.stdout + result.stderr)
    (RUN / (label + '.json')).write_text(json.dumps({'argv': argv, 'cwd': str(ROOT), 'started_at': started, 'ended_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(), 'exit_code': result.returncode}, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'label': label, 'exit_code': result.returncode}))

report = Path('D:/dianzi/reports/reviews/recovery/G-D-R12-hybrid-retrieval-review-1-recheck.md')
before = report.read_bytes()
assert hashlib.sha256(before).hexdigest() == 'fdd7e85122b79c02cd4afc4b0f9a44fbec51322e7761d783920930d9dfb066d8'
(RUN / 'prior_review_scope_reference.md.txt').write_bytes(before)
after = report.read_bytes()
assert before == after
(RUN / 'prior_review_reference_receipt.json').write_text(json.dumps({'path': str(report), 'before_sha256': hashlib.sha256(before).hexdigest(), 'after_sha256': hashlib.sha256(after).hexdigest(), 'review_commit': None, 'role': 'scope boundary reference only'}, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps({'imported_code': 'owned fixed worktree', 'prior_review_unchanged': True}))
