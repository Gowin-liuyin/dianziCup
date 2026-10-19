"""Run bounded isolated repair checks with standalone command receipts."""
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo
import json
import os
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FRONTEND = ROOT / "frontend"
SOURCE = "592b49d6920a4b25db094212eab1d74ca964b1c2"
MATERIAL = "6472d816471a8c8ff176745d199ae4a3ef73270f"
PORT = 25321

def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")

def receipt(record):
    record.update(source_commit=SOURCE, material_commit=MATERIAL)
    (RUN / f"{record['label']}.command.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as output:
        output.write(json.dumps(record, ensure_ascii=False) + "\n")
    print(json.dumps(record, ensure_ascii=False))

def run(label, cwd, argv):
    start = now()
    environment = dict(os.environ)
    environment["PLAYWRIGHT_BROWSERS_PATH"] = "C:/Users/yinha/.codex/cache/dianzi/r01_playwright_1248"
    result = subprocess.run(argv, cwd=cwd, env=environment, capture_output=True, check=False, timeout=120)
    (RUN / f"{label}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{label}.stderr.log").write_bytes(result.stderr)
    receipt(dict(label=label, cwd=str(cwd), argv=argv, start=start, end=now(), exit_code=result.returncode))
    print(result.stdout.decode("utf-8", errors="replace")[-1000:])
    return result.returncode

def listening():
    with socket.socket() as probe:
        probe.settimeout(.2)
        return probe.connect_ex(("127.0.0.1", PORT)) == 0

def browser(label):
    assert not listening(), "Dedicated port occupied"
    argv = ["node", "node_modules/vite/bin/vite.js", "--host", "127.0.0.1", "--port", str(PORT), "--strictPort"]
    started = now()
    with (RUN / f"{label}.vite.log").open("wb") as output:
        server = subprocess.Popen(argv, cwd=FRONTEND, stdout=output, stderr=subprocess.STDOUT)
        try:
            deadline = time.monotonic() + 30
            while not listening():
                assert server.poll() is None and time.monotonic() < deadline
                time.sleep(.2)
            receipt(dict(label=f"{label}-controlledserve-start", cwd=str(FRONTEND), argv=argv, start=started, end=now(), exit_code=0, pid=server.pid, port=PORT, listener_before=False, listener_ready=True))
            code = run(label, FRONTEND, ["node", "node_modules/@playwright/test/cli.js", "test", "--config", str(RUN / f"{label}.config.mjs")])
        finally:
            server.terminate()
            server.wait(timeout=10)
            receipt(dict(label=f"{label}-controlledserve-end", cwd=str(FRONTEND), argv=["terminate_owned_vite", str(server.pid)], start=now(), end=now(), exit_code=0 if not listening() else 1, pid=server.pid, process_exit_code=server.returncode, listener_after=listening()))
    return code

CHECKS = {
    "events-tests": (FRONTEND, ["npm.cmd", "run", "test", "--", "--run", "src/features/events/event-detail-view.test.tsx", "src/features/events/event-workspace.test.tsx", "--maxWorkers=1", "--no-file-parallelism", "--reporter=json", f"--outputFile={RUN / 'events-tests.json'}"]),
    "typecheck": (FRONTEND, ["npm.cmd", "run", "typecheck"]),
    "lint": (FRONTEND, ["npm.cmd", "run", "lint"]),
    "build": (FRONTEND, ["npm.cmd", "run", "build"]),
    "source-diff-check": (ROOT, ["git", "diff", "--check", "e594cbbcaf82a0ccc36fc0b1cd9f4988da330127", SOURCE]),
    "material-diff-check": (ROOT, ["git", "diff", "--check", SOURCE, MATERIAL]),
    "author-manifest-audit": (ROOT, ["python", str(RUN / "audit_author.py")]),
}
sys.stdout.reconfigure(encoding="utf-8")
label = sys.argv[1]
sys.exit(browser(label) if label.startswith("browser") else run(label, *CHECKS[label]))
