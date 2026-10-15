"""Small platform-native resource probes; each child has a parent eight-second watchdog."""
import json,subprocess,sys,time
from datetime import datetime
cases={
'memory': "from ai_intel.infrastructure.process_limits import bound_process_resources; handle=bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=5); print('LIMIT_APPLIED',flush=True); allocation=bytearray(200*1024**2)",
'cpu': "from ai_intel.infrastructure.process_limits import bound_process_resources\nhandle=bound_process_resources(memory_bytes=100*1024**2,cpu_seconds=1)\nprint('LIMIT_APPLIED',flush=True)\nwhile True:\n pass\n"}
receipt={'started_at':datetime.now().astimezone().isoformat(),'platform':sys.platform,'python':sys.version,'cases':[]}
for name,code in cases.items():
    start=time.monotonic();p=subprocess.run([sys.executable,'-c',code],capture_output=True,timeout=8,check=False)
    receipt['cases'].append({'case':name,'exit_code':p.returncode,'seconds':time.monotonic()-start,'stdout':p.stdout.decode(errors='replace'),'stderr':p.stderr.decode(errors='replace')})
    assert b'LIMIT_APPLIED' in p.stdout and p.returncode!=0
    if name=='memory':assert b'MemoryError' in p.stderr or p.returncode<0
    else:assert b'Traceback' not in p.stderr
receipt['ended_at']=datetime.now().astimezone().isoformat();print(json.dumps(receipt,indent=2))
