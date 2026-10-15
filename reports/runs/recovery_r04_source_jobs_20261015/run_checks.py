"""本轮隔离库与命令收据；不接触旧审查库或共享 coverage 文件。"""

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    label, group = sys.argv[1:]
    if not re.fullmatch("[a-z0-9_]{1,60}", label) or group not in {"jobs", "api", "unit", "static"}:
        raise ValueError("invalid run label or group")
    receipt_path = RUN / (label + ".command.json")
    if receipt_path.exists():
        raise FileExistsError("run label already recorded")
    source = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"],
        capture_output=True, text=True, check=True, timeout=10)
    root_url = make_url(json.loads(source.stdout)["TEST_DATABASE_URL"])
    if root_url.host != "127.0.0.1" or root_url.port != 25432 or root_url.database != "test_dianzi_r01_20261014":
        raise ValueError("unexpected root isolated database")
    run_id = "r04_api_20261015" if group == "api" else "r04_source_jobs_20261015"
    database_name = "test_dianzi_" + run_id
    admin = create_engine(root_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        if connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database_name}) is None:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
    admin.dispose()
    database_url = root_url.set(database=database_name).render_as_string(hide_password=False)
    environment = dict(os.environ)
    coverage_path = Path(os.environ["TEMP"]) / "dianzi-recovery-coverage" / (label + ".coverage")
    coverage_path.parent.mkdir(exist_ok=True)
    environment.update(TEST_DATABASE_URL=database_url, DIANZI_TEST_RUN_ID=run_id,
        PYTHONUTF8="1", PYTHONIOENCODING="utf-8", COVERAGE_FILE=str(coverage_path))
    if group == "static":
        commands = [["uv", "run", "--locked", "ruff", "check", "src", "tests/unit/test_r04_source_jobs.py", "tests/integration/test_r04_source_jobs_pg.py", "tests/integration/test_r04_api_review_regressions.py"],
            ["uv", "run", "--locked", "mypy", "src"]]
    else:
        targets = {"jobs": ["tests/unit", "tests/integration/test_r04_source_jobs_pg.py"],
            "unit": ["tests/unit"],
            "api": ["tests/integration/test_r04_knowledge_api_pg.py", "tests/integration/test_r04_api_review_regressions.py"]}[group]
        commands = [["uv", "run", "--locked", "pytest", *targets,
            "-q", f"--junitxml={RUN / (label + '.xml')}",
            f"--cov-report=json:{RUN / (label + '.coverage.json')}"]]
        if group == "api":
            commands[0] += ["--no-cov"]
    receipts = []
    for index, command in enumerate(commands):
        started = now()
        result = subprocess.run(command, cwd=ROOT / "backend", env=environment,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=240)
        output = result.stdout + result.stderr
        for secret in (database_url, unquote(root_url.password or "")):
            if secret:
                output = output.replace(secret, "[REDACTED]")
        suffix = "" if len(commands) == 1 else "_" + str(index + 1)
        (RUN / (label + suffix + ".log")).write_text(output, encoding="utf-8")
        receipts.append({"command": command, "cwd": str(ROOT / "backend"), "started_at": started,
            "ended_at": now(), "exit_code": result.returncode})
        print(output[-1300:])
    xml_path = RUN / (label + ".xml")
    counts = None
    if xml_path.exists():
        suites = ElementTree.parse(xml_path).getroot()
        counts = {name: sum(int(suite.get(name, 0)) for suite in suites.iter("testsuite"))
            for name in ("tests", "failures", "errors", "skipped")}
    receipt = {"recorded_at": now(), "commands": receipts, "counts": counts,
        "database_scope": database_name, "other_database_migrated": False,
        "coverage_file": str(coverage_path), "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "working_diff_sha256": hashlib.sha256(subprocess.check_output(["git", "diff", "--binary"], cwd=ROOT)).hexdigest(),
        "source_state": "root uncommitted source-jobs/API fix; this receipt is not fixed-SHA acceptance"}
    receipt_path.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    return max(item["exit_code"] for item in receipts)


if __name__ == "__main__":
    raise SystemExit(main())
