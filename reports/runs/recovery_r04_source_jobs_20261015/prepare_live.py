"""为固定 SHA 的真实来源链建专用测试库；只通过 stdin 保存仓外秘密配置。"""

import json
import os
import subprocess
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from zoneinfo import ZoneInfo

from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import run_migrations

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
FROZEN = Path("C:/Users/yinha/.codex/worktrees/r04-real-pipeline/dianzi")
SHA = "95ba6503dcae4b86ea8fdffea150f1b59a941014"
NOW = datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds")
assert subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=FROZEN, text=True).strip() == SHA
assert not (RUN / "live_prepare.json").exists(), "do not overwrite previous runtime preparation"


def private_json(path):
    result = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "cat", path],
        capture_output=True, text=True, check=True, timeout=10)
    return json.loads(result.stdout)


def main():
    connections = private_json("/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json")
    objects = private_json("/tmp/dianzi-minio-r02-20261015/private/connection.json")
    source = make_url(connections["TEST_DATABASE_URL"])
    assert source.host == "127.0.0.1" and source.port == 25432
    assert source.database == "test_dianzi_r01_20261014"
    database = "test_dianzi_r04_pipeline_20261015"
    admin = create_engine(source, isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        assert connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": database}) is None, "runtime database already exists; inspect before resuming"
        connection.execute(text(f'CREATE DATABASE "{database}"'))
    admin.dispose()
    database_url = source.set(database=database).render_as_string(hide_password=False)
    run_migrations(database_url)
    engine = create_engine(database_url)
    try:
        directory = DatabaseUserDirectory(engine)
        service = AuthenticationSessionService(directory, ("http://127.0.0.1:25300", "http://127.0.0.1:25305"), False)
        for suffix, tenant, role in (("", "test-r04-display", Role.ANALYST), ("-r04-admin", None, Role.SYSTEM_ADMIN)):
            service.create_precreated_user(os.environ["DIANZI_E2E_USERNAME"] + suffix,
                os.environ["DIANZI_E2E_PASSWORD"], tenant, role)
        with engine.connect() as connection:
            migration = connection.scalar(text("SELECT version_num FROM alembic_version"))
    finally:
        engine.dispose()
    redis_parts = urlsplit(connections["TEST_REDIS_URL"])
    assert redis_parts.hostname == "127.0.0.1" and redis_parts.port == 26379
    redis_url = urlunsplit(redis_parts._replace(path="/14"))
    from redis import Redis
    cache = Redis.from_url(redis_url, socket_connect_timeout=3, socket_timeout=3)
    assert cache.dbsize() == 0, "dedicated runtime Redis DB14 is not empty"
    cache.close()
    settings = {
        "APP_ENV": "test", "DATA_MODE": "live", "DATABASE_URL": database_url,
        "REDIS_URL": redis_url, "OPENSEARCH_URL": "http://127.0.0.1:29200",
        "ALLOWED_ORIGINS": '["http://127.0.0.1:25300","http://127.0.0.1:25305"]',
        "DNS_RESOLVER": "cloudflare_doh", "CONTENT_STORE_BACKEND": "minio",
        "MINIO_ENDPOINT": objects["endpoint"], "MINIO_BUCKET": objects["bucket"],
        "MINIO_ACCESS_KEY": objects["access_key"], "MINIO_SECRET_KEY": objects["secret_key"],
        "MINIO_SECURE": "false", "DIANZI_E2E_USERNAME": os.environ["DIANZI_E2E_USERNAME"],
        "DIANZI_E2E_PASSWORD": os.environ["DIANZI_E2E_PASSWORD"],
    }
    payload = json.dumps({"code_sha": SHA, "environment": settings,
        "secret_values": [source.password or "", redis_parts.password or "", objects["access_key"], objects["secret_key"], os.environ["DIANZI_E2E_PASSWORD"]]})
    private_path = "/tmp/dianzi-r04-live-20261015/private/runtime.json"
    save = subprocess.run(["wsl", "-d", "Ubuntu-22.04", "-u", "root", "--exec", "python3", "-c",
        "import os,pathlib,sys;os.umask(0o077);p=pathlib.Path(sys.argv[1]);p.parent.mkdir(mode=0o700,parents=True,exist_ok=True);p.write_text(sys.stdin.read());p.chmod(0o600)", private_path],
        input=payload, text=True, capture_output=True, timeout=10)
    assert save.returncode == 0, "private configuration write failed"
    receipt = {"started_at": NOW, "ended_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"), "code_sha": SHA,
        "database": database, "migration": migration, "redis_database": 14,
        "source_mode": "real public source GET; no inserted fixture records",
        "transport_scope": "isolated test MinIO and search use loopback HTTP; external source gateway verifies HTTPS",
        "credential_arguments": False, "private_configuration_mode": "0600",
        "precreated_accounts": "dedicated analyst and global source administrator"}
    (RUN / "live_prepare.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(json.dumps({"status": "failed", "error_type": type(error).__name__, "details": "withheld; preserve partial resources for diagnosis"}))
        raise SystemExit(1) from None
