"""Record fixture-only commands and their original output without reading secrets."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
LOCAL_TIME = timezone(timedelta(hours=8))
ENVIRONMENT_KEYS = (
    "PATH",
    "SYSTEMROOT",
    "WINDIR",
    "TEMP",
    "TMP",
    "COMSPEC",
    "PATHEXT",
    "USERPROFILE",
    "APPDATA",
    "LOCALAPPDATA",
)


def main() -> int:
    """Run an argv in a controlled environment and preserve its exit code."""
    label, working_directory, *command = sys.argv[1:]
    environment = {key: os.environ[key] for key in ENVIRONMENT_KEYS if key in os.environ}
    environment.update(
        PYTHONPATH=os.pathsep.join((str(ROOT / "backend/src"), str(ROOT / "backend/tests"))),
        PYTHONIOENCODING="utf-8",
        PYTHONDONTWRITEBYTECODE="1",
        DATA_MODE="fixture",
    )
    started_at = datetime.now(LOCAL_TIME).isoformat()
    with (
        (RUN / f"{label}.stdout.log").open("wb") as stdout,
        (RUN / f"{label}.stderr.log").open("wb") as stderr,
    ):
        result = subprocess.run(
            command,
            cwd=working_directory,
            env=environment,
            stdout=stdout,
            stderr=stderr,
            check=False,
        )
    receipt = {
        "command": command,
        "cwd": working_directory,
        "started_at": started_at,
        "finished_at": datetime.now(LOCAL_TIME).isoformat(),
        "exit_code": result.returncode,
        "stdout": f"{label}.stdout.log",
        "stderr": f"{label}.stderr.log",
        "pythonpath": environment["PYTHONPATH"],
        "environment_policy": "standard runtime keys only; DATA_MODE=fixture; no secrets",
        "evidence_class": "author_local_fixture_combination",
    }
    (RUN / f"{label}.command.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print(json.dumps({"label": label, "exit_code": result.returncode}, ensure_ascii=False))
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
