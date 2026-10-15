"""Capture authorized WSL secrets only in memory and pass them to isolated test processes."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import httpx
import psycopg
from psycopg import sql
from run_checks import RUN, execute
from sqlalchemy.engine import make_url

DATABASE = "test_dianzi_r12_hybrid_20261016"
SECRET_SOURCE = "/tmp/dianzi-docker-static-r01-20261014/runtime/test-services/connection.json"


def prepare() -> None:
    captured = subprocess.run(
        [
            "wsl",
            "-d",
            "Ubuntu-22.04",
            "-u",
            "root",
            "--",
            "cat",
            SECRET_SOURCE,
        ],
        capture_output=True,
        check=False,
        timeout=15,
    )
    if captured.returncode != 0:
        raise RuntimeError("authorized_connection_reference_unavailable")
    connection = json.loads(captured.stdout)
    database_url = make_url(connection["TEST_DATABASE_URL"])
    if (database_url.host, database_url.port, database_url.database) != (
        "127.0.0.1",
        25432,
        "test_dianzi_r01_20261014",
    ):
        raise RuntimeError("authorized_connection_identity_mismatch")
    parameters = {
        "host": database_url.host,
        "port": database_url.port,
        "user": database_url.username,
        "password": database_url.password,
        "connect_timeout": 5,
        "options": "-c statement_timeout=15000 -c lock_timeout=5000",
    }
    with psycopg.connect(dbname=database_url.database, **parameters) as pg:
        pg.autocommit = True
        if pg.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DATABASE,)).fetchone() is None:
            pg.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DATABASE)))
    with psycopg.connect(dbname=DATABASE, **parameters) as pg:
        pg.execute("CREATE EXTENSION IF NOT EXISTS vector")
        version = pg.execute("SHOW server_version").fetchone()[0]
        extension = pg.execute(
            "SELECT extversion FROM pg_extension WHERE extname='vector'"
        ).fetchone()[0]
    os.environ["TEST_DATABASE_URL"] = database_url.set(database=DATABASE).render_as_string(
        hide_password=False
    )
    os.environ["DIANZI_TEST_RUN_ID"] = "r12_hybrid_20261016"
    os.environ["R05_SEMANTIC_CACHE"] = "C:/Users/yinha/.codex/cache/dianzi/r05-semantic-runtime"
    os.environ["R12_EVIDENCE_DIR"] = str(RUN / "synthetic_source_blobs")
    names = sorted(name for name in connection if name.startswith(("TEST_OPENSEARCH_", "R12_")))
    for name in names:
        os.environ[name] = connection[name]
    base_url = os.environ.get("R12_OPENSEARCH_URL") or os.environ.get("TEST_OPENSEARCH_URL")
    if base_url is None:
        base_url = "http://127.0.0.1:29200"
    prior_probe = RUN / "resource_probe.json"
    metadata = {
        "database": DATABASE,
        "postgres_version": version,
        "vector_version": extension,
        "available_search_config_keys": names,
        "source_reference": SECRET_SOURCE,
    }
    if prior_probe.exists():
        prior = json.loads(prior_probe.read_text(encoding="utf-8"))
        metadata["opensearch_status"] = prior["opensearch_status"]
        metadata["opensearch_version"] = prior.get("opensearch_version")
    else:
        probe = httpx.get(base_url.rstrip("/") + "/", timeout=3.0, follow_redirects=False)
        metadata["opensearch_status"] = probe.status_code
        if probe.status_code == 200:
            payload = probe.json()
            metadata["opensearch_version"] = payload.get("version", {}).get("number")
    if metadata["opensearch_status"] == 200:
        os.environ["R12_OPENSEARCH_URL"] = base_url
    (RUN / "resource_probe.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(json.dumps(metadata))
    if metadata["opensearch_status"] != 200:
        raise RuntimeError("opensearch_access_blocked")


def main() -> int:
    try:
        prepare()
    except Exception as error:
        print(json.dumps({"status": "blocked_resource", "error_type": type(error).__name__}))
        return 4
    return execute(
        sys.argv[1], [str(Path("D:/dianzi/backend/.venv/Scripts/python.exe")), *sys.argv[2:]]
    )


if __name__ == "__main__":
    raise SystemExit(main())
