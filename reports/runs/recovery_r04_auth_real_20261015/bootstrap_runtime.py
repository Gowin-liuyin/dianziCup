"""仅在已命名隔离test库迁移/预创建测试账号，不输出连接或凭据。"""

import json
import os
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

from sqlalchemy import text

from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import build_engine, run_migrations
from ai_intel.infrastructure.settings import load_application_settings

clock = ZoneInfo("Asia/Shanghai")
started_at = datetime.now(clock).isoformat(timespec="seconds")
expected_database = "test_dianzi_r01_20261014"
url = urlsplit(os.environ["DATABASE_URL"])
assert url.hostname == "127.0.0.1" and url.port == 25432
assert url.path == "/" + expected_database and url.username == "test_dianzi_r01"
configuration = load_application_settings()
engine = build_engine(configuration)
try:
    with engine.connect() as connection:
        database, user = connection.execute(text("SELECT current_database(), current_user")).one()
    assert database == expected_database and user == "test_dianzi_r01"
    run_migrations(os.environ["DATABASE_URL"])
    directory = DatabaseUserDirectory(engine)
    username = os.environ["DIANZI_E2E_USERNAME"]
    if directory.find_by_username(username) is None:
        AuthenticationSessionService(
            directory, configuration.allowed_origins, False
        ).create_precreated_user(
            username, os.environ["DIANZI_E2E_PASSWORD"], "test-tenant-r01-root", Role.ANALYST
        )
    with engine.connect() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
    receipt = {
        "started_at": started_at,
        "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
        "database": expected_database,
        "user": user,
        "port": 25432,
        "migration_revision": revision,
        "precreated_account": "dedicated integration-test analyst",
        "data_mode": configuration.data_mode,
        "status": "bootstrapped",
    }
    Path(os.environ["DIANZI_BOOTSTRAP_RECEIPT"]).write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("isolated runtime bootstrapped", revision)
finally:
    engine.dispose()
