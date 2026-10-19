"""Execute the frozen supervisor failure branch inside a disposable real nested Job."""

import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import review_driver as review

RUN = Path(__file__).resolve().parent
PREP = RUN.parent / "recovery_r06_live_restart_preparation_20261016"

CHILD = r'''
import ast,json,sys,time,subprocess
from pathlib import Path
sys.path.insert(0,sys.argv[1])
from runtime_limits import OwnedJob
from owned_stop_watcher import current_windows_identity
from windows_actor import OwnershipError
job=OwnedJob()
leaf=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)'],creationflags=0x08000000)
print(json.dumps({'identity':current_windows_identity(),'leaf_launcher':leaf.pid}),flush=True)
sys.stdin.readline()
source=ast.parse((Path(sys.argv[1])/'controlled_supervise.py').read_bytes())
function=next(node for node in source.body if isinstance(node,ast.FunctionDef) and node.name=='main')
statement=next(node for node in function.body if isinstance(node,ast.Try) and node.finalbody)
scope={
 'reason':'owned_stop_request','actors':{'worker':object()},'processes':{},
 'actor_receipts':{'worker':{}},'current_lease':None,'stop_receipts':[],
 'job':job,'__builtins__':__builtins__,
}
def stop_actor(*args):
 raise OwnershipError('review owned actor ownership failure')
def write(name,value):
 (Path(sys.argv[2])/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8')
scope['stop_actor']=stop_actor
scope['write']=write
code=compile(ast.fix_missing_locations(ast.Module(body=statement.finalbody,type_ignores=[])),'frozen_supervisor_finally_fixture','exec')
exec(code,scope)
raise RuntimeError('whole Job should terminate this process before observer final read')
'''


def main():
    job = review.OwnedJob()
    target = RUN / "recheck_44c9415" / "whole_job_fixture"
    target.mkdir()
    started, clock = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(), time.monotonic()
    process = subprocess.Popen([sys.executable, "-B", "-c", CHILD, str(PREP), str(target)],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, creationflags=0x08000000)
    ready = json.loads(process.stdout.readline())
    handles = []
    try:
        tree = review.windows_actor.process_tree()
        selected = {ready["identity"]["actual_pid"]}
        while additions := {pid for pid, row in tree.items() if row["parent"] in selected} - selected:
            selected.update(additions)
        for pid in selected:
            kernel, handle = review.kernel_process_handle(pid)
            handles.append((pid, kernel, handle))
        process.stdin.write("go\n")
        process.stdin.flush()
        process.wait(timeout=5)
        states = [{"pid": pid, "exit_confirmed_by_preheld_handle": kernel.WaitForSingleObject(handle, 1000) == 0}
                  for pid, kernel, handle in handles]
        failure = json.loads((target / "owned_stop_failure.json").read_bytes())
        result = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                  "seconds": time.monotonic() - clock, "launcher_exit_code": process.returncode,
                  "identity": ready["identity"], "all_owned_handles": states,
                  "failure_receipt": failure, "observer_terminal_request_created": (target / "collector_stop.request").exists(),
                  "passed": process.returncode == 70 and all(row["exit_confirmed_by_preheld_handle"] for row in states)
                            and failure["observer_terminal_guaranteed"] is False,
                  "scope": "exact frozen AST finally block, injected OwnershipError, real nested OwnedJob termination; no application startup",
                  "source_http_count": 0, "product_pg_count": 0, "usage": job.usage()}
        (RUN / "recheck_44c9415/whole_job_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        if not result["passed"]:
            raise AssertionError("whole owned Job did not fail closed")
    finally:
        for _, kernel, handle in handles:
            if kernel.WaitForSingleObject(handle, 0) != 0:
                if not kernel.TerminateProcess(handle, 70) and kernel.WaitForSingleObject(handle, 1000) != 0:
                    raise RuntimeError("owned review cleanup rejected")
                if kernel.WaitForSingleObject(handle, 1000) != 0:
                    raise RuntimeError("owned review cleanup not confirmed")
            kernel.CloseHandle(handle)
        process.stdin.close()
        process.stdout.close()
        process.stderr.close()


if __name__ == "__main__":
    main()
