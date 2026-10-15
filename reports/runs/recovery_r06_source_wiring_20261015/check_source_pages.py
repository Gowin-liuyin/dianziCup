"""Record current-worktree source checks with original gates and no live credentials."""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

root = Path(__file__).resolve().parents[3]
run = Path(__file__).resolve().parent
label, mode = sys.argv[1:]
commands = {
    "focused": [
        "pytest",
        "tests/unit/test_r06_catalog_pages.py",
        "tests/unit/test_r06_source_catalog.py",
        "--no-cov",
        "-q",
    ],
    "pure": [
        "pytest",
        "tests/unit",
        "tests/contract",
        "tests/security",
        "-m",
        "not real_pg",
        "-q",
    ],
    "ruff": ["ruff", "check", "src", "tests/unit/test_r06_catalog_pages.py"],
    "mypy": ["mypy", "src"],
}
argv = [str(root / "backend/.venv/Scripts/python.exe"), "-m", *commands[mode]]
if mode in {"focused", "pure"}:
    argv.append("--junitxml=" + str(run / (label + ".xml")))
environment = dict(
    os.environ, PYTHONPATH=str(root / "backend/src"), PYTHONIOENCODING="utf-8"
)
for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
    environment.pop(name, None)
started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
with (run / (label + ".log")).open("wb") as output:
    result = subprocess.run(
        argv,
        cwd=root / "backend",
        env=environment,
        stdout=output,
        stderr=subprocess.STDOUT,
        timeout=600,
        check=False,
    )
(run / (label + ".json")).write_text(
    json.dumps(
        {
            "argv": argv,
            "cwd": str(root / "backend"),
            "started_at": started,
            "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
                timespec="seconds"
            ),
            "exit_code": result.returncode,
            "head": subprocess.check_output(
                ["git", "rev-parse", "HEAD"], cwd=root, text=True
            ).strip(),
            "scope": "source offline normalization tests only; product worker/PG/UI not yet wired",
        },
        indent=2,
    )
    + "\n",
    encoding="utf-8",
)
print(json.dumps({"label": label, "exit_code": result.returncode}))
raise SystemExit(result.returncode)
