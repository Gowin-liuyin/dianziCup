"""Create only this new database, upgrade forward, and provision its local login."""

from common import DATABASE, PREFIX, PRODUCT_SHA, now, verify_authorization, write

verify_authorization()

import os

from redis import Redis
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.settings import load_application_settings

settings = load_application_settings()
assert settings.data_mode == "live" and settings.content_store_backend == "minio" and settings.source_polling_enabled
assert settings.generation_api_key is None or not settings.generation_api_key.get_secret_value()
url = make_url(os.environ["DATABASE_URL"]).set(drivername="postgresql+psycopg")
assert url.database == DATABASE and url.host in {"127.0.0.1", "localhost"} and url.port == 25432
cache = Redis.from_url(os.environ["REDIS_URL"], socket_timeout=3, socket_connect_timeout=3)
assert cache.connection_pool.connection_kwargs["db"] == 15
existing_keys = cache.dbsize()
assert not list(cache.scan_iter(match=PREFIX + "*", count=100))
cache.close()
base = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", hide_parameters=True)
with base.connect() as connection:
    assert not connection.scalar(text("select 1 from pg_database where datname=:name"), {"name": DATABASE})
    protected = [dict(row) for row in connection.execute(text("select datname,oid from pg_database where datname like 'test_dianzi_%' order by datname")).mappings()]
    connection.execute(text('CREATE DATABASE "' + DATABASE + '"'))
base.dispose()
run_migrations(url.render_as_string(hide_password=False), "0016_source_response_receipts")
engine = create_engine(url, hide_parameters=True)
auth = AuthenticationSessionService(DatabaseUserDirectory(engine), ("http://127.0.0.1:25176",), False, state_store=PgAuthenticationStateStore(engine))
auth.create_precreated_user(os.environ["DIANZI_E2E_USERNAME"] + "-r06-live-8a-admin", os.environ["DIANZI_E2E_PASSWORD"], None, Role.SYSTEM_ADMIN)
with engine.connect() as connection:
    installed = connection.scalar(text("select version_num from alembic_version"))
    assert installed == "0016_source_response_receipts"
    assert connection.scalar(text("select count(*) from job_runs")) == 0
engine.dispose()
write("prepare_receipt.json", {"prepared_at": now(), "product_sha": PRODUCT_SHA, "database": DATABASE, "schema": installed, "protected_database_identities": protected, "redis_database": 15, "existing_redis_keys_preserved": existing_keys, "owned_prefix_keys_before": 0, "redis_flush_or_delete": False, "source_requests_so_far": 0, "model_requests_permitted": 0, "data_mode": "live", "content_store_backend": "minio"})
print("isolated forward migration and local login prepared")
