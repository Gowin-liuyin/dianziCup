"""Provision one new named live-source test DB without changing the running G-B database."""

import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from redis import Redis

from ai_intel.api.auth_state import PgAuthenticationStateStore
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.infrastructure.settings import load_application_settings

run = Path(__file__).resolve().parent
assert not (run / "prepare_receipt.json").exists()
url = make_url(os.environ["DATABASE_URL"])
assert url.database == "test_dianzi_r06_integrated_live_20261015"
assert url.host in {"localhost", "127.0.0.1"}
settings = load_application_settings()
(run / "settings_precheck.json").write_text(json.dumps({
    "observed_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "environment_data_mode": os.environ.get("DATA_MODE"),
    "environment_content_store": os.environ.get("CONTENT_STORE_BACKEND"),
    "settings_data_mode": settings.data_mode,
    "settings_content_store": settings.content_store_backend,
    "source_polling_enabled": settings.source_polling_enabled,
}, indent=2) + "\n", encoding="utf-8")
assert settings.data_mode == "live" and settings.content_store_backend == "minio"
assert settings.source_polling_enabled
assert settings.generation_api_key is None or not settings.generation_api_key.get_secret_value()
cache = Redis.from_url(os.environ["REDIS_URL"], socket_timeout=3, socket_connect_timeout=3)
redis_database = cache.connection_pool.connection_kwargs["db"]
redis_size = cache.dbsize()
cache.close()
assert redis_database == 15 and redis_size == 0
base = create_engine(url.set(database="test_dianzi_r04_pipeline_20261015"), isolation_level="AUTOCOMMIT")
with base.connect() as connection:
    before = connection.scalar(text("select version_num from alembic_version"))
    assert before == "0014_grounded_answer_vectors"
    assert not connection.scalar(text("select 1 from pg_database where datname=:name"), {"name": url.database})
    connection.execute(text('CREATE DATABASE "test_dianzi_r06_integrated_live_20261015"'))
base.dispose()
run_migrations(url.render_as_string(hide_password=False))
engine = create_engine(url, connect_args={"connect_timeout": 3})
auth = AuthenticationSessionService(DatabaseUserDirectory(engine), ("http://127.0.0.1:25175",), False, state_store=PgAuthenticationStateStore(engine))
for suffix, role, tenant in (("-r06-integrated-admin", Role.SYSTEM_ADMIN, None), ("-r06-integrated-viewer", Role.VIEWER, "integrated-live-viewer")):
    auth.create_precreated_user(os.environ["DIANZI_E2E_USERNAME"] + suffix, os.environ["DIANZI_E2E_PASSWORD"], tenant, role)
with engine.connect() as connection:
    installed = connection.scalar(text("select version_num from alembic_version"))
    counts = {name: connection.scalar(text("select count(*) from " + name)) for name in ("users", "events", "documents", "document_revisions", "evidence", "job_runs")}
    assert installed == "0015_catalog_document_metadata" and counts["users"] == 2
engine.dispose()
(run / "prepare_receipt.json").write_text(json.dumps({
    "prepared_at": datetime.now(ZoneInfo("Asia/Shanghai")).isoformat(timespec="seconds"),
    "database": url.database, "schema": installed, "counts": counts,
    "running_gb_database_action": "read-only version check; no migrations or writes",
    "product_data_mode": "live", "source_requests_so_far": 0,
    "credentials_recorded": False,
    "redis_database": redis_database, "redis_keys_before": redis_size,
    "source_polling_enabled": True, "beat_poll_interval_seconds": 60,
    "content_store": "same authorized MinIO identity; immutable content-addressed objects",
    "model_calls_permitted": 0,
}, indent=2) + "\n", encoding="utf-8")
print("new isolated document-live database prepared; G-B schema unchanged")
