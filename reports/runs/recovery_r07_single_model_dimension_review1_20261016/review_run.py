"""Record bounded independent review commands without importing product secrets."""

import datetime
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def run(label, argv, cwd=None, extra_env=None):
    receipt = RUN / f"{label}.command.json"
    if receipt.exists():
        raise RuntimeError(f"refusing to overwrite {label}")
    environment = os.environ.copy()
    environment["PYTHONPATH"] = str(ROOT / "backend/src")
    environment.update(extra_env or {})
    started = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    result = subprocess.run(argv, cwd=cwd or ROOT, env=environment, capture_output=True)
    ended = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).isoformat()
    (RUN / f"{label}.stdout.log").write_bytes(result.stdout)
    (RUN / f"{label}.stderr.log").write_bytes(result.stderr)
    receipt.write_text(json.dumps({"argv": argv, "cwd": str(cwd or ROOT),
        "started_at_shanghai": started, "ended_at_shanghai": ended,
        "exit_code": result.returncode, "material_sha": "b05e63462f1b513eabc183d0a8d42b03196696d2",
        "code_sha": "d8a3189bb7bc1cfde24825f5478920e37eac9556",
        "pythonpath": environment["PYTHONPATH"]}, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
    print(f"{label}: exit={result.returncode}")
    print(result.stdout.decode("utf-8", errors="replace")[-3500:])
    print(result.stderr.decode("utf-8", errors="replace")[-1000:])
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(run(sys.argv[1], sys.argv[2:]))
