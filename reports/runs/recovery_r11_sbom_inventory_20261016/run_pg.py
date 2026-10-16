"""只读取批准连接到内存，在独占test数据库前向迁移；不写DSN或删除数据库。"""

import json
import os
import re
import subprocess
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

from run_checks import PYTHON, ROOT, RUN, run
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.infrastructure.database import run_migrations


def approved_url():
    result = subprocess.run(
        [
            "wsl.exe",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--exec",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        capture_output=True,
        check=True,
    )
    configured = json.loads(result.stdout)
    url = make_url(configured["TEST_DATABASE_URL"])
    if (
        url.host not in {"127.0.0.1", "localhost"}
        or url.port != 25432
        or not url.database
        or not url.database.startswith("test_dianzi_")
        or not url.username
        or not url.username.startswith("test_")
    ):
        raise RuntimeError("approved test database boundary unavailable")
    return url


def main():
    mode = sys.argv[1]
    if mode not in {"sbom", "legacy"}:
        raise ValueError("unsupported database suite")
    started = datetime.now(ZoneInfo("Asia/Shanghai"))
    run_id = ("r11_sbom_inventory_" if mode == "sbom" else "r11_inventory_") + started.strftime(
        "%Y%m%d_%H%M%S"
    )
    database = "test_dianzi_" + run_id
    assert re.fullmatch(r"test_dianzi_r11_(sbom_inventory|inventory)_[0-9]{8}_[0-9]{6}", database)
    parsed = approved_url()
    admin = create_engine(parsed, isolation_level="AUTOCOMMIT", hide_parameters=True)
    with admin.connect() as connection:
        assert not connection.scalar(
            text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}
        )
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    admin.dispose()
    url = parsed.set(database=database, query={})
    dsn = url.render_as_string(hide_password=False)
    target = "0019_aggregate_observations" if mode == "sbom" else "0018_asset_inventory"
    run_migrations(dsn, target)
    engine = create_engine(url, hide_parameters=True)
    with engine.begin() as connection:
        asset_snapshot_sbom_sidecars.create(connection)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_database()")) == database
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        version = connection.scalar(text("SHOW server_version"))
    engine.dispose()
    receipt = {
        "mode": mode,
        "database": database,
        "host": "127.0.0.1",
        "port": 25432,
        "start": started.isoformat(timespec="seconds"),
        "prepared": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
        "postgres_version": version,
        "forward_revision": revision,
        "sidecar_action": "test_table_create_not_production_0022",
        "rollback": "none",
        "database_deleted": False,
    }
    (RUN / f"database_{run_id}.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    environment = {
        **os.environ,
        "TEST_DATABASE_URL": dsn,
        "DIANZI_TEST_RUN_ID": run_id,
        "PYTHONPATH": str(ROOT / "backend/src"),
        "DIANZI_ENV": "test",
    }
    files = (
        ["tests/integration/test_r11_sbom_inventory_postgres.py"]
        if mode == "sbom"
        else ["tests/integration/test_t24_asset_inventory.py"]
    )
    return run(
        f"pg_{mode}_{run_id}",
        [
            str(PYTHON),
            "-m",
            "pytest",
            *files,
            "--no-cov",
            "-q",
            f"--junitxml={RUN / (run_id + '.xml')}",
        ],
        environment=environment,
    )


if __name__ == "__main__":
    raise SystemExit(main())
