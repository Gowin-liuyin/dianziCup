"""Read-only candidate, resource, and authority receipts for the independent review."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from sqlalchemy import create_engine, text

RUN = Path(__file__).resolve().parent
WT = Path('C:/Users/yinha/.codex/worktrees/recovery-r02-minio-review/dianzi')
ROOT = Path('D:/dianzi')


def git(*args: str) -> str:
    return subprocess.check_output(['git', *args], cwd=WT, text=True).strip()


def main() -> int:
    checked_at = datetime.now(timezone(timedelta(hours=8))).isoformat(timespec='seconds')
    docs = ('AGENTS.md', 'docs/plan/00_execution_map.md', 'docs/plan/03_data_contracts.md',
            'docs/plan/05_api_and_tool_contracts.md', 'docs/plan/06_testing_and_evaluation.md',
            'docs/plan/12_recovery_task_cards_20261014.md', 'docs/tasks/T05_persistence_and_raw_store.md',
            'docs/tasks/T06_authentication_and_scope.md', 'docs/tasks/T19_structured_enrichment.md',
            'docs/tasks/T21_claims_entities_conflicts.md', 'docs/decisions/CR-R02.md',
            'docs/decisions/CR-R04-R02_implementation_contract.md', 'docs/decisions/CR-R05.md',
            'progress/task_state.json', 'progress/context_handoff.md')
    hashes = {path: hashlib.sha256((WT/path).read_bytes()).hexdigest() for path in docs}
    for path in ('reports/tasks/R02-minio.md', 'reports/reviews/recovery/G-A-R02-persistence-review-1.md'):
        hashes['main_readonly/' + path] = hashlib.sha256((ROOT/path).read_bytes()).hexdigest()
    wsl_script = '''import hashlib, json, subprocess, urllib.request
from pathlib import Path
binary = Path('/tmp/dianzi-minio-r02-20261015/bin/minio')
group = Path('/sys/fs/cgroup/dianzi-r01-20261014/minio-server-20261015')
result = {'binary_sha256': hashlib.sha256(binary.read_bytes()).hexdigest(),
          'self_reported_version': subprocess.check_output([str(binary), '--version'], text=True).strip(),
          'limits': {field: (group/field).read_text().strip() for field in
                     ('memory.max', 'memory.swap.max', 'cpu.max', 'pids.max')},
          'only_read_process_identifiers': (group/'cgroup.procs').read_text().split()}
with urllib.request.urlopen('http://127.0.0.1:29400/minio/health/live', timeout=2) as response:
    result['health_status'] = response.status
print(json.dumps(result))
'''
    resource = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec', 'python3', '-'],
                              input=wsl_script, capture_output=True, text=True, timeout=15)
    if resource.returncode:
        raise RuntimeError('read-only isolated object resource verification failed')
    engine = create_engine(os.environ['TEST_DATABASE_URL'], connect_args={'connect_timeout': 3})
    with engine.connect() as connection:
        head = connection.execute(text('SELECT version_num FROM alembic_version')).scalar_one()
    engine.dispose()
    record = {'checked_at': checked_at, 'candidate_sha': git('rev-parse', 'HEAD'),
              'candidate_tree': git('rev-parse', 'HEAD^{tree}'), 'branch': git('branch', '--show-current'),
              'status_porcelain': git('status', '--porcelain'), 'authority_hashes': hashes,
              'isolated_database_migration_head': head, 'object_resource': json.loads(resource.stdout),
              'external_source': {'url': 'https://github.com/minio/minio',
                                  'observed_archived_date': '2026-04-25',
                                  'maintenance_state': 'official repository declares no longer maintained',
                                  'distribution': 'official README says source-only; source build is not release binary'}}
    filename = sys.argv[1] if len(sys.argv) > 1 else 'freeze_and_resources.json'
    (RUN/filename).write_text(json.dumps(record, indent=2), encoding='utf-8')
    print(json.dumps({key: value for key, value in record.items() if key != 'authority_hashes'}))
    return 0 if record['status_porcelain']=='' and head=='0009_enrichment_results' else 1


if __name__ == '__main__':
    raise SystemExit(main())
