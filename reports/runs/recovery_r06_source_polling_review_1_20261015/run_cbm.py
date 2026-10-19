"""Official CBM source-only graph; independent allowed root and cache."""

import json
import os
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

RUN=Path('/mnt/d/wt/r06-source-polling-review-1/reports/runs/recovery_r06_source_polling_review_1_20261015')
SOURCE='/mnt/d/wt/r06-source-polling-review-1/backend/src'
TOOL='/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp'
PROJECT='r06-polling-review-93c458a'
ZONE=timezone(timedelta(hours=8))
environment=dict(os.environ, XDG_CACHE_HOME='/tmp/dianzi-cbm-r06-source-polling-review-1-cache', CBM_ALLOWED_ROOT=SOURCE)
commands=[('version',[TOOL,'--version']), ('index',[TOOL,'cli','index_repository','--repo-path',SOURCE,'--name',PROJECT,'--mode','full']), ('architecture',[TOOL,'cli','get_architecture','--project',PROJECT,'--aspects','overview'])]
for function in ['poll_due_public_sources','enqueue_due_source_collections','enqueue_source_page','build_celery_application','dispatch_pending_jobs','consume_job','build_source_page_handler','execute_job']:
    commands.append(('trace_'+function,[TOOL,'cli','trace_path','--project',PROJECT,'--function-name',function,'--direction','outbound','--depth','4','--limit','250','--max-output-tokens','5000']))
receipts=[]
for label,command in commands:
    start=datetime.now(ZONE).isoformat(timespec='seconds')
    result=subprocess.run(command, cwd=SOURCE, env=environment, capture_output=True, text=True, timeout=90)
    (RUN/('cbm_'+label+'.log')).write_text(result.stdout+result.stderr)
    receipts.append({'label':label, 'command':command, 'started_at':start, 'ended_at':datetime.now(ZONE).isoformat(timespec='seconds'), 'exit_code':result.returncode})
(RUN/'cbm.commands.json').write_text(json.dumps({'source':SOURCE, 'cache':environment['XDG_CACHE_HOME'], 'allowed_root':SOURCE, 'commands':receipts},indent=2))
print(json.dumps({'commands':len(receipts), 'exit_codes':[row['exit_code'] for row in receipts]}))
