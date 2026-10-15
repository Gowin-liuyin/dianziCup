"""当前UI/skip与已授权Vitest安全修复的新集成回归，不复用旧30例结论。"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "reports/runs/recovery_r04_frontend_integrated_20261015"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> int:
    RUN.mkdir(exist_ok=False)
    commands = (
        ("ci", ["npm.cmd", "ci"]),
        ("audit", ["npm.cmd", "audit", "--json"]),
        ("lint", ["npm.cmd", "run", "lint"]),
        ("typecheck", ["npm.cmd", "run", "typecheck"]),
        ("test", ["npm.cmd", "run", "test", "--", "--reporter=junit",
                  "--outputFile=" + str(RUN / "tests.xml")]),
        ("build", ["npm.cmd", "run", "build"]),
    )
    failures = 0
    for label, command in commands:
        started = now()
        result = subprocess.run(command, cwd=ROOT / "frontend", capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=180)
        (RUN / f"{label}.stdout.log").write_text(result.stdout, encoding="utf-8")
        (RUN / f"{label}.stderr.log").write_text(result.stderr, encoding="utf-8")
        receipt = {"started_at": started, "ended_at": now(), "command": command,
                   "cwd": str(ROOT / "frontend"), "exit_code": result.returncode,
                   "source_state": "staged UI471 + reviewed skip + Vitest4.1.11 dependency pair"}
        (RUN / f"{label}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
        print(json.dumps(receipt), flush=True)
        failures += result.returncode != 0
        if label == "ci" and result.returncode:
            break
    return int(failures > 0)


if __name__ == "__main__":
    raise SystemExit(main())
