"""Capture independent commands without granting umbrella tests PostgreSQL access."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
TZ = timezone(timedelta(hours=8))


def stamp():
    return datetime.now(TZ).isoformat()


def public_snapshot(connection_url):
    from sqlalchemy import create_engine, func, inspect, select, table, text

    engine = create_engine(connection_url, connect_args={"connect_timeout": 5})
    assert engine.url.database in {"test_dianzi_r05_pgvector_20261015", "test_dianzi_r06_catalog_final_review_20261015"}
    try:
        with engine.connect() as connection:
            transaction = connection.begin()
            connection.execute(text("SET TRANSACTION READ ONLY"))
            names = inspect(connection).get_table_names(schema="public")
            counts = {
                name: connection.scalar(select(func.count()).select_from(table(name, schema="public")))
                for name in names
            }
            versions = list(connection.scalars(text("SELECT version_num FROM public.alembic_version"))) if "alembic_version" in names else []
            schemas = list(connection.scalars(text("SELECT nspname FROM pg_namespace WHERE nspname LIKE 'test_r05_%' OR nspname LIKE 'test_r06_%' ORDER BY nspname")))
            transaction.rollback()
            return {"table_counts": counts, "alembic_versions": versions, "test_schemas": schemas}
    finally:
        engine.dispose()


def main():
    label, mode, *argv = sys.argv[1:]
    assert mode in {"pure", "pg", "static"}
    env = dict(os.environ)
    for name in tuple(env):
        if name in {"TEST_DATABASE_URL", "DIANZI_TEST_RUN_ID", "DATABASE_URL", "PGPASSWORD", "PGSERVICE", "PGSERVICEFILE"}:
            env.pop(name)
    env.update({
        "PYTHONPATH": str(ROOT / "backend/src"),
        "PYTHONDONTWRITEBYTECODE": "1",
        "COVERAGE_FILE": str(RUN / f"coverage_{label}"),
        "PYTHONUTF8": "1",
    })
    connection_url = None
    before = None
    if mode == "pure":
        assert "pytest" in argv and "not real_pg" in argv
    elif mode == "pg":
        allowed = {
            "tests/integration/test_r05_vector_persistence.py",
            "tests/integration/test_r05_question_api_pg.py",
            "tests/integration/test_r06_catalog_documents_pg.py",
            str(RUN / "test_independent_probes.py"),
            str(RUN / "verify_seed.py"),
        }
        selected = [value for value in argv if value.endswith(".py") or ".py::" in value]
        assert selected and all(value.split("::")[0].replace("\\", "/") in {name.replace("\\", "/") for name in allowed} for value in selected)
        connection_info = json.loads(subprocess.check_output([
            "wsl", "-d", "Ubuntu-22.04", "-u", "root", "--", "cat",
            "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json",
        ], text=True))
        connection_url = connection_info["TEST_DATABASE_URL"]
        if label.startswith("catalog_") or label.startswith("probes_"):
            from sqlalchemy.engine import make_url

            connection_url = make_url(connection_url).set(database="test_dianzi_r06_catalog_final_review_20261015").render_as_string(hide_password=False)
        run_id = "r06_catalog_final_review_20261015" if label.startswith(("catalog_", "probes_")) else "r05_pgvector_20261015"
        env.update({"TEST_DATABASE_URL": connection_url, "DIANZI_TEST_RUN_ID": run_id})
        before = public_snapshot(connection_url)
    started = stamp()
    result = subprocess.run(argv, cwd=ROOT / "backend", env=env, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    ended = stamp()
    output = result.stdout + result.stderr
    if connection_url:
        for secret in {connection_url, unquote(urlsplit(connection_url).password or "")}:
            if secret:
                output = output.replace(secret, "[redacted test connection]")
    log = RUN / f"{label}.log"
    log.write_text(output, encoding="utf-8")
    after = public_snapshot(connection_url) if connection_url else None
    metadata = {
        "label": label, "mode": mode, "argv": argv, "cwd": str(ROOT / "backend"),
        "started_at": started, "ended_at": ended, "exit_code": result.returncode,
        "sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "log": log.name, "log_sha256": hashlib.sha256(log.read_bytes()).hexdigest(),
        "public_before": before, "public_after": after,
        "public_counts_and_versions_unchanged": before is None or {k:v for k,v in before.items() if k != "test_schemas"} == {k:v for k,v in after.items() if k != "test_schemas"},
        "pg_environment_granted": mode == "pg",
    }
    (RUN / f"{label}.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    with (RUN / "commands.jsonl").open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(metadata, ensure_ascii=False) + "\n")
    print(json.dumps({"label": label, "exit_code": result.returncode, "public_unchanged": metadata["public_counts_and_versions_unchanged"], "output_tail": output[-2000:]}, ensure_ascii=False))
    assert metadata["public_counts_and_versions_unchanged"], "public counts/version changed"
    sys.exit(result.returncode)


if __name__ == "__main__":
    main()
