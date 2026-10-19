"""Record bounded commands and real Asia/Shanghai timestamps without model credentials."""

import json
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
ZONE = timezone(timedelta(hours=8))


def main() -> int:
    name, relative_cwd, *command = sys.argv[1:]
    started = datetime.now(ZONE).isoformat(timespec="seconds")
    result = subprocess.run(command, cwd=ROOT / relative_cwd, capture_output=True, timeout=300)
    (RUN / f"{name}.log").write_bytes(result.stdout + result.stderr)
    receipt = {"command": command, "cwd": str(ROOT / relative_cwd), "started_at": started,
               "finished_at": datetime.now(ZONE).isoformat(timespec="seconds"),
               "exit_code": result.returncode, "log": f"{name}.log"}
    (RUN / f"{name}.command.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
