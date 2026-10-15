from pathlib import Path
import json, datetime, subprocess
ROOT=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
WT='/mnt/c/Users/yinha/.codex/worktrees/recovery-r02-review/dianzi/backend/src'
BASE=['wsl','-d','Ubuntu-22.04','-u','root','--','env','CBM_CACHE_DIR=/tmp/dianzi-cbm-r02-persistence-review1-20261015','CBM_ALLOWED_ROOT='+WT,'/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp','cli','--json']
commands=[('cbm2_index',['index_repository','--repo-path',WT,'--mode','fast','--name','r02-persistence-review1','--persistence','false']),('cbm2_schema',['get_graph_schema','--project','r02-persistence-review1','--format','json']),('cbm2_auth_search',['search_graph','--project','r02-persistence-review1','--name-pattern','authenticated_session','--format','json']),('cbm2_publish_search',['search_graph','--project','r02-persistence-review1','--name-pattern','publish','--format','json'])]
for name,args in commands:
    start=datetime.datetime.now().astimezone().isoformat()
    p=subprocess.run(BASE+args,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (ROOT/(name+'.stdout.json')).write_text(p.stdout,encoding='utf-8')
    (ROOT/(name+'.stderr.log')).write_text(p.stderr,encoding='utf-8')
    (ROOT/(name+'.command.json')).write_text(json.dumps({'start':start,'end':datetime.datetime.now().astimezone().isoformat(),'command':BASE+args,'exit_code':p.returncode,'scope':'fixed WT backend/src only; independent cache; excludes secrets holdout reports'},indent=2),encoding='utf-8')
    print(name,p.returncode,p.stdout[:4800])

