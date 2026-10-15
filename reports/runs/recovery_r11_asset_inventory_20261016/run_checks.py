"""隔离测试资源与真实命令收据；连接配置仅捕获到内存，不写stdout/argv。"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from ai_intel.assets.inventory_models import ASSET_TABLES
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.models import metadata
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

RUN_ROOT = Path(__file__).resolve().parent
ROOT = RUN_ROOT.parents[2]
RUN = RUN_ROOT / (sys.argv[1] if len(sys.argv) > 1 else "attempt_2")
RUN.mkdir(exist_ok=False)
BACKEND = ROOT / "backend"
PYTHON = BACKEND / ".venv/Scripts/python.exe"


def now():
    return datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")


def main():
    config_bytes = subprocess.check_output(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ]
    )
    config = json.loads(config_bytes)
    original_url = make_url(config["TEST_DATABASE_URL"])
    assert config["postgres_port"] == 25432
    suffix = datetime.now(ZoneInfo("Asia/Shanghai")).strftime("%Y%m%d_%H%M%S")
    run_id = "r11_inventory_" + suffix
    database = "test_dianzi_r11_inventory_" + suffix
    assert re.fullmatch(r"test_dianzi_r11_inventory_[0-9_]+", database)
    admin_url = original_url.set(
        drivername="postgresql+psycopg",
        host="127.0.0.1",
        port=25432,
        database="postgres",
    )
    admin = create_engine(admin_url, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        connection.execute(text('CREATE DATABASE "' + database + '"'))
    admin.dispose()
    url = admin_url.set(database=database, query={})
    started = now()
    run_migrations(
        url.render_as_string(hide_password=False), "0016_source_response_receipts"
    )
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        metadata.create_all(connection, tables=list(ASSET_TABLES))
    with engine.connect() as connection:
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        pg_version = connection.scalar(text("SHOW server_version"))
    engine.dispose()
    (RUN / "database_receipt.json").write_text(
        json.dumps(
            {
                "run_id": run_id,
                "database": database,
                "host": "127.0.0.1",
                "port": 25432,
                "started_at": started,
                "finished_at": now(),
                "postgres_version": pg_version,
                "base_migration": revision,
                "asset_tables_action": "create_tables_not_production_migration",
                "asset_tables": [table.name for table in ASSET_TABLES],
                "exit_code": 0,
                "cleanup": "not_deleted_no_downgrade",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    environment = {
        **os.environ,
        "TEST_DATABASE_URL": url.render_as_string(hide_password=False),
        "DIANZI_TEST_RUN_ID": run_id,
        "PYTHONPATH": str(BACKEND / "src"),
        "PYTHONIOENCODING": "utf-8",
    }
    secret = original_url.password or ""
    checks = [
        (
            "unit_contract_security",
            [
                "-m",
                "pytest",
                "tests/unit/test_r11_inventory.py",
                "tests/contract/test_r11_inventory_contracts.py",
                "tests/security/test_r11_inventory_boundary.py",
                "--no-cov",
                "-q",
            ],
        ),
        (
            "pg_inventory_api",
            [
                "-m",
                "pytest",
                "tests/integration/test_t24_asset_inventory.py",
                "--no-cov",
                "-q",
            ],
        ),
        (
            "parser_regression",
            [
                "-m",
                "pytest",
                "tests/unit/test_r11_manifest_parser.py",
                "tests/unit/test_r11_manifest_parser_identity_time.py",
                "tests/contract/test_r11_manifest_candidate.py",
                "tests/security/test_r11_manifest_parser_boundary.py",
                "--no-cov",
                "-q",
            ],
        ),
        (
            "related_regression",
            [
                "-m",
                "pytest",
                "tests/unit/test_t04_domain_contracts.py",
                "tests/unit/test_t06_access_scope_boundaries.py",
                "tests/unit/test_r02_auth_state_inputs.py",
                "tests/security/test_r02_auth_state_boundaries.py",
                "tests/contract/test_t07_jobs_outbox.py",
                "--no-cov",
                "-q",
            ],
        ),
        (
            "ruff",
            [
                "-m",
                "ruff",
                "check",
                "src/ai_intel/assets/inventory.py",
                "src/ai_intel/assets/inventory_models.py",
                "src/ai_intel/assets/inventory_contracts.py",
                "src/ai_intel/assets/inventory_routes.py",
                "tests/unit/test_r11_inventory.py",
                "tests/contract/test_r11_inventory_contracts.py",
                "tests/security/test_r11_inventory_boundary.py",
                "tests/integration/test_t24_asset_inventory.py",
            ],
        ),
        (
            "format",
            [
                "-m",
                "ruff",
                "format",
                "--check",
                "src/ai_intel/assets/inventory.py",
                "src/ai_intel/assets/inventory_models.py",
                "src/ai_intel/assets/inventory_contracts.py",
                "src/ai_intel/assets/inventory_routes.py",
                "tests/unit/test_r11_inventory.py",
                "tests/contract/test_r11_inventory_contracts.py",
                "tests/security/test_r11_inventory_boundary.py",
                "tests/integration/test_t24_asset_inventory.py",
            ],
        ),
        ("mypy", ["-m", "mypy", "src/ai_intel"]),
    ]
    receipts = []
    for label, args in checks:
        if "pytest" in args:
            args.append("--junitxml=" + str(RUN / (label + ".xml")))
        command = [str(PYTHON), *args]
        started = now()
        result = subprocess.run(
            command,
            cwd=BACKEND,
            env=environment,
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=180,
            check=False,
        )
        output = result.stdout + result.stderr
        if secret:
            output = output.replace(secret, "[redacted database credential]")
        output = output.replace(
            environment["TEST_DATABASE_URL"], "[redacted test connection]"
        )
        (RUN / (label + ".log")).write_text(output, encoding="utf-8")
        receipts.append(
            {
                "label": label,
                "argv": command,
                "cwd": str(BACKEND),
                "started_at": started,
                "finished_at": now(),
                "exit_code": result.returncode,
            }
        )
        (RUN / "commands.json").write_text(
            json.dumps(receipts, indent=2), encoding="utf-8"
        )
        print(
            json.dumps(
                {
                    "label": label,
                    "exit_code": result.returncode,
                    "summary": output.splitlines()[-1] if output else "",
                }
            ),
            flush=True,
        )
    return int(any(row["exit_code"] for row in receipts))


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (
        OSError,
        ValueError,
        AssertionError,
        SQLAlchemyError,
        subprocess.SubprocessError,
    ) as error:
        (RUN / "environment_failure.json").write_text(
            json.dumps(
                {
                    "type": type(error).__name__,
                    "occurred_at": now(),
                    "reason": "isolated resource setup failed; details withheld",
                }
            ),
            encoding="utf-8",
        )
        print("isolated resource setup failed: " + type(error).__name__)
        sys.exit(2)
