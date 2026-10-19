"""Keep actual bounded offline validation logs separate from product live evidence."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
COMMANDS = (
    (
        "public_fix_contract",
        [
            "-m",
            "pytest",
            "backend/tests/contract/test_r18_public_extensions.py",
            "backend/tests/contract/test_r18_task_poll_uri.py",
            "--no-cov",
            "-q",
        ],
    ),
    (
        "projection_unit",
        [
            "-m",
            "pytest",
            "backend/tests/unit/test_r12_default_projection_runtime.py",
            "backend/tests/unit/test_r01_worker_configuration.py",
            "backend/tests/unit/test_r01_runtime_settings.py",
            "--no-cov",
            "-q",
        ],
    ),
    (
        "style",
        [
            "-m",
            "ruff",
            "check",
            "backend/src/ai_intel/retrieval/runtime_policy.py",
            "backend/src/ai_intel/retrieval/indexing.py",
            "backend/src/ai_intel/infrastructure/settings.py",
            "backend/src/ai_intel/workers/runtime.py",
            "backend/tests/unit/test_r12_default_projection_runtime.py",
            "backend/tests/contract/test_r18_task_poll_uri.py",
        ],
    ),
    (
        "types",
        [
            "-m",
            "mypy",
            "--config-file",
            "backend/pyproject.toml",
            "backend/src/ai_intel/retrieval/runtime_policy.py",
            "backend/src/ai_intel/retrieval/indexing.py",
            "backend/src/ai_intel/infrastructure/settings.py",
            "backend/src/ai_intel/workers/runtime.py",
        ],
    ),
)
records = []
for label, arguments in COMMANDS:
    if len(sys.argv) > 1:
        label = label + "_" + sys.argv[1]
    started = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
    result = subprocess.run(
        [sys.executable, *arguments],
        cwd=ROOT,
        capture_output=True,
        timeout=120,
        check=False,
    )
    (RUN / (label + ".stdout.log")).write_bytes(result.stdout)
    (RUN / (label + ".stderr.log")).write_bytes(result.stderr)
    records.append(
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
    manifest_name = (
        "commands" + ("_" + sys.argv[1] if len(sys.argv) > 1 else "") + ".json"
    )
    (RUN / manifest_name).write_text(
        json.dumps(records, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"label": label, "exit_code": result.returncode}), flush=True)
