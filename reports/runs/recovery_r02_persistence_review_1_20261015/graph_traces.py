from pathlib import Path
import json,datetime,subprocess
ROOT=Path(r'D:\dianzi\reports\runs\recovery_r02_persistence_review_1_20261015')
BASE=['wsl','-d','Ubuntu-22.04','-u','root','--','env','CBM_CACHE_DIR=/tmp/dianzi-cbm-r02-persistence-review1-20261015','CBM_ALLOWED_ROOT=/mnt/c/Users/yinha/.codex/worktrees/recovery-r02-review/dianzi/backend/src','/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp','cli','--json']
project='r02-persistence-review1'
commands=[('cbm_auth_exact',['search_graph','--project',project,'--qn-pattern',project+'.ai_intel.api.authentication.AuthenticationSessionService.authenticated_session','--format','json']),('cbm_auth_trace',['trace_path','--project',project,'--function-name',project+'.ai_intel.api.authentication.AuthenticationSessionService.authenticated_session','--direction','both','--depth','3','--include-evidence','true','--format','json']),('cbm_publish_exact',['search_graph','--project',project,'--qn-pattern',project+'.ai_intel.knowledge.persistence.KnowledgeRepository.publish','--format','json']),('cbm_publish_trace',['trace_path','--project',project,'--function-name',project+'.ai_intel.knowledge.persistence.KnowledgeRepository.publish','--direction','both','--depth','2','--include-evidence','true','--format','json']),('cbm_app_trace',['trace_path','--project',project,'--function-name',project+'.ai_intel.api.app.create_application','--direction','outbound','--depth','2','--include-evidence','true','--format','json'])]
for name,args in commands:
    start=datetime.datetime.now().astimezone().isoformat()
    p=subprocess.run(BASE+args,capture_output=True,text=True,encoding='utf-8',errors='replace')
    (ROOT/(name+'.stdout.json')).write_text(p.stdout,encoding='utf-8')
    (ROOT/(name+'.stderr.log')).write_text(p.stderr,encoding='utf-8')
    (ROOT/(name+'.command.json')).write_text(json.dumps({'start':start,'end':datetime.datetime.now().astimezone().isoformat(),'command':BASE+args,'exit_code':p.returncode},indent=2),encoding='utf-8')
    print(name,p.returncode,p.stdout[:2300])
