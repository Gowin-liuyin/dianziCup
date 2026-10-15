"""Capture bounded offline/isolated-PG commands without persisting credentials."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sqlalchemy import create_engine, func, inspect, select, table, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
label, mode, *argv = sys.argv[1:]
assert mode in {"pure", "pg"}
env = dict(os.environ)
for field in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "DIANZI_TEST_RUN_ID"):
    env.pop(field, None)
connection_url = ""
engine = None
before = None
if mode == "pg":
    connection_info = json.loads(
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
    base_url = make_url(connection_info["TEST_DATABASE_URL"])
    assert base_url.database.startswith("test_")
    target_url = base_url.set(database="test_dianzi_r06_catalog_worker_20261015")
    connection_url = target_url.render_as_string(hide_password=False)
    env.update(TEST_DATABASE_URL=connection_url, DIANZI_TEST_RUN_ID="r06_catalog_worker_20261015")
    engine = create_engine(target_url)

    def public_snapshot():
        with engine.connect() as connection:
            names = inspect(connection).get_table_names(schema="public")
            return {
                "table_counts": {
                    name: connection.scalar(
                        select(func.count()).select_from(table(name, schema="public"))
                    )
                    for name in names
                },
                "alembic_versions": list(
                    connection.scalars(text("SELECT version_num FROM public.alembic_version"))
                )
                if "alembic_version" in names
                else [],
            }

    before = public_snapshot()
started = datetime.now().astimezone().isoformat(timespec="seconds")
result = subprocess.run(
    argv,
    cwd=ROOT / "backend",
    env=env,
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    check=False,
)
output = result.stdout + result.stderr
for value in (connection_url, unquote(urlsplit(connection_url).password or "")):
    if value:
        output = output.replace(value, "[redacted test connection]")
(RUN / f"{label}.log").write_text(output, encoding="utf-8")
after = public_snapshot() if engine is not None else None
metadata = {
    "argv": argv,
    "cwd": str(ROOT / "backend"),
    "started_at": started,
    "ended_at": datetime.now().astimezone().isoformat(timespec="seconds"),
    "exit_code": result.returncode,
    "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "candidate_hashes": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "backend/src/ai_intel/ingestion/source_jobs.py",
            "backend/src/ai_intel/api/source_routes.py",
        )
    },
    "mode": mode,
    "public_before": before,
    "public_after": after,
    "public_unchanged": before == after,
}
(RUN / f"{label}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "label": label,
            "exit_code": result.returncode,
            "public_unchanged": before == after,
            "tail": output[-3000:],
        }
    )
)
if engine is not None:
    engine.dispose()
assert before == after
sys.exit(result.returncode)
