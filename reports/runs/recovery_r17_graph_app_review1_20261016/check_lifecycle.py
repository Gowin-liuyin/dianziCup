"""Observe only this review's process descendants and verify they exit."""

import datetime
import json
from pathlib import Path
import subprocess
import sys
import time

import psutil

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ZONE = datetime.timezone(datetime.timedelta(hours=8))


def main() -> None:
    observed = {}
    start = datetime.datetime.now(ZONE).isoformat(timespec="milliseconds")
    child = subprocess.Popen([sys.executable, str(RUN / "run_command.py"), "edge-independent-lifecycle",
        str(ROOT / "frontend"), "node", "node_modules/@playwright/test/cli.js", "test", "--config",
        str(RUN / "playwright.independent.config.mjs")], cwd=ROOT, creationflags=subprocess.CREATE_NO_WINDOW)
    while child.poll() is None:
        try:
            processes = [psutil.Process(child.pid), *psutil.Process(child.pid).children(recursive=True)]
            for process in processes:
                observed[(process.pid, process.create_time())] = {"pid": process.pid, "parent_pid": process.ppid(), "name": process.name(), "create_time": process.create_time()}
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
        time.sleep(0.2)
    time.sleep(0.5)
    for (pid, created), row in observed.items():
        try:
            current = psutil.Process(pid)
            row["still_running"] = current.create_time() == created and current.is_running()
        except psutil.NoSuchProcess:
            row["still_running"] = False
    listeners = [connection.laddr.port for connection in psutil.net_connections(kind="tcp")
        if connection.status == "LISTEN" and connection.laddr.port in [25619, 25620]]
    result = {"start": start, "end": datetime.datetime.now(ZONE).isoformat(timespec="milliseconds"),
        "exit_code": child.returncode, "observed": list(observed.values()), "survivors": [row for row in observed.values() if row["still_running"]],
        "review_port_listeners": listeners, "no_user_browser_attached": True}
    (RUN / "process-lifecycle.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result))
    if child.returncode != 0 or result["survivors"] or listeners:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
