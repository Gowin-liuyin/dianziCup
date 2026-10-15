"""Audit the authorized diff, original regression files, public schema and credentials."""

import hashlib
import json
import os
import subprocess
from pathlib import Path
from urllib.parse import unquote, urlsplit

from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "86e1fd504263844091a7c00415551ad3e8dc4a0c"
FILES = (
    "backend/src/ai_intel/ingestion/source_jobs.py",
    "backend/src/ai_intel/api/source_routes.py",
    "backend/tests/unit/test_r06_source_worker.py",
    "backend/tests/integration/test_r06_source_worker_pg.py",
    "backend/tests/integration/test_r06_source_worker_api_pg.py",
    "backend/tests/r06_source_worker_fixtures.py",
)
changed = subprocess.check_output(
    ["git", "diff", "--name-only", BASE, "HEAD"], cwd=ROOT, text=True
).splitlines()
assert set(changed) == set(FILES)
for name in (
    "backend/tests/integration/test_r04_source_jobs_pg.py",
    "backend/tests/integration/test_r04_source_http_idempotency_pg.py",
    "backend/tests/unit/test_r04_source_jobs.py",
    "backend/tests/unit/test_r04_source_rate_limits.py",
):
    assert subprocess.check_output(
        ["git", "hash-object", name], cwd=ROOT
    ) == subprocess.check_output(["git", "rev-parse", f"{BASE}:{name}"], cwd=ROOT)
connection_url = os.environ["TEST_DATABASE_URL"]
credentials = (connection_url, unquote(urlsplit(connection_url).password or ""))
artifacts = [ROOT / name for name in FILES]
artifacts += [path for path in RUN.iterdir() if path.is_file()]
artifacts += [ROOT / "reports/tasks/R06-source-worker.md"]
for path in artifacts:
    content = path.read_bytes()
    assert all(not value or value.encode() not in content for value in credentials)
for path in RUN.glob("*.json"):
    recorded = json.loads(path.read_bytes())
    if "public_before" in recorded:
        assert recorded["public_before"] == recorded["public_after"]
        assert recorded["public_unchanged"]
engine = create_engine(connection_url)
assert engine.url.database == "test_dianzi_r06_catalog_worker_20261015"
with engine.connect() as connection:
    assert inspect(connection).get_table_names(schema="public") == []
    assert connection.scalar(text("SELECT to_regclass('public.alembic_version')")) is None
engine.dispose()
manifest = {
    "base_sha": BASE,
    "code_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
    "files_sha256": {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in FILES
    },
    "credential_scan_passed": True,
    "old_regressions_unchanged": True,
    "public_tables": [],
    "public_alembic_version": None,
    "artifact_count": len(artifacts),
}
(RUN / "artifact_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
print(json.dumps(manifest))
