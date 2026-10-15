import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN=Path('/mnt/d/dianzi/reports/runs/recovery_r04_pipeline_review_1_20261015')
TOOL='/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp'
SOURCE='/mnt/c/Users/yinha/.codex/worktrees/recovery-r04-pipeline-review/dianzi/backend/src'
PROJECT='dianzi-r04-pipeline-review-95ba650'
environment=dict(os.environ,XDG_CACHE_HOME='/tmp/dianzi-cbm-r04-pipeline-review-cache',CBM_ALLOWED_ROOT=SOURCE)
commands=[
    ('help',[TOOL,'--help']),
    ('index',[TOOL,'cli','index_repository','--repo-path',SOURCE,'--name',PROJECT,'--mode','full']),
    ('schema',[TOOL,'cli','get_graph_schema','--project',PROJECT]),
    ('architecture',[TOOL,'cli','get_architecture','--project',PROJECT,'--aspects','overview']),
]
for name in ('create_application','build_source_router','enqueue_source_page','consume_job','execute_job','build_source_page_handler','persist_source_response','register_response_content','event_detail'):
    commands.append(('trace_'+name,[TOOL,'cli','trace_path','--project',PROJECT,'--function-name',name,'--direction','outbound','--depth','4','--limit','250','--max-output-tokens','5000']))
receipts=[]
for label,command in commands:
    start=datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
    result=subprocess.run(command,env=environment,capture_output=True,text=True,timeout=90,cwd=SOURCE)
    (RUN/('cbm_'+label+'.log')).write_text(result.stdout+result.stderr)
    receipts.append({'label':label,'command':command,'cwd':SOURCE,'started_at':start,'ended_at':datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds'),'exit_code':result.returncode})
(RUN/'cbm.command.json').write_text(json.dumps({'version':'0.11.0','allowed_root':SOURCE,'cache':environment['XDG_CACHE_HOME'],'commands':receipts},indent=2))
print(json.dumps({'commands':len(receipts),'exit_codes':[row['exit_code'] for row in receipts]}))
