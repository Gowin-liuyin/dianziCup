"""Run scoped receipts and scan PostgreSQL secrets and eight-character password fragments."""

import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy.engine import make_url

RUN = Path(__file__).resolve().parent
ZONE = ZoneInfo("Asia/Shanghai")


def now() -> str:
    return datetime.now(ZONE).isoformat(timespec="seconds")


def main() -> None:
    receipts = []
    for name, command in [
        ("resource_final", [sys.executable, str(RUN / "inspect_resource.py")]),
        ("probe_final", [sys.executable, str(RUN / "probe_existing.py")]),
        ("sql_final", [sys.executable, str(RUN / "verify_isolated.py")]),
        (
            "ruff_final",
            [sys.executable, "-m", "ruff", "check", "--config", "backend/pyproject.toml", str(RUN)],
        ),
        (
            "format_final",
            [
                sys.executable,
                "-m",
                "ruff",
                "format",
                "--check",
                "--config",
                "backend/pyproject.toml",
                str(RUN),
            ],
        ),
        ("diff_final", ["git", "diff", "--check"]),
    ]:
        started_at = now()
        completed = subprocess.run(command, capture_output=True, text=True, timeout=120)
        log_path = RUN / f"{name}.log"
        log_path.write_text(completed.stdout + completed.stderr, encoding="utf-8")
        receipts.append(
            {
                "name": name,
                "argv": command,
                "cwd": str(Path.cwd()),
                "started_at": started_at,
                "ended_at": now(),
                "exit_code": completed.returncode,
                "log": log_path.name,
            }
        )
        (RUN / "command_receipts.json").write_text(
            json.dumps(receipts, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
        assert completed.returncode == 0, f"check failed: {name}; inspect recorded log"
    secrets = []
    for secret_path in (
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json",
    ):
        secret_read = subprocess.run(
            ["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat", secret_path],
            capture_output=True,
            text=True,
            check=True,
            timeout=15,
        )
        database_url = json.loads(secret_read.stdout)["TEST_DATABASE_URL"]
        secrets.append(database_url)
        password = make_url(database_url).password
        assert password is not None and len(password) >= 8
        secrets.extend(password[offset : offset + 8] for offset in range(len(password) - 7))
    files = [path for path in RUN.iterdir() if path.is_file()]
    files.append(Path.cwd() / "reports/tasks/R05-pgvector-runtime.md")
    for path in files:
        content = path.read_text(encoding="utf-8")
        assert all(value not in content for value in secrets), f"secret scan failed: {path.name}"
    staged_names = subprocess.run(
        ["git", "diff", "--cached", "--name-only"],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.splitlines()
    for name in staged_names:
        assert name == "reports/tasks/R05-pgvector-runtime.md" or name.startswith(
            "reports/runs/recovery_r05_pgvector_runtime_20261015/"
        ), "staging scope exceeded"
        content = subprocess.run(
            ["git", "show", f":{name}"],
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=True,
            timeout=15,
        ).stdout
        assert all(value not in content for value in secrets), f"staged secret scan failed: {name}"
    for path in RUN.glob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
    result = {
        "completed_at": now(),
        "exit_code": 0,
        "secret_scan_files": len(files),
        "secret_fragment_length": 8,
        "secret_findings": 0,
        "staged_secret_scan_files": len(staged_names),
        "syntax_checked_scripts": len(list(RUN.glob("*.py"))),
        "commands_passed": len(receipts),
    }
    (RUN / "final_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result))


if __name__ == "__main__":
    main()
