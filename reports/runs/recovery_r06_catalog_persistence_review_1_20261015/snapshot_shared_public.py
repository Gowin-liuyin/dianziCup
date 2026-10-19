"""Read-only scope-incident snapshot; no row values or credentials are emitted."""

import json

from sqlalchemy import create_engine, text

from run_review import RUN, load_connection, now

resource = load_connection("/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json")
engine = create_engine(resource["TEST_DATABASE_URL"])
with engine.connect() as connection, connection.begin():
    connection.execute(text("SET TRANSACTION READ ONLY"))
    assert connection.scalar(text("SELECT current_setting('transaction_read_only')")) == "on"
    database = connection.scalar(text("SELECT current_database()"))
    assert database == "test_dianzi_r05_pgvector_20261015"
    tables = list(connection.scalars(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename")))
    assert len(tables) <= 100
    counts = {}
    for table in tables:
        identifier = connection.dialect.identifier_preparer.quote(table)
        counts[table] = connection.scalar(text("SELECT COUNT(*) FROM public." + identifier))
    version = None
    if "alembic_version" in tables:
        version = list(connection.scalars(text("SELECT version_num FROM public.alembic_version ORDER BY version_num")))
engine.dispose()
result = {"observed_at": now(), "database": database, "transaction_read_only": True,
          "public_table_counts": counts, "public_alembic_version": version,
          "attribution": "snapshot after reviewer scope error; no before-snapshot exists, so counts are not claimed as all reviewer-created"}
(RUN / "shared_public_read_only_snapshot.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
print(json.dumps(result))
