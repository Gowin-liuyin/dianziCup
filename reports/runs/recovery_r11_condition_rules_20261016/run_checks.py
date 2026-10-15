"""Execute only this slice's offline checks and preserve command receipts/raw logs."""

import json
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BACKEND = ROOT / "backend"
RUN = Path(__file__).resolve().parent
ZONE = timezone(timedelta(hours=8))
UV = ["uv", "run", "--frozen", "--offline", "--all-extras"]
FILES = [
    "src/ai_intel/assessment/conditions.py", "src/ai_intel/assessment/rules.py",
    "tests/unit/test_t27_condition_rules.py", "tests/contract/test_r11_condition_schema.py",
    "tests/security/test_r11_condition_security.py",
]
RECEIPTS = json.loads((RUN / "commands.json").read_text(encoding="utf-8")) if (RUN / "commands.json").exists() else []
CHECKS = [
    ("replay_unit", [*UV, "python", "-m", "pytest", FILES[2], "-v", "--override-ini", "addopts=", "--junitxml=" + str(RUN / "replay_unit.xml")]),
    ("replay_contract", [*UV, "python", "-m", "pytest", FILES[3], "-v", "--override-ini", "addopts=", "--junitxml=" + str(RUN / "replay_contract.xml")]),
    ("replay_security", [*UV, "python", "-m", "pytest", FILES[4], "-v", "--override-ini", "addopts=", "--junitxml=" + str(RUN / "replay_security.xml")]),
    ("replay_full_unit", [*UV, "python", "-m", "pytest", "tests/unit", "-q", "--junitxml=" + str(RUN / "replay_full_unit.xml")]),
    ("replay_mypy", [*UV, "mypy", *FILES[:2]]),
    ("replay_ruff", [*UV, "ruff", "check", *FILES]),
    ("replay_format", [*UV, "ruff", "format", "--check", *FILES]),
]
CURRENT_EXITS = []
for label, command in CHECKS:
    started = datetime.now(ZONE).isoformat(timespec="seconds")
    result = subprocess.run(command, cwd=BACKEND, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    (RUN / f"{label}.log").write_bytes(result.stdout)
    receipt = dict(label=label, command=command, cwd=str(BACKEND), started_at=started,
                   completed_at=datetime.now(ZONE).isoformat(timespec="seconds"), exit_code=result.returncode,
                   log=str(RUN / f"{label}.log"))
    RECEIPTS.append(receipt)
    CURRENT_EXITS.append(result.returncode)
    (RUN / "commands.json").write_text(json.dumps(RECEIPTS, indent=2), encoding="utf-8")
    print(json.dumps(receipt), flush=True)
raise SystemExit(1 if any(CURRENT_EXITS) else 0)
