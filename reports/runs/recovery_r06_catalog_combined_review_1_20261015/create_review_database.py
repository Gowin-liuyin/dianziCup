"""Create only the dedicated review database explicitly authorized by the controller."""

import json
import subprocess

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url


def main():
    info = json.loads(subprocess.check_output([
        "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
        "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json",
    ], text=True))
    url = make_url(info["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r05_pgvector_20261015"
    name = "test_dianzi_r06_catalog_final_review_20261015"
    engine = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT", connect_args={"connect_timeout": 5})
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT 1 FROM pg_database WHERE datname=:name"), {"name": name}) is None
            connection.execute(text('CREATE DATABASE "test_dianzi_r06_catalog_final_review_20261015"'))
        print(json.dumps({"created_database": name, "public_tables_expected": 0}))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
