"""新维度库独立迁移；不升级正在被固定0009 reviewer使用的知识库。"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
RUN_ID = "r02_dimensions_20261015"


def now() -> str:
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main() -> int:
    label = sys.argv[1]
    if re.fullmatch(r"[a-z0-9_]{1,60}", label) is None:
        raise ValueError("invalid evidence label")
    if any((RUN / f"{label}{suffix}").exists() for suffix in (".xml", ".log", ".command.json")):
        raise FileExistsError("evidence label already used")
    source = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, text=True, check=True, timeout=10)
    root_url = make_url(json.loads(source.stdout)["TEST_DATABASE_URL"])
    if root_url.host != "127.0.0.1" or root_url.port != 25432 or root_url.database != "test_dianzi_r01_20261014":
        raise ValueError("unexpected root isolated database identity")
    database_name = "test_dianzi_" + RUN_ID
    engine = create_engine(root_url, isolation_level="AUTOCOMMIT")
    with engine.connect() as connection:
        if connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"),
                             {"name": database_name}) is None:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    engine.dispose()
    database_url = root_url.set(database=database_name).render_as_string(hide_password=False)
    private_path = f"/tmp/dianzi-{RUN_ID}/connection.json"
    save = subprocess.run(["wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-c",
        "import os,pathlib,sys;os.umask(0o077);p=pathlib.Path(sys.argv[1]);"
        "p.parent.mkdir(mode=0o700,exist_ok=True);p.write_text(sys.stdin.read());p.chmod(0o600)",
        private_path], input=json.dumps({"DIANZI_TEST_RUN_ID": RUN_ID, "TEST_DATABASE_URL": database_url}),
        capture_output=True, text=True, timeout=10)
    if save.returncode:
        raise RuntimeError("private configuration storage failed")
    environment = dict(os.environ)
    environment.update(TEST_DATABASE_URL=database_url, DIANZI_TEST_RUN_ID=RUN_ID,
                       PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    command = ["uv", "run", "--locked", "pytest", "tests/unit",
        "tests/integration/test_r02_dimension_persistence.py",
        "tests/integration/test_r02_dimension_migration.py",
        "tests/integration/test_r02_schema_migration.py", f"--junitxml={RUN / (label + '.xml')}", "-q"]
    started = now()
    completed = subprocess.run(command, cwd=ROOT / "backend", env=environment,
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    output = completed.stdout + completed.stderr
    password = unquote(root_url.password or "")
    for sensitive in (database_url, password):
        if sensitive:
            output = output.replace(sensitive, "[REDACTED]")
    (RUN / f"{label}.log").write_text(output, encoding="utf-8")
    receipt = {"started_at": started, "ended_at": now(), "exit_code": completed.returncode,
        "command": command, "cwd": str(ROOT / "backend"), "database_scope": RUN_ID,
        "parent_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_state": "uncommitted root dimension publication slice", "other_database_migrated": False}
    (RUN / f"{label}.command.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    print(output[-1600:])
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
