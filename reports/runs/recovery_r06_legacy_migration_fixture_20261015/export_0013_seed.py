"""Export only the original public fixture from the frozen 1927 writer and 0013 schema."""

import hashlib
import importlib
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

from sqlalchemy import MetaData, Table, create_engine, inspect, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.schema import CreateSchema, DropSchema

OLD_ROOT = Path("D:/wt/gb-stage-final")
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(OLD_ROOT / "backend/src"))

access = importlib.import_module("ai_intel.domain.access")
AccessScope, Role = access.AccessScope, access.Role
ContentStore = importlib.import_module("ai_intel.infrastructure.content_store").ContentStore
run_migrations = importlib.import_module("ai_intel.infrastructure.database").run_migrations
source_documents = importlib.import_module("ai_intel.ingestion.source_documents")
SourceResponse = source_documents.SourceResponse
persist_source_response = source_documents.persist_source_response

EXPECTED_SHA = "1927eeb00a7e0c1335f76340b0382f46102f08f2"
assert (
    subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=OLD_ROOT, text=True).strip()
    == EXPECTED_SHA
)
assert (
    Path(source_documents.__file__).resolve()
    == OLD_ROOT / "backend/src/ai_intel/ingestion/source_documents.py"
)
assert (
    hashlib.sha256(Path(source_documents.__file__).read_bytes()).hexdigest()
    == "b688f3eb1393c9bb0914980f75578b55c024ab58bd3cf57b3b18f89b78109f8a"
)
ALLOWED_TABLES = {
    "sources",
    "content_objects",
    "documents",
    "document_revisions",
    "text_blocks",
    "evidence",
    "events",
    "event_external_ids",
    "event_documents",
    "claims",
    "claim_assertions",
    "claim_evidence",
    "claim_status_history",
    "scope_epochs",
    "change_events",
    "publication_receipts",
    "outbox_events",
    "fetch_attempts",
    "job_runs",
}
url = make_url(os.environ["TEST_DATABASE_URL"])
assert url.database == "test_dianzi_r05_pgvector_20261015"
base = create_engine(url)
schema = "test_r05_legacy_export_" + uuid4().hex
with base.begin() as connection:
    connection.execute(CreateSchema(schema))
migration_url = url.update_query_dict(
    {"options": f"-c search_path={schema} -c statement_timeout=15000"}
)
engine = create_engine(
    migration_url.update_query_dict(
        {"options": f"-c search_path={schema},public -c statement_timeout=15000"}
    )
)
try:
    run_migrations(
        migration_url.render_as_string(hide_password=False),
        "0013_revision_source_metadata",
    )
    with engine.connect() as connection:
        assert (
            connection.scalar(
                text(
                    "SELECT n.nspname FROM pg_class c "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "WHERE c.oid=to_regclass('alembic_version')"
                )
            )
            == schema
        )
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0013_revision_source_metadata"
        )
    source_path = ROOT / "fixtures/recorded/vllm_vendor_20261015_public.json"
    source_bytes = source_path.read_bytes()
    body = json.dumps([json.loads(source_bytes)[0]]).encode()
    at = datetime(2026, 10, 15, 8, tzinfo=UTC)
    with TemporaryDirectory(prefix="dianzi-legacy-content-") as directory:
        store = ContentStore(Path(directory))
        with Session(engine) as session, session.begin():
            saved = persist_source_response(
                session,
                store,
                AccessScope.for_authenticated_user("fixture-vector-admin", None, Role.SYSTEM_ADMIN),
                SourceResponse(
                    "vllm_vendor",
                    body,
                    "https://api.github.com/repos/vllm-project/vllm/security-advisories?per_page=10&state=published",
                    at,
                ),
                ingested_at=at,
            )
        tables = {}
        with engine.connect() as connection:
            available = set(inspect(connection).get_table_names(schema=schema))
            for name in sorted(ALLOWED_TABLES):
                assert name in available
                table = Table(
                    name,
                    MetaData(),
                    schema=schema,
                    autoload_with=connection,
                    resolve_fks=False,
                )
                rows = [dict(row) for row in connection.execute(select(table)).mappings()]
                if rows:
                    tables[name] = {"columns": list(table.columns.keys()), "rows": rows}
            assert tables["evidence"]["rows"]
            assert len(tables["document_revisions"]["rows"]) == 1
            assert "source_metadata" not in tables["document_revisions"]["columns"]
        payloads = {
            row["content_hash"]: store.read_verified(row["content_hash"]).decode("utf-8")
            for row in tables["content_objects"]["rows"]
        }
    seed = {
        "fixture_version": 1,
        "data_mode": "fixture",
        "migration_revision": "0013_revision_source_metadata",
        "writer_commit": EXPECTED_SHA,
        "writer_source_sha256": hashlib.sha256(
            Path(source_documents.__file__).read_bytes()
        ).hexdigest(),
        "source_fixture": "fixtures/recorded/vllm_vendor_20261015_public.json",
        "source_fixture_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "source_record_index": 0,
        "response_body_sha256": hashlib.sha256(body).hexdigest(),
        "observed_at": at.isoformat(),
        "required_tables": sorted(tables),
        "tables": tables,
        "content_payloads_utf8": payloads,
    }
    output = ROOT / "fixtures/recorded/r05_legacy_0013_vllm_public_v1.json"
    output.write_text(
        json.dumps(
            seed,
            ensure_ascii=False,
            indent=2,
            default=lambda value: value.isoformat() if isinstance(value, datetime) else value,
        )
        + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "writer_commit": EXPECTED_SHA,
                "writer_import": source_documents.__file__,
                "interpreter": sys.executable,
                "schema_revision": "0013_revision_source_metadata",
                "output": str(output),
                "output_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
                "table_counts": {name: len(value["rows"]) for name, value in tables.items()},
                "content_hashes": sorted(payloads),
            }
        )
    )
finally:
    engine.dispose()
    with base.begin() as connection:
        connection.execute(DropSchema(schema, cascade=True))
    base.dispose()
