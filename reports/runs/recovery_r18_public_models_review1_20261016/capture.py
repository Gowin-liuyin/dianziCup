"""Capture exact independent read-only commands without shell interpolation."""
from __future__ import annotations
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = Path('D:/wt/r18pm-r1')
ZONE = ZoneInfo('Asia/Shanghai')
PREFIX = ['wsl','-d','Ubuntu-22.04','--','env',
          'CBM_CACHE_DIR=/tmp/dianzi-r18pm-review1-cbm-20261016',
          '/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp']
PROJECT = 'dianzi-r18pm-review1-20261016'
COMMANDS = {
    'cbm_help': PREFIX+['--help'],
    'cbm_cli_help': PREFIX+['cli','--help'],
    'cbm_index': PREFIX+['cli','--json','index_repository',json.dumps({'repo_path':'/mnt/d/wt/r18pm-r1/sdk/python/ai_intel_client','name':PROJECT,'mode':'fast'})],
    'cbm_schema': PREFIX+['cli','--json','get_graph_schema',json.dumps({'project':PROJECT})],
    'cbm_architecture': PREFIX+['cli','--json','get_architecture',json.dumps({'project':PROJECT,'aspects':['all']})],
    'cbm_outline': PREFIX+['cli','--json','get_file_outline',json.dumps({'project':PROJECT,'file_path':'client.py'})],
    'cbm_trace_ask': PREFIX+['cli','--json','trace_path',json.dumps({'project':PROJECT,'function_name':PROJECT+'.client.DianziClient.ask','direction':'outbound','depth':3})],
    'cbm_trace_models': PREFIX+['cli','--json','trace_path',json.dumps({'project':PROJECT,'function_name':PROJECT+'.models.RiskSummary.require_consistent_confirmation','direction':'both','depth':2})],
    'rg_consumers': ['rg','-n','ai_intel_client.models|from ai_intel_client import|StackCheckEnvelope|RiskFinding|RiskSummary|SourcePage|TaskResultEnvelope','sdk/python','backend/src','backend/tests/contract/test_r18_public_extensions.py','tests','-g','*.py','-g','*.toml','-g','*.md'],
    'source_diff': ['git','diff','1315194a8ee421b7f1131a901221f31f4cacb536','be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958','--','sdk/python/ai_intel_client/models.py','sdk/python/ai_intel_client/__init__.py','sdk/python/tests/test_public_extension_models.py'],
    'source_status': ['git','status','--porcelain','--untracked-files=no'],
}
name=sys.argv[1]
command=COMMANDS[name]
start=datetime.now(ZONE)
with (RUN/(name+'.log')).open('wb') as log:
    completed=subprocess.run(command,cwd=ROOT,stdout=log,stderr=subprocess.STDOUT,timeout=60,check=False)
end=datetime.now(ZONE)
receipt={'command':command,'workdir':str(ROOT),'started_at':start.isoformat(),'ended_at':end.isoformat(),
         'exit_code':completed.returncode,'timeout_seconds':60,'log':name+'.log',
         'input_source':'be4b9114eafaf2556f4cb54fefdfdaa2e1cc8958','cache':'/tmp/dianzi-r18pm-review1-cbm-20261016'}
(RUN/(name+'.json')).write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8')
print(json.dumps(receipt),flush=True)
raise SystemExit(completed.returncode)
