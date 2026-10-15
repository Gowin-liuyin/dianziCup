"""Official SDK selective downloader, with external memory and elapsed-time watchdog."""
import hashlib,json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime
import psutil
ROOT=Path(r'C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime')
OUT=Path(__file__).parent
MODEL_NAMES=[('multilingual-e5-small.metadata.json','e5'),('mmarco.metadata.json','mmarco')]
if len(sys.argv)>1 and sys.argv[1]=='worker':
    from huggingface_hub import hf_hub_download
    receipt={'started_at':datetime.now().astimezone().isoformat(),'artifacts':[],'transport':'huggingface_hub1.33.0/hf-xet1.7.0'}
    for metadata_name,folder in MODEL_NAMES:
        model=json.loads((ROOT/metadata_name).read_text())
        for filename in ['onnx/model.onnx','tokenizer.json','config.json']:
            artifact=next(f for f in model['files'] if f['rfilename']==filename)
            assert artifact['size'] < 500_000_000
            path=Path(hf_hub_download(model['id'],filename,revision=model['sha'],local_dir=ROOT/folder,token=False))
            with path.open('rb') as f: actual_sha=hashlib.file_digest(f,'sha256').hexdigest()
            assert path.stat().st_size == artifact['size']
            if 'lfs' in artifact: assert actual_sha == artifact['lfs']['sha256']
            receipt['artifacts'].append({'model':model['id'],'revision':model['sha'],'filename':filename,'bytes':path.stat().st_size,'sha256':actual_sha,'license':model['license']})
            (OUT/'artifacts_sdk.json').write_text(json.dumps(receipt,indent=2))
            print(folder,filename,path.stat().st_size,actual_sha,flush=True)
    receipt['ended_at']=datetime.now().astimezone().isoformat()
    (OUT/'artifacts_sdk.json').write_text(json.dumps(receipt,indent=2))
else:
    started=time.monotonic();peak=0
    env=dict(os.environ,HF_HOME=str(ROOT/'hf'),HF_HUB_DISABLE_TELEMETRY='1',HF_HUB_DISABLE_PROGRESS_BARS='1',HF_XET_NUM_CONCURRENT_RANGE_GETS='2',HF_XET_CHUNK_CACHE_SIZE_BYTES='0',HF_HUB_DOWNLOAD_TIMEOUT='20')
    with (OUT/'download_sdk_segment2.log').open('w') as log:
        proc=subprocess.Popen([sys.executable,__file__,'worker'],stdout=log,stderr=log,env=env)
        while proc.poll() is None:
            process=psutil.Process(proc.pid)
            family=[process,*process.children(recursive=True)]
            rss=sum(member.memory_info().rss for member in family if member.is_running())
            peak=max(peak,rss)
            if rss>int(1.8*1024**3) or time.monotonic()-started>480:
                
                for member in reversed(family):
                    if member.is_running():member.kill()
                proc.wait();break
            time.sleep(0.2)
    receipt={'exit_code':proc.returncode,'elapsed_seconds':time.monotonic()-started,'peak_rss_bytes':peak,'ended_at':datetime.now().astimezone().isoformat(),'deadline_seconds':480}
    (OUT/'download_watchdog_segment2.json').write_text(json.dumps(receipt,indent=2));print(json.dumps(receipt))
    sys.exit(proc.returncode)
