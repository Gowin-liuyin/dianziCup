"""A main PID exit cannot by itself prove all owned descendant handles exited."""

import json
from pathlib import Path
import subprocess
import sys
import time
from datetime import datetime
from zoneinfo import ZoneInfo

import review_driver as review


def main():
    job = review.OwnedJob()
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat()
    process = subprocess.Popen([sys.executable, "-B", "-c", review.IDENTITY],
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                               creationflags=0x08000000)
    identity = json.loads(process.stdout.readline())
    actor = review.windows_actor.WindowsOwnedActor(identity["pid"], identity["ticks"], process.pid)
    handles = []
    try:
        tree = review.windows_actor.process_tree()
        selected = {identity["pid"]}
        while additions := {pid for pid, row in tree.items() if row["parent"] in selected} - selected:
            selected.update(additions)
        for pid in selected - {identity["pid"]}:
            kernel, handle = review.kernel_process_handle(pid)
            handles.append((pid, kernel, handle))
        assert actor.kernel.TerminateProcess(actor.handle, 70)
        assert actor.kernel.WaitForSingleObject(actor.handle, 1000) == 0
        actor.kill_owned_tree()
        descendants = [{"pid": pid, "exit_confirmed": kernel.WaitForSingleObject(handle, 0) == 0}
                       for pid, kernel, handle in handles]
        result = {"started_at": started, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                  "actual_pid": identity["pid"], "creation_ticks": identity["ticks"],
                  "main_exit_confirmed_before_call": True, "kill_tree_returned_without_error": True,
                  "descendants": descendants, "bug_reproduced": any(not row["exit_confirmed"] for row in descendants),
                  "scope": "verified owned actor handle exited before kill_owned_tree call; all real descendant handles prebound",
                  "source_http_count": 0, "usage": job.usage()}
        output_name = sys.argv[1] if len(sys.argv) > 1 else "already_exited_actor_results.json"
        (Path(__file__).resolve().parent / output_name).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        for _, kernel, handle in handles:
            if kernel.WaitForSingleObject(handle, 0) != 0:
                if not kernel.TerminateProcess(handle, 70):
                    assert kernel.WaitForSingleObject(handle, 1000) == 0
                assert kernel.WaitForSingleObject(handle, 1000) == 0
            kernel.CloseHandle(handle)
        actor.close()
        process.wait(timeout=3)
        process.stdout.close()
        process.stderr.close()


if __name__ == "__main__":
    main()
