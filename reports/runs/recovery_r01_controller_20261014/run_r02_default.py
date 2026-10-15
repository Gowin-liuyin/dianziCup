"""有限R02复跑，私有连接只进环境，输出保留失败计数并精确脱敏。"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def timestamp() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> int:
    """只访问已授权的独立R02auth库，不启停共享服务。"""
    private = subprocess.run(
        ["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
         "/tmp/dianzi-r02_auth_20261015/connection.json"],
        check=True, capture_output=True, text=True, timeout=10,
    )
    configuration = json.loads(private.stdout)
    label = sys.argv[1] if len(sys.argv) > 1 else "r02_default_auth_resume"
    if re.fullmatch(r"[a-z0-9_]{1,80}", label) is None:
        raise ValueError("invalid evidence label")
    if any((RUN / f"{label}{suffix}").exists() for suffix in (".xml", ".log", ".command.json")):
        raise FileExistsError("evidence label already exists; choose a new label")
    database_url = configuration["TEST_DATABASE_URL"]
    environment = dict(os.environ)
    environment.update(TEST_DATABASE_URL=database_url, DIANZI_TEST_RUN_ID="r02_auth_20261015",
                       PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    command = ["uv", "run", "--locked", "pytest", "tests/unit",
               "tests/security/test_r02_default_auth_failure.py",
               "tests/integration/test_r02_default_application.py",
               "tests/integration/test_r02_schema_migration.py",
               "tests/integration/test_r02_auth_state.py",
               f"--junitxml={RUN / (label + '.xml')}", "-q"]
    started = timestamp()
    completed = subprocess.run(command, cwd=ROOT / "backend", env=environment,
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=240)
    output = completed.stdout + completed.stderr
    password = unquote(urlsplit(database_url).password or "")
    for secret in (database_url, password):
        if secret:
            output = output.replace(secret, "[redacted test credential]")
    (RUN / f"{label}.log").write_text(output, encoding="utf-8")
    receipt = {"started_at": started, "ended_at": timestamp(), "command": command,
               "cwd": str(ROOT / "backend"), "exit_code": completed.returncode,
               "parent_sha": subprocess.check_output(
                   ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
               "database_scope": "r02_auth_20261015",
               "scope": "full unit + default PG factory + forward0009 + independent-process auth cases"}
    (RUN / f"{label}.command.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(receipt, ensure_ascii=False))
    print(output[-1400:])
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
