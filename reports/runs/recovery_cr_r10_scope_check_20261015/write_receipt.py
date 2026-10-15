"""Read-only documentation scope receipt; no tests or dependency changes."""
import hashlib
import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path('D:/dianzi')
RUN = Path(__file__).resolve().parent
paths = ('AGENTS.md', 'prompts/12_full_delivery_parallel_push.txt',
         'docs/decisions/CR-R10_vitest_security_upgrade.md', 'docs/decisions/CR-R02.md',
         'docs/plan/11_full_delivery_recovery_20261014.md',
         'docs/plan/12_recovery_task_cards_20261014.md',
         'reports/reviews/recovery/G-A-R01-dependency-review-1.md',
         'reports/reviews/recovery/G-A-R00-activation-check.md',
         'reports/reviews/recovery/G-A-CR-R10-scope-check.md')
commands = [
    ['git', 'diff', '--name-only', 'd0a179eeb3621cdf21a4cba94a6b5bd4e8a2a120..497740a', '--', 'frontend'],
    ['git', 'diff', '497740a^..497740a', '--', 'frontend/package.json'],
    ['git', 'show', '497740a:frontend/vite.config.ts'],
]
records = []
for command in commands:
    start = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding='utf-8')
    records.append({'start': start,
                    'end': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
                    'argv': command, 'cwd': str(ROOT), 'exit_code': result.returncode,
                    'stdout': result.stdout, 'stderr': result.stderr})
receipt = {'written_at': datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds'),
           'candidate': '497740a771e7cb2d719ab22ebad34bd30539e20d',
           'scope': 'authorization interpretation only; no new technical test approval',
           'hashes': {path: hashlib.sha256((ROOT/path).read_bytes()).hexdigest() for path in paths},
           'commands': records, 'tests_executed': 0,
           'business_or_dependency_changes': [], 'global_state_changes': [], 'commits_or_pushes': []}
(RUN/'scope_receipt.json').write_text(json.dumps(receipt, indent=2, ensure_ascii=False), encoding='utf-8')
print(json.dumps({'written_at': receipt['written_at'], 'tests_executed': 0,
                  'all_document_commands_exit_zero': all(item['exit_code']==0 for item in records)}))
