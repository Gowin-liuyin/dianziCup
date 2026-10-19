"""Expose both frozen stale branches without environment, database or wall-time changes."""

import json
import sys
from pathlib import Path

RUN=Path('D:/dianzi-runtime-cache/r06-live-e310-run-20261016/reports/runs/recovery_r06_live_restart_preparation_20261016')
sys.path.insert(0,str(RUN))
from runtime_controls import resource_guard_reason

rows=[{'snapshot_age_seconds':age,'reason':resource_guard_reason(42,196.34375,645,141538,age)} for age in [-0.000001,0,3,3.000001]]
assert rows[0]['reason']==rows[3]['reason']=='guard_snapshot_stale'
assert rows[1]['reason'] is None and rows[2]['reason'] is None
print(json.dumps({'fixed_tool_sha':'44c94151840213d9e5ab7c653778d4ae3219c630','cases':rows,'historical_failure_reproduced':False,'env_or_db_access':0,'source_http':0}))
