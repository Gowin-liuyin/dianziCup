"""Record fixed recheck commands without modifying implementation or earlier evidence."""

from datetime import datetime, timezone, timedelta
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
PYTHON = Path("C:/Users/yinha/.codex/worktrees/r11-version-ranges-review1/dianzi/backend/.venv/Scripts/python.exe")
CBM = ["wsl.exe", "-e", "/tmp/dianzi-cbm-audit-20261014/portable/codebase-memory-mcp", "cli", "--json"]


if __name__ == "__main__":
    label = sys.argv[1]
    cwd = BACKEND if sys.argv[2] == "backend" else ROOT
    executable = sys.argv[3]
    command = ([str(PYTHON)] if executable == "python" else CBM if executable == "cbm" else [executable]) + sys.argv[4:]
    start = datetime.now(timezone(timedelta(hours=8))).isoformat()
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(BACKEND / "src")
    with (RUN / f"{label}.stdout.log").open("wb") as stdout, (RUN / f"{label}.stderr.log").open("wb") as stderr:
        result = subprocess.run(command, cwd=cwd, env=environment, stdout=stdout, stderr=stderr, check=False)
    receipt = {"argv": command, "cwd": str(cwd), "started_at": start, "ended_at": datetime.now(timezone(timedelta(hours=8))).isoformat(), "exit_code": result.returncode, "material_sha": "8f5fe818774349b41b0b5aceb45d69ba81410678", "code_sha": "71e724131daf4d03372392d58cd17c764c3e2e40", "source_fix_sha": "65838b42c0dcff863036968e39a1404aa323b3c9", "pythonpath": environment["PYTHONPATH"]}
    (RUN / f"{label}.receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
