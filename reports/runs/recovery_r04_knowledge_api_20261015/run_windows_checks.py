"""冻结前Windows锁环境验证，保存准确时点和退出码。"""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def timestamp():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    name = sys.argv[1]
    command = sys.argv[2:]
    started = timestamp()
    result = subprocess.run(command, cwd=ROOT / "backend", stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
    ended = timestamp()
    (RUN / (name+".log")).write_text(result.stdout, encoding="utf-8")
    receipt = {"started_at": started, "ended_at": ended, "timezone": "Asia/Shanghai",
               "cwd": str(ROOT / "backend"), "command": command, "exit_code": result.returncode,
               "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "source_tree": "working tree, not frozen", "test_mode": "isolated unit / static"}
    (RUN / (name+".receipt.json")).write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    print(result.stdout[-5000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
