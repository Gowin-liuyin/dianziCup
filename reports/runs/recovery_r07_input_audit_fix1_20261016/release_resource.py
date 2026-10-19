"""Verify only this marked database has no owned schemas or remaining sessions."""

import json
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from checks import DATABASE, OWNER, RUN, now, resource_url

started = now()
engine = create_engine(resource_url(), hide_parameters=True, poolclass=NullPool)
try:
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT shobj_description(oid,'pg_database') FROM pg_database WHERE datname=current_database()")) == OWNER
        schemas = connection.scalar(text("SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'test_r07_audit_fix1_%'"))
        sessions = connection.scalar(text("SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() AND pid<>pg_backend_pid()"))
        assert schemas == 0 and sessions == 0
finally:
    engine.dispose()
(RUN / "resource_release.json").write_bytes(json.dumps({"started_at": started, "ended_at": now(), "database": DATABASE, "owned_schemas": schemas, "other_database_sessions": sessions, "engine_disposed": True, "exit_code": 0}, indent=2).encode())
print(json.dumps({"owned_schemas": schemas, "other_database_sessions": sessions, "engine_disposed": True}))
