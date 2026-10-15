"""仅创建已命名R02隔离库，将专属连接配置写到仓库外WSL root600文件。"""

import json
import os
import subprocess
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ai_intel.infrastructure.database import run_migrations

started_at = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
configuration = json.loads(os.environ["DIANZI_ROOT_TEST_CONNECTION"])
root_url = make_url(configuration["TEST_DATABASE_URL"])
assert root_url.host == "127.0.0.1" and root_url.port == 25432
assert root_url.database == "test_dianzi_r01_20261014" and root_url.username == "test_dianzi_r01"
engine = create_engine(
    root_url, isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5}
)
receipts: list[dict[str, object]] = []
try:
    with engine.connect() as connection:
        database, user = connection.execute(text("SELECT current_database(), current_user")).one()
        assert database == root_url.database and user == root_url.username
        for run_id in ("r02_auth_20261015", "r02_knowledge_20261015"):
            database_name = "test_dianzi_" + run_id
            exists = connection.execute(
                text("SELECT 1 FROM pg_database WHERE datname = :name"), {"name": database_name}
            ).scalar_one_or_none()
            if exists is None:
                connection.execute(text(f'CREATE DATABASE "{database_name}"'))
            test_url = root_url.set(database=database_name).render_as_string(hide_password=False)
            run_migrations(test_url)
            private_path = f"/tmp/dianzi-{run_id}/connection.json"
            private_configuration = {
                "DIANZI_TEST_RUN_ID": run_id,
                "TEST_DATABASE_URL": test_url,
                "NO_PROXY": "127.0.0.1,localhost,::1",
            }
            save_private = subprocess.run(
                [
                    "wsl.exe", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-c",
                    "import os,pathlib,sys;os.umask(0o077);"
                    "p=pathlib.Path(sys.argv[1]);p.parent.mkdir(mode=0o700,exist_ok=True);"
                    "p.write_text(sys.stdin.read());p.chmod(0o600)", private_path,
                ],
                input=json.dumps(private_configuration), text=True, capture_output=True, timeout=20,
            )
            if save_private.returncode:
                raise RuntimeError("private test configuration storage failed")
            receipts.append({"run_id": run_id, "database": database_name, "private_path": private_path})
finally:
    engine.dispose()
print(json.dumps({
    "started_at": started_at,
    "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "resource": "owned root test PostgreSQL on loopback 25432; separate R02 databases",
    "migration": "0006_auth_state", "databases": receipts,
}, ensure_ascii=False, indent=2))
