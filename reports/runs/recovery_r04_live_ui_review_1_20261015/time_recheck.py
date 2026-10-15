"""Bound new UI to ten minutes and retain redacted directed browser evidence."""
import json,os,subprocess,time,urllib.request
from pathlib import Path
from datetime import datetime
from zoneinfo import ZoneInfo
source=Path(__file__).resolve().parent
run=source/'time_recheck'
run.mkdir(exist_ok=False)
frontend=Path.home()/'.codex/worktrees/r04-ui-time-review/dianzi/frontend'
sha=subprocess.check_output(['git','rev-parse','HEAD'],cwd=frontend,text=True).strip()
assert sha=='d391f89c65fb892b27b6a3b45cf0a06fea6032b0'
now=lambda:datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')
environment=dict(os.environ,API_PROXY_TARGET='http://127.0.0.1:28000')
for name in ('DIANZI_E2E_USERNAME','DIANZI_E2E_PASSWORD'):environment.pop(name,None)
command=['node','--max-old-space-size=384',str(frontend/'node_modules/vite/bin/vite.js'),'--host','127.0.0.1','--port','25305','--strictPort']
started=now()
with (run/'vite.log').open('wb')as log:
 process=subprocess.Popen(command,cwd=frontend,env=environment,stdout=log,stderr=subprocess.STDOUT,creationflags=0x08000000)
 try:
  for _ in range(40):
   if process.poll() is not None:raise RuntimeError('new Vite exited')
   try:urllib.request.urlopen('http://127.0.0.1:25305',timeout=1);break
   except OSError:time.sleep(.2)
  environment=dict(os.environ,PLAYWRIGHT_BROWSERS_PATH=str(Path.home()/'.codex/cache/dianzi/r01_playwright_1248'),UI_REVIEW_RUN_PATH=str(run))
  browser_command=['node',str(source/'time_recheck.mjs')]
  completed=subprocess.run(browser_command,cwd=frontend,env=environment,capture_output=True,timeout=160)
  fragments=set()
  for name in ('DIANZI_E2E_USERNAME','DIANZI_E2E_PASSWORD'):
   value=environment[name];fragments.add(value.encode());fragments.update(value[index:index+8].encode()for index in range(max(0,len(value)-7)))
  def redact(content):
   for fragment in sorted(fragments,key=len,reverse=True):content=content.replace(fragment,b'[redacted identity]')
   return content
  (run/'browser.stdout.json').write_bytes(redact(completed.stdout));(run/'browser.stderr.log').write_bytes(redact(completed.stderr))
  (run/'command.json').write_text(json.dumps({'started_at':started,'ended_at':now(),'frontend_sha':sha,'backend_sha':'7184dc63525ae3e8ea439ec64fc03dfaa629f7a8','cwd':str(frontend),'frontend_command':command,'browser_command':browser_command,'browser_exit_code':completed.returncode,'frontend_pid':process.pid,'maximum_seconds':600,'node_heap_mib':384,'log_limit_bytes':4194304,'trace':'off','video':'off','automatic_screenshots':'off','credentials_in_frontend_environment':False},indent=2),encoding='utf-8')
  assert (run/'vite.log').stat().st_size<=4194304
  print(json.dumps({'exit_code':completed.returncode,'output':str(run/'browser.stdout.json')}))
 finally:
  process.terminate();process.wait(timeout=10)
  (run/'frontend_end.json').write_text(json.dumps({'ended_at':now(),'exit_code':process.returncode,'own_frontend_stopped':True}),encoding='utf-8')
raise SystemExit(completed.returncode)
