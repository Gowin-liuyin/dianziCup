"""Inspect fixed official graph signatures inside native bounded disposable workers."""
import json,os,subprocess,sys,time
from pathlib import Path
from datetime import datetime
CACHE=Path(r'C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime')
if len(sys.argv)>2 and sys.argv[1]=='worker':
    from ai_intel.infrastructure.models.semantic import E5_MODEL,RERANK_MODEL,_verified_model_directory
    from ai_intel.infrastructure.process_limits import bound_process_resources
    handle=bound_process_resources(memory_bytes=2*1024**3,cpu_seconds=30)
    for key in ['OMP_NUM_THREADS','MKL_NUM_THREADS','OPENBLAS_NUM_THREADS','RAYON_NUM_THREADS']:os.environ[key]='2'
    os.environ['TOKENIZERS_PARALLELISM']='false'
    model=E5_MODEL if sys.argv[2]=='e5' else RERANK_MODEL
    directory=_verified_model_directory(CACHE,model)
    import onnxruntime as ort
    from tokenizers import Tokenizer
    ort.disable_telemetry_events()
    options=ort.SessionOptions();options.intra_op_num_threads=2;options.inter_op_num_threads=1
    options.graph_optimization_level=ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.enable_cpu_mem_arena=False;options.enable_mem_pattern=False
    started=time.monotonic()
    session=ort.InferenceSession(str(directory/'onnx/model.onnx'),options,providers=['CPUExecutionProvider'])
    loaded=time.monotonic()-started
    tokenizer=Tokenizer.from_file(str(directory/'tokenizer.json'));tokenizer.no_padding();tokenizer.no_truncation()
    data={'model_version':model.model_version,'space_description':model.space_description,'inputs':[{'name':x.name,'type':x.type,'shape':x.shape} for x in session.get_inputs()],'outputs':[{'name':x.name,'type':x.type,'shape':x.shape} for x in session.get_outputs()],'graph_load_seconds':loaded,'chinese_token_ids':tokenizer.encode('query: 什么是提示注入攻击？').ids,'pad_token_id':tokenizer.token_to_id('<pad>'),'onnxruntime':ort.__version__}
    print(json.dumps(data,ensure_ascii=False),flush=True)
else:
    import psutil
    name=sys.argv[1] if len(sys.argv)>1 else 'e5'
    started=time.monotonic();peak=0;began=datetime.now().astimezone().isoformat()
    proc=subprocess.Popen([sys.executable,__file__,'worker',name],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    while proc.poll() is None:
        try:
            family=[psutil.Process(proc.pid),*psutil.Process(proc.pid).children(recursive=True)]
            peak=max(peak,sum(member.memory_info().rss for member in family if member.is_running()))
        except psutil.NoSuchProcess:pass
        if time.monotonic()-started>30:proc.kill();proc.wait();break
        time.sleep(0.02)
    stdout,stderr=proc.communicate()
    receipt={'started_at':began,'ended_at':datetime.now().astimezone().isoformat(),'exit_code':proc.returncode,'total_seconds':time.monotonic()-started,'peak_rss_bytes':peak,'stdout':stdout.decode(),'stderr':stderr.decode()}
    Path(__file__).with_name('graph_'+name+'.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False),encoding='utf8')
    print(json.dumps(receipt,ensure_ascii=False));sys.exit(proc.returncode)
