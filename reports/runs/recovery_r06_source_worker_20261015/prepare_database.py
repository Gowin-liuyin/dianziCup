"""Create only the explicitly authorized dedicated catalog-worker test database."""

import json
import subprocess

from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

info = json.loads(
    subprocess.check_output(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--",
            "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json",
        ],
        text=True,
    )
)
url = make_url(info["TEST_DATABASE_URL"])
assert url.database == info["postgres_database"] and url.database.startswith("test_")
target = "test_dianzi_r06_catalog_worker_20261015"
engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
with engine.connect() as connection:
    present = connection.scalar(
        text("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname=:name)"), {"name": target}
    )
    if not present:
        connection.execute(text("CREATE DATABASE test_dianzi_r06_catalog_worker_20261015"))
engine.dispose()
engine = create_engine(url.set(database=target))
with engine.connect() as connection:
    assert connection.scalar(text("SELECT current_database()")) == target
    tables = inspect(connection).get_table_names(schema="public")
    assert tables == [], "dedicated test public schema must stay empty"
engine.dispose()
print(json.dumps({"database": target, "created": not present, "public_tables": tables}))
