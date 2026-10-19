"""Record scoped schema validation separately from the whole-repository coverage gate."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
TEST = "backend/tests/contract/test_r18_public_extensions.py"
commands = []


def execute(label, arguments):
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(
        [sys.executable, *arguments], cwd=ROOT, capture_output=True, check=False
    )
    (RUN / (label + ".stdout.log")).write_bytes(result.stdout)
    (RUN / (label + ".stderr.log")).write_bytes(result.stderr)
    commands.append(
        {
            "label": label,
            "argv": [sys.executable, *arguments],
            "cwd": str(ROOT),
            "started_at": started,
            "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(
                timespec="seconds"
            ),
            "exit_code": result.returncode,
        }
    )
    (RUN / "commands.json").write_text(
        json.dumps(commands, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
    return result.returncode


execute(
    "whole_coverage_scope_mismatch",
    [
        "-m",
        "pytest",
        TEST,
        "-q",
        "--junitxml=" + str(RUN / "whole_coverage_scope_mismatch.xml"),
    ],
)
execute("initial_style", ["-m", "ruff", "check", TEST])
assert (
    execute(
        "format",
        [
            "-m",
            "ruff",
            "format",
            TEST,
            str(RUN / "freeze_extensions.py"),
            str(RUN / "run_checks.py"),
        ],
    )
    == 0
)
assert (
    execute(
        "contract_scoped",
        [
            "-m",
            "pytest",
            TEST,
            "--no-cov",
            "-q",
            "--junitxml=" + str(RUN / "contract_scoped.xml"),
        ],
    )
    == 0
)
assert (
    execute(
        "final_style",
        [
            "-m",
            "ruff",
            "check",
            TEST,
            str(RUN / "freeze_extensions.py"),
            str(RUN / "run_checks.py"),
        ],
    )
    == 0
)
assert (
    execute(
        "final_format",
        [
            "-m",
            "ruff",
            "format",
            "--check",
            TEST,
            str(RUN / "freeze_extensions.py"),
            str(RUN / "run_checks.py"),
        ],
    )
    == 0
)
