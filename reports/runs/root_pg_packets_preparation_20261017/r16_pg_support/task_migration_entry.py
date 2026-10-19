"""Migrate only the Root-owned nonce schema to the exact approved 0031 dependency."""
import os
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from ai_intel.infrastructure.database import run_migrations
from task_pg_identity import verify_native_identity
database_url = os.environ["R18_REVIEW_MIGRATION_DATABASE_URL"]
engine = create_engine(database_url, poolclass=NullPool, hide_parameters=True)
try:
    with engine.connect() as connection:
        verify_native_identity(connection)
    run_migrations(database_url, "0031_public_task_bindings")
    with engine.connect() as connection:
        verify_native_identity(connection)
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0031_public_task_bindings"
finally:
    engine.dispose()
print("owned nonce schema at exact head 0031; no unrelated R05 seed")
