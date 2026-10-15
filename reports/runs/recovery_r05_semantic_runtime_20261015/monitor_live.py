"""Record full live-test command, wall time and sampled memory of all owned descendants."""
import json,os,psutil,subprocess,sys,time
from datetime import datetime
from pathlib import Path
OUT=Path(__file__).parent
start=time.monotonic();started=datetime.now().astimezone().isoformat();peak=0
command=[sys.executable,'-m','pytest','-o','addopts=','tests/live/test_r05_semantic_live.py','-q','-s','--junitxml='+str(OUT/'live_final.xml')]
env=dict(os.environ,R05_SEMANTIC_CACHE=r'C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime')
with (OUT/'live_final.log').open('w',encoding='utf8') as log:
    proc=subprocess.Popen(command,cwd=Path(__file__).parents[3]/'backend',env=env,stdout=log,stderr=log)
    while proc.poll() is None:
        try:
            family=[psutil.Process(proc.pid),*psutil.Process(proc.pid).children(recursive=True)]
            peak=max(peak,sum(member.memory_info().rss for member in family if member.is_running()))
        except psutil.NoSuchProcess:pass
        if time.monotonic()-start>120:
            for member in reversed(family):
                if member.is_running():member.kill()
            proc.wait();break
        time.sleep(0.02)
receipt={'started_at':started,'ended_at':datetime.now().astimezone().isoformat(),'command':command,'exit_code':proc.returncode,'seconds':time.monotonic()-start,'peak_sampled_family_rss_bytes':peak,'per_inference_native_memory_limit':2*1024**3,'per_inference_total_deadline_seconds':30}
(OUT/'live_final.command.json').write_text(json.dumps(receipt,indent=2))
print(json.dumps(receipt));sys.exit(proc.returncode)
