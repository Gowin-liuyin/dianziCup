"""Independently check frozen seed provenance and every old row across forward migration."""

import ast
import hashlib
import importlib.util
import json
import os
import subprocess
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.schema import CreateSchema, DropSchema

from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.database import run_migrations

ROOT = Path(__file__).resolve().parents[3]
RUN = Path(__file__).resolve().parent
BASE = "1927eeb00a7e0c1335f76340b0382f46102f08f2"
PRE_SEED = "7b8103e6d91a7274bcfb661d8e6f1d5b7180be17"
TEST = "backend/tests/integration/test_r05_vector_persistence.py"
SEED = ROOT / "fixtures/recorded/r05_legacy_0013_vllm_public_v1.json"


def git_bytes(revision, path):
    return subprocess.check_output(["git", "show", f"{revision}:{path}"], cwd=ROOT)


def test_nodes(source):
    return {node.name: ast.dump(node, include_attributes=False) for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}


def must_reject(action):
    try:
        action()
    except AssertionError:
        return
    raise AssertionError("unsafe seed input accepted")


def main():
    current = (ROOT / TEST).read_bytes()
    assert test_nodes(current) == test_nodes(git_bytes(PRE_SEED, TEST))
    old_tests = test_nodes(git_bytes(BASE, TEST))
    new_tests = test_nodes(current)
    changed_tests = [name for name, value in old_tests.items() if value != new_tests[name]]
    assert changed_tests == ["test_upgrade_preserves_immutable_evidence_and_real_extension"]
    question = "backend/tests/integration/test_r05_question_api_pg.py"
    assert git_bytes(BASE, question) == git_bytes("HEAD", question)
    seed_bytes = SEED.read_bytes().replace(b"\r\n", b"\n")
    assert hashlib.sha256(seed_bytes).hexdigest() == "6170ce55e63a70a557f62fc79213d20b596222220e2a04d5e050e67b7e188336"
    seed = json.loads(seed_bytes)
    assert seed["writer_commit"] == BASE
    manifest = json.loads((ROOT / "reports/runs/recovery_r06_legacy_migration_fixture_20261015/artifact_manifest.json").read_text())
    provenance = {}
    for name, item in manifest["original_writer_import_chain"].items():
        physical = Path(item["path"]).read_bytes()
        assert hashlib.sha256(physical).hexdigest() == item["sha256"]
        relative = "backend/src/" + name.replace(".", "/") + ".py"
        assert physical.replace(b"\r\n", b"\n") == git_bytes(BASE, relative)
        provenance[name] = item["sha256"]
    assert sum(len(table["rows"]) for table in seed["tables"].values()) == 154
    assert len(seed["tables"]) == 19
    assert all(table["rows"] for table in seed["tables"].values())
    assert not {"users", "sessions", "auth_sessions", "secrets"} & set(seed["tables"])
    for table in seed["tables"].values():
        for row in table["rows"]:
            assert "tenant_id" not in row or row["tenant_id"] is None
            assert "visibility" not in row or row["visibility"] == "public"
            assert "scope_key" not in row or row["scope_key"] == "public"
    specification = importlib.util.spec_from_file_location("review_vector_seed", ROOT / TEST)
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    assert set(module.LEGACY_SEED_TABLES) == set(seed["tables"])
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_r05_pgvector_20261015"
    schema = "test_r05_review_seed_" + uuid4().hex
    base = create_engine(url)
    with base.begin() as connection:
        connection.execute(CreateSchema(schema))
    migration_url = url.update_query_dict({"options": f"-c search_path={schema} -c statement_timeout=15000"})
    runtime_url = migration_url.update_query_dict({"options": f"-c search_path={schema},public -c statement_timeout=15000"})
    engine = create_engine(runtime_url)
    checks = []
    try:
        run_migrations(migration_url.render_as_string(hide_password=False), "0013_revision_source_metadata")
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT n.nspname FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace WHERE c.oid=to_regclass('alembic_version')")) == schema
        with TemporaryDirectory(prefix="r06-review-seed-") as folder:
            store = ContentStore(Path(folder))
            must_reject(lambda: module.load_legacy_0013_seed(engine, "public", store))
            checks.append("public_schema_rejected")
            original_read = Path.read_bytes

            def changed_seed(path):
                original = original_read(path)
                return original + b" " if path.resolve() == SEED.resolve() else original

            with patch.object(Path, "read_bytes", changed_seed):
                must_reject(lambda: module.load_legacy_0013_seed(engine, schema, store))
            checks.append("tampered_seed_rejected")
            source_path = ROOT / "fixtures/recorded/vllm_vendor_20261015_public.json"

            def changed_source(path):
                original = original_read(path)
                return original + b" " if path.resolve() == source_path.resolve() else original

            with patch.object(Path, "read_bytes", changed_source):
                must_reject(lambda: module.load_legacy_0013_seed(engine, schema, store))
            checks.append("tampered_source_rejected")
            tables = module.load_legacy_0013_seed(engine, schema, store)
            checks.append("frozen_seed_loaded_0013")
            for digest, payload in seed["content_payloads_utf8"].items():
                assert store.read_verified(digest) == payload.encode("utf-8")
            checks.append("actual_content_objects_verified")
            with engine.connect() as connection:
                counts = {table.name: connection.scalar(select(func.count()).select_from(table)) for table in tables}
                before = tuple(tuple(connection.execute(select(table).order_by(*table.primary_key.columns))) for table in tables)
            must_reject(lambda: module.load_legacy_0013_seed(engine, schema, store))
            checks.append("nonempty_schema_rejected")
            run_migrations(migration_url.render_as_string(hide_password=False))
            with engine.connect() as connection:
                after = tuple(tuple(connection.execute(select(table).order_by(*table.primary_key.columns))) for table in tables)
                assert before == after
                assert connection.scalar(text("SELECT source_metadata FROM document_revisions")) == {}
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0015_catalog_document_metadata"
            checks.append("all_19_tables_154_old_rows_and_columns_equal_after_upgrade")
            must_reject(lambda: module.load_legacy_0013_seed(engine, schema, store))
            checks.append("head_schema_rejected")
            summary = {"schema": schema, "migration_search_path": schema, "runtime_search_path": schema + ",public", "checks": checks, "table_counts": counts, "total_rows": sum(counts.values()), "old_writer_hashes": provenance, "seed_lf_sha256": hashlib.sha256(seed_bytes).hexdigest(), "original_test_functions_preserved_since_7b": True, "baseline_changed_test": changed_tests, "question_blob_unchanged": True}
            (RUN / "seed_independent_verification.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
            print(json.dumps(summary, indent=2))
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


if __name__ == "__main__":
    main()
