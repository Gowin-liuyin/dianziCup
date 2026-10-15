"""只启动冻结前端的本地开发服务，30分钟/384MiB Node heap/日志上限。"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
RUN = Path(__file__).resolve().parent / "frontend_live_8f6bd9"
RUN.mkdir(exist_ok=False)
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip() == "8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce"
environment = dict(os.environ, API_PROXY_TARGET="http://127.0.0.1:28000")
command = ["node", "--max-old-space-size=384", str(ROOT / "frontend/node_modules/vite/bin/vite.js"), "--host", "127.0.0.1", "--port", "25300", "--strictPort"]
clock = ZoneInfo("Asia/Shanghai")
started = datetime.now(clock).isoformat(timespec="seconds")
with (RUN / "vite.log").open("wb") as output:
    process = subprocess.Popen(command, cwd=ROOT / "frontend", env=environment,
        stdout=output, stderr=subprocess.STDOUT, creationflags=0x08000000)
    (RUN / "start.json").write_text(json.dumps({"started_at": started, "pid": process.pid,
        "command": command, "code_sha": "8f6bd9f62b4bfb91c61ba47caaa7d6414fe6ecce", "maximum_seconds": 900}, indent=2))
    deadline = time.monotonic() + 900
    try:
        while process.poll() is None and time.monotonic() < deadline:
            if (RUN / "stop.request").exists() or (RUN / "vite.log").stat().st_size > 4 * 1024 * 1024:
                break
            time.sleep(0.5)
    finally:
        if process.poll() is None:
            process.terminate()
        process.wait(timeout=10)
        (RUN / "end.json").write_text(json.dumps({"started_at": started, "ended_at": datetime.now(clock).isoformat(timespec="seconds"), "exit_code": process.returncode}, indent=2))
