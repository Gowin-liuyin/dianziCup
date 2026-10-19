"""Check stop receipts emitted by real disposable worker and beat interpreters."""

import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
PREP = RUN.parent / "recovery_r06_live_restart_preparation_20261016"
sys.path.insert(0, str(PREP))
import stop_controller
from runtime_limits import OwnedJob
from windows_actor import WindowsOwnedActor


def main():
    job = OwnedJob()
    started = datetime.now(ZoneInfo("Asia/Shanghai"))
    fixtures = RUN / "actual_ack_fixture"
    fixtures.mkdir()
    shutil.copyfile(PREP / "owned_stop_watcher.py", fixtures / "owned_stop_watcher.py")
    specification = importlib.util.spec_from_file_location("review_watch", fixtures / "owned_stop_watcher.py")
    watcher = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(watcher)
    processes, actors, receipts = {}, {}, []
    try:
        for role in ("worker", "beat"):
            code = (
                "import sys,time\n"
                f"sys.path.insert(0,{str(fixtures)!r})\n"
                "from owned_stop_watcher import install_owned_stop_watcher\n"
                f"install_owned_stop_watcher({role!r})\n"
            )
            if role == "worker":
                code += (
                    "from celery.worker import state\n"
                    "from celery.exceptions import WorkerShutdown\n"
                    "try:\n"
                    " while True:\n"
                    "  state.maybe_shutdown()\n"
                    "  time.sleep(0.01)\n"
                    "except WorkerShutdown:\n"
                    " pass\n"
                )
            else:
                code += "time.sleep(30)\n"
            processes[role] = subprocess.Popen([sys.executable, "-B", "-c", code],
                                               stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                               creationflags=0x08000000)
        with patch.object(stop_controller, "owned_control_path", watcher.owned_control_path):
            for role in ("worker", "beat"):
                ready_path = watcher.owned_control_path(role, "ready")
                deadline = time.monotonic() + 5
                while not ready_path.exists():
                    if time.monotonic() >= deadline or processes[role].poll() is not None:
                        raise RuntimeError("review-owned synthetic actor did not become ready")
                    time.sleep(0.01)
                ready = stop_controller.read_actor_receipt(role, "ready")
                actors[role] = WindowsOwnedActor(ready["actual_pid"], ready["creation_ticks"], processes[role].pid)
                receipt = stop_controller.stop_actor(role, actors[role], ready,
                                                    datetime.now(UTC) + timedelta(seconds=60), False)
                processes[role].wait(timeout=3)
                acknowledgement = stop_controller.read_actor_receipt(role, "ack")
                receipt["launcher_pid"] = processes[role].pid
                receipt["launcher_exit_code"] = processes[role].returncode
                receipt["actual_acknowledgement"] = acknowledgement
                receipt["identity_match"] = all(ready[key] == acknowledgement[key] for key in ("actual_pid", "creation_ticks"))
                receipts.append(receipt)
        result = {"started_at": started.isoformat(),
                  "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(),
                  "receipts": receipts, "usage": job.usage(), "source_http_count": 0,
                  "scope": "synthetic actor loop and real stop watcher; no Celery broker or source consumer"}
        (RUN / "actual_ack_results.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
    finally:
        for actor in actors.values():
            if not actor.exited():
                actor.kill_owned_tree()
            actor.close()
        for process in processes.values():
            process.wait(timeout=3)
            process.stdout.close()
            process.stderr.close()


if __name__ == "__main__":
    main()
