"""Run isolated checks with credential redaction and a public-schema mutation guard."""

import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sqlalchemy import create_engine, func, inspect, select, table, text

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
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
            "/tmp/dianzi-docker-static-r01-20261014/runtime/r05-pgvector/connection.json",
        ],
        text=True,
    )
)
connection_url = connection_info["TEST_DATABASE_URL"]
engine = create_engine(connection_url)
assert engine.url.database == "test_dianzi_r05_pgvector_20261015"


def public_snapshot():
    with engine.connect() as connection:
        tables = inspect(connection).get_table_names(schema="public")
        counts = {
            name: connection.scalar(select(func.count()).select_from(table(name, schema="public")))
            for name in tables
        }
        versions = (
            list(connection.scalars(text("SELECT version_num FROM public.alembic_version")))
            if "alembic_version" in tables
            else []
        )
        return {"table_counts": counts, "alembic_versions": versions}


label, *argv = sys.argv[1:]
before = public_snapshot()
started = datetime.now().astimezone().isoformat()
env = {
    **os.environ,
    "TEST_DATABASE_URL": connection_url,
    "DIANZI_TEST_RUN_ID": "r05_pgvector_20261015",
    "PYTHONPATH": str(ROOT / "backend/src"),
}
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
after = public_snapshot()
metadata = {
    "argv": argv,
    "cwd": str(ROOT / "backend"),
    "started_at": started,
    "ended_at": datetime.now().astimezone().isoformat(),
    "exit_code": result.returncode,
    "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "public_before": before,
    "public_after": after,
    "public_unchanged": before == after,
    "candidate_files_sha256": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in (
            "backend/tests/integration/test_r05_vector_persistence.py",
            "backend/tests/integration/test_r05_question_api_pg.py",
            "fixtures/recorded/r05_legacy_0013_vllm_public_v1.json",
        )
        if (ROOT / name).exists()
    },
    "scope": "Dedicated real PG; synthetic/recorded fixture, no model live",
}
(RUN / f"{label}.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
print(
    json.dumps(
        {
            "label": label,
            "exit_code": result.returncode,
            "public_unchanged": before == after,
            "output_tail": output[-2500:],
        }
    )
)
engine.dispose()
assert before == after, "public schema changed"
sys.exit(result.returncode)
