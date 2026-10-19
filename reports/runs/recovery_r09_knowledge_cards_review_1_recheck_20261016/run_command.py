"""独立固定组合复核：白名单环境、离线依赖和实际北京时间回执。"""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
ENVIRONMENT_NAMES = ("PATH", "SystemRoot", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "USERPROFILE", "LOCALAPPDATA", "APPDATA", "SYSTEMDRIVE", "PROGRAMFILES", "PROGRAMFILES(X86)", "PROGRAMDATA", "ALLUSERSPROFILE")


def record(label, cwd, command):
    environment = {name: os.environ[name] for name in ENVIRONMENT_NAMES if name in os.environ}
    environment.update({"PYTHONPATH": os.pathsep.join((str(ROOT / "backend/src"), str(ROOT / "backend/tests"), str(ROOT / "backend/tests/unit"))), "PYTHONUTF8": "1", "PYTHONDONTWRITEBYTECODE": "1", "DATA_MODE": "fixture", "RUFF_CACHE_DIR": str(RUN / "ruff_cache"), "UV_PROJECT_ENVIRONMENT": str(RUN / ".venv"), "UV_OFFLINE": "1", "PIP_NO_INDEX": "1"})
    started = datetime.now(timezone(timedelta(hours=8))).isoformat()
    result = subprocess.run(command, cwd=cwd, env=environment, capture_output=True, check=False)
    finished = datetime.now(timezone(timedelta(hours=8))).isoformat()
    (RUN / f"{label}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{label}.stderr.log").write_bytes(result.stderr)
    receipt = {"command": command, "cwd": str(cwd), "started_at": started, "finished_at": finished, "exit_code": result.returncode, "stdout": f"{label}.stdout.log", "stderr": f"{label}.stderr.log", "pythonpath": environment["PYTHONPATH"], "data_mode": "fixture", "offline": True}
    (RUN / f"{label}.command.json").write_bytes((json.dumps(receipt, ensure_ascii=False, indent=2) + "\n").encode())
    print(json.dumps(receipt, ensure_ascii=False))
    print(result.stdout.decode("utf-8", errors="replace"))
    print(result.stderr.decode("utf-8", errors="replace"))
    return result.returncode


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    raise SystemExit(record(sys.argv[1], ROOT / sys.argv[2], sys.argv[3:]))
