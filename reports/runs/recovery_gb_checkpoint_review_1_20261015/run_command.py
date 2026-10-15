from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

RUN = Path(__file__).resolve().parent

def now() -> str:
    return datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat(timespec="seconds")

def run(label: str, cwd: str, argv: list[str], environment: dict[str, str] | None = None) -> int:
    started = now()
    env = os.environ.copy() if environment is None else environment
    checked_root = str(Path(cwd).resolve())
    checked_root = checked_root if (Path(checked_root) / 'backend').exists() else str(Path(checked_root).parent)
    env["PYTHONPATH"] = str(Path(checked_root) / 'backend/src') + os.pathsep + env.get("PYTHONPATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    with (RUN / f"{label}.log").open("w", encoding="utf-8") as output:
        result = subprocess.run(argv, cwd=cwd, env=env, stdout=output, stderr=subprocess.STDOUT, check=False)
    sha = subprocess.check_output(['git','rev-parse','HEAD'],cwd=cwd,text=True).strip()
    record = {"label": label, "argv": argv, "cwd": cwd, "started_at": started, "ended_at": now(), "exit_code": result.returncode, "sha": sha}
    (RUN / f"{label}.command.json").write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(record, ensure_ascii=False))
    return result.returncode

if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1], sys.argv[2], sys.argv[3:]))
