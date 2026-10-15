"""Assert source provenance, integrity, isolation and loader rejection boundaries."""

import ast
import hashlib
import importlib
import json
import os
import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "backend/tests/integration"))
load_legacy_0013_seed = importlib.import_module("test_r05_vector_persistence").load_legacy_0013_seed

BASE = "7b8103e6d91a7274bcfb661d8e6f1d5b7180be17"
test_path = "backend/tests/integration/test_r05_vector_persistence.py"
old = ast.parse(
    subprocess.check_output(
        ["git", "show", f"{BASE}:{test_path}"], cwd=ROOT, text=True, encoding="utf-8"
    )
)
current = ast.parse((ROOT / test_path).read_text(encoding="utf-8"))
old_tests = {
    node.name: ast.dump(node)
    for node in old.body
    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
}
new_tests = {
    node.name: ast.dump(node)
    for node in current.body
    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")
}
assert old_tests == new_tests
question_path = "backend/tests/integration/test_r05_question_api_pg.py"
assert subprocess.check_output(
    ["git", "hash-object", question_path], cwd=ROOT
) == subprocess.check_output(["git", "rev-parse", f"{BASE}:{question_path}"], cwd=ROOT)
checks = [
    "all_original_business_test_asts_unchanged",
    "question_api_git_blob_unchanged",
]
seed_path = ROOT / "fixtures/recorded/r05_legacy_0013_vllm_public_v1.json"
seed_bytes = seed_path.read_bytes()
seed = json.loads(seed_bytes)
rows = seed["tables"]
blocks = {row["block_id"]: row for row in rows["text_blocks"]["rows"]}
for item in rows["evidence"]["rows"]:
    block = blocks[item["block_id"]]
    start = item["start_offset"] - block["start_offset"]
    end = item["end_offset"] - block["start_offset"]
    assert block["block_text"][start:end] == item["quote"]
    assert hashlib.sha256(item["quote"].encode()).hexdigest() == item["quote_sha256"]
    assert item["verified_at"] is not None
checks.append("all_nonempty_evidence_quotes_coordinates_hashes_verified")


class NoDatabaseAccess:
    def begin(self):
        raise RuntimeError("unexpected database access before seed validation")


with TemporaryDirectory(prefix="dianzi-seed-constraints-") as directory:
    store = ContentStore(Path(directory))
    original_read = Path.read_bytes
    canonical_seed = seed_bytes.replace(b"\r\n", b"\n")
    for name, valid in (
        ("lf_seed_hash_accepted", canonical_seed),
        ("crlf_seed_hash_accepted", canonical_seed.replace(b"\n", b"\r\n")),
    ):

        def equivalent_seed(path, portable_seed=valid):
            return portable_seed if path == seed_path else original_read(path)

        with patch.object(Path, "read_bytes", equivalent_seed):
            try:
                load_legacy_0013_seed(NoDatabaseAccess(), "test_r05_unused", store)
            except RuntimeError as expected:
                assert str(expected) == "unexpected database access before seed validation"
            else:
                raise AssertionError("valid portable seed did not reach the target guard")
        checks.append(name)
    for invalid in (
        seed_bytes + b" ",
        seed_bytes.replace(b'"sources"', b'"users"', 1),
        seed_bytes.replace(b'"revision_number"', b'"unapproved_column"', 1),
    ):
        with patch.object(Path, "read_bytes", return_value=invalid):
            try:
                load_legacy_0013_seed(NoDatabaseAccess(), "test_r05_unused", store)
            except AssertionError:
                pass
            else:
                raise AssertionError("tampered seed was accepted")
    checks.extend(
        [
            "altered_seed_rejected_before_io",
            "unapproved_table_rejected_before_io",
            "unapproved_column_rejected_before_io",
        ]
    )

    def altered_source(path):
        if path.name == "vllm_vendor_20261015_public.json":
            return original_read(path) + b" "
        return original_read(path)

    with patch.object(Path, "read_bytes", altered_source):
        try:
            load_legacy_0013_seed(NoDatabaseAccess(), "test_r05_unused", store)
        except AssertionError:
            pass
        else:
            raise AssertionError("altered source was accepted")
    checks.append("altered_recorded_source_rejected_before_io")

    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r05_pgvector_20261015"
    base = create_engine(url)
    schema = "test_r05_seed_constraints_" + uuid4().hex
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    migration_url = url.update_query_dict({"options": f"-c search_path={schema}"})
    engine = create_engine(
        migration_url.update_query_dict({"options": f"-c search_path={schema},public"})
    )
    try:
        run_migrations(
            migration_url.render_as_string(hide_password=False),
            "0013_revision_source_metadata",
        )
        tables = load_legacy_0013_seed(engine, schema, store)

        def snapshot():
            with engine.connect() as connection:
                return tuple(
                    tuple(connection.execute(select(table).order_by(*table.primary_key.columns)))
                    for table in tables
                )

        before = snapshot()
        for name, rejected_schema in (
            ("public_schema_rejected", "public"),
            ("nonempty_0013_rejected", schema),
        ):
            try:
                load_legacy_0013_seed(engine, rejected_schema, store)
            except AssertionError:
                pass
            else:
                raise AssertionError("loader accepted unsafe target")
            assert snapshot() == before
            checks.append(name)
        run_migrations(migration_url.render_as_string(hide_password=False))
        assert snapshot() == before
        checks.append("all_19_table_legacy_rows_preserved_0013_to_0015")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0015_catalog_document_metadata"
            )
            assert connection.scalar(text("SELECT source_metadata FROM document_revisions")) == {}
            assert (
                connection.scalar(
                    text("SELECT extversion FROM pg_extension WHERE extname='vector'")
                )
                == "0.8.2"
            )
        try:
            load_legacy_0013_seed(engine, schema, store)
        except AssertionError:
            pass
        else:
            raise AssertionError("loader accepted a newer schema as a legacy target")
        assert snapshot() == before
        checks.append("head_schema_rejected_without_writes")
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()
print(
    json.dumps(
        {
            "checks_passed": len(checks),
            "checks": checks,
            "seed_sha256": hashlib.sha256(seed_bytes).hexdigest(),
            "row_counts": {name: len(value["rows"]) for name, value in rows.items()},
        }
    )
)
