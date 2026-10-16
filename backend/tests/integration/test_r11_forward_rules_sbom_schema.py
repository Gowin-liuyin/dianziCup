"""Production DDL, old-byte preservation, transaction rollback and SBOM DB boundaries."""

import hashlib
import importlib.util
import json
import os
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4

import pytest
from alembic.config import Config
from alembic.migration import MigrationContext
from alembic.operations import Operations
from alembic.script import ScriptDirectory
from pydantic import SecretStr
from sqlalchemy import (
    CheckConstraint,
    UniqueConstraint,
    create_engine,
    insert,
    inspect,
    select,
    text,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.exc import IntegrityError
from tests.integration import test_r11_pg_assessments as rule_fixture
from tests.integration import test_t24_asset_inventory as inventory_fixture
from tests.r11_forward_fixtures import HEAD, migrated_schema, owned_url
from tests.r12_hybrid_fixtures import NOW, record_change, seed_fact

from ai_intel.assessment.assessment_persistence import ASSESSMENT_TABLES
from ai_intel.assessment.rule_persistence import RULE_TABLES
from ai_intel.assets.sbom_parser import SBOM_ADAPTER_VERSION, parse_sbom
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.infrastructure.database import MIGRATIONS_DIR, run_migrations
from ai_intel.retrieval.hybrid_schema import hybrid_chunks, hybrid_index_generations

pytestmark = pytest.mark.real_pg
TABLES = (*RULE_TABLES, *ASSESSMENT_TABLES, asset_snapshot_sbom_sidecars)


@pytest.fixture(scope="module")
def schema_engine():
    with migrated_schema() as (engine, _url, _schema):
        yield engine


@pytest.fixture(autouse=True)
def sensitive_connection(register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(owned_url().password))


@pytest.mark.parametrize("table", TABLES, ids=lambda table: table.name)
def test_full_columns_types_keys_checks_and_foreign_keys_match_metadata(schema_engine, table):
    inspector = inspect(schema_engine)
    actual_columns = inspector.get_columns(table.name)
    assert [column["name"] for column in actual_columns] == list(table.columns.keys())
    dialect = postgresql.dialect()
    for expected, actual in zip(table.columns, actual_columns, strict=True):
        assert actual["nullable"] == expected.nullable
        assert str(actual["type"].compile(dialect=dialect)) == str(
            expected.type.compile(dialect=dialect)
        )
        assert actual["default"] is None
    assert inspector.get_pk_constraint(table.name)["constrained_columns"] == [
        column.name for column in table.primary_key.columns
    ]
    expected_foreign_keys = {
        (
            tuple(element.parent.name for element in constraint.elements),
            constraint.elements[0].column.table.name,
            tuple(element.column.name for element in constraint.elements),
        )
        for constraint in table.foreign_key_constraints
    }
    actual_foreign_keys = {
        (
            tuple(constraint["constrained_columns"]),
            constraint["referred_table"],
            tuple(constraint["referred_columns"]),
        )
        for constraint in inspector.get_foreign_keys(table.name)
    }
    assert actual_foreign_keys == expected_foreign_keys
    assert {item["name"] for item in inspector.get_check_constraints(table.name)} == {
        item.name for item in table.constraints if isinstance(item, CheckConstraint)
    }
    assert {
        (item["name"], tuple(item["column_names"]))
        for item in inspector.get_unique_constraints(table.name)
    } == {
        (item.name, tuple(column.name for column in item.columns))
        for item in table.constraints
        if isinstance(item, UniqueConstraint)
    }
    assert {
        item["name"]
        for item in inspector.get_indexes(table.name)
        if not item.get("duplicates_constraint")
    } == {item.name for item in table.indexes}


def test_all_immutable_triggers_and_partial_unique_are_installed(schema_engine):
    with schema_engine.connect() as connection:
        triggers = connection.execute(
            text(
                "SELECT c.relname,t.tgname,t.tgtype,t.tgenabled,p.proname "
                "FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                "JOIN pg_namespace n ON n.oid=c.relnamespace JOIN pg_proc p ON p.oid=t.tgfoid "
                "WHERE n.nspname=current_schema() AND NOT t.tgisinternal"
            )
        ).all()
    for table in TABLES:
        function = (
            "prevent_sbom_sidecar_changes"
            if table.name == "asset_snapshot_sbom_sidecars"
            else "r11_require_immutable_rule"
            if table.name == "condition_rule_versions"
            else "r11_require_append_only"
        )
        assert (table.name, table.name + "_immutable", 27, "O", function) in triggers
    index = next(
        item
        for item in inspect(schema_engine).get_indexes("condition_rule_versions")
        if item["name"] == "uq_current_published_rule_family"
    )
    assert index["unique"] and index["column_names"] == ["rule_id"]
    assert "published" in str(index["dialect_options"]["postgresql_where"])


def row_snapshot(engine, names):
    with engine.connect() as connection:
        return {
            name: sorted(
                connection.execute(text(f'SELECT to_jsonb(row)::text FROM "{name}" row')).scalars()
            )
            for name in names
        }


def retain_history_evidence(label, before, after, schema):
    assert after == before
    records = {
        name: {
            "count": len(rows),
            "raw_json": rows,
            "sha256": hashlib.sha256(
                json.dumps(rows, ensure_ascii=False, separators=(",", ":")).encode()
            ).hexdigest(),
        }
        for name, rows in before.items()
    }
    directory = os.environ.get("R11_FORWARD_EVIDENCE_DIR")
    if directory:
        path = Path(directory) / (label + "_" + schema + ".json")
        assert not path.exists()
        path.write_text(
            json.dumps(
                {"schema": schema, "tables": records, "all_raw_json_equal": True},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def seed_history(engine):
    identities = seed_fact(engine, "Synthetic preserved history: 中文 😀 immutable evidence")
    access = inventory_fixture.scope(engine)
    imported = inventory_fixture.save(engine, access)
    change = record_change(engine)
    return identities, imported, change


def fill_0020_history(engine, identities, change):
    with engine.begin() as connection:
        connection.execute(
            insert(hybrid_index_generations).values(
                generation_id="retained-generation",
                index_name="dianzi_test_retained_generation",
                model_version="explicit-synthetic-vector",
                dimension=384,
                state="ready",
                created_at=NOW,
            )
        )
        connection.execute(
            insert(hybrid_chunks).values(
                generation_id="retained-generation",
                chunk_id="retained-chunk",
                **{
                    key: identities[key]
                    for key in (
                        "evidence_id",
                        "revision_id",
                        "document_id",
                        "source_id",
                        "event_id",
                        "claim_id",
                    )
                },
                scope_key="public",
                visibility="public",
                tenant_id=None,
                available_at=NOW,
                start_offset=0,
                end_offset=1,
                chunk_text="S",
                text_sha256=hashlib.sha256(b"S").hexdigest(),
                source_uri="https://example.invalid/synthetic",
                locator="synthetic-offset",
                model_version="explicit-synthetic-vector",
                embedding=[1.0] + [0.0] * 383,
                indexed_epoch=1,
                indexed_at=NOW,
            )
        )
        connection.execute(
            text(
                "INSERT INTO hybrid_index_watermarks VALUES "
                "('retained-generation','public',1,:outbox,:now)"
            ),
            {"outbox": change.outbox_id, "now": NOW},
        )
        connection.execute(
            text(
                "INSERT INTO hybrid_index_receipts VALUES "
                "('retained-generation',:outbox,'public',1,1,:digest,:now)"
            ),
            {"outbox": change.outbox_id, "digest": "a" * 64, "now": NOW},
        )


@pytest.mark.parametrize("start", ["0019_aggregate_observations", "0020_hybrid_retrieval"])
def test_filled_history_forward_20_21_22_and_restart_are_byte_preserving(start, monkeypatch):
    with migrated_schema(start) as (engine, url, schema):
        identities, _imported, change = seed_history(engine)
        if start == "0020_hybrid_retrieval":
            fill_0020_history(engine, identities, change)
        names = sorted(set(inspect(engine).get_table_names(schema=schema)) - {"alembic_version"})
        before = row_snapshot(engine, names)
        assert (
            before["asset_snapshots"] and before["document_revisions"] and before["outbox_events"]
        )
        if start == "0019_aggregate_observations":
            run_migrations(url.render_as_string(hide_password=False), "0020_hybrid_retrieval")
            assert row_snapshot(engine, names) == before
            fill_0020_history(engine, identities, change)
            names = sorted(
                set(inspect(engine).get_table_names(schema=schema)) - {"alembic_version"}
            )
            before = row_snapshot(engine, names)
        for revision in ("0021_condition_assessments", HEAD):
            run_migrations(url.render_as_string(hide_password=False), revision)
            assert row_snapshot(engine, names) == before
        engine.dispose()
        run_migrations(url.render_as_string(hide_password=False))
        restarted = create_engine(engine.url, hide_parameters=True)
        try:
            assert row_snapshot(restarted, names) == before
            with restarted.connect() as connection:
                assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            retain_history_evidence(
                "history_" + start[:4], before, row_snapshot(restarted, names), schema
            )
        finally:
            restarted.dispose()


def revision_module(revision):
    spec = importlib.util.spec_from_file_location(
        revision, MIGRATIONS_DIR / "versions" / (revision + ".py")
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_pg_ddl_and_version_transaction_rolls_back_without_downgrade():
    with migrated_schema("0020_hybrid_retrieval") as (engine, url, schema):
        identities, _imported, change = seed_history(engine)
        fill_0020_history(engine, identities, change)
        names = sorted(set(inspect(engine).get_table_names(schema=schema)) - {"alembic_version"})
        before = row_snapshot(engine, names)
        config = Config()
        config.set_main_option("script_location", str(MIGRATIONS_DIR))
        scripts = ScriptDirectory.from_config(config)
        with (
            pytest.raises(RuntimeError, match="synthetic deployment failure"),
            engine.connect() as connection,
            connection.begin(),
        ):
            context = MigrationContext.configure(connection)
            with Operations.context(context):
                revision_module("0021_condition_assessments").upgrade()
                revision_module(HEAD).upgrade()
            context.stamp(scripts, HEAD)
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            raise RuntimeError("synthetic deployment failure")
        with engine.connect() as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version"))
                == "0020_hybrid_retrieval"
            )
            assert connection.scalar(text("SELECT to_regclass('condition_rule_versions')")) is None
            assert (
                connection.scalar(text("SELECT to_regclass('asset_snapshot_sbom_sidecars')"))
                is None
            )
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_proc p "
                        "JOIN pg_namespace n ON n.oid=p.pronamespace "
                        "WHERE n.nspname=current_schema() AND p.proname IN "
                        "('r11_require_append_only','r11_require_immutable_rule','prevent_sbom_sidecar_changes')"
                    )
                )
                == 0
            )
        assert row_snapshot(engine, names) == before
        run_migrations(url.render_as_string(hide_password=False))
        retain_history_evidence(
            "rollback_then_forward", before, row_snapshot(engine, names), schema
        )


@pytest.fixture()
def sidecar_case(schema_engine):
    access = inventory_fixture.scope(schema_engine)
    imported = inventory_fixture.save(schema_engine, access)
    document = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "version": 1,
        "components": [
            {
                "type": "library",
                "name": "langchain",
                "version": "1.0",
                "purl": "pkg:pypi/langchain@1.0",
                "bom-ref": "component-a",
            }
        ],
        "dependencies": [{"ref": "component-a", "dependsOn": []}],
    }
    raw = json.dumps(document, ensure_ascii=False).encode()
    parsed = parse_sbom(
        raw,
        sbom_format="cyclonedx_json",
        scope=access,
        authorized_asset_tenant_id=access.tenant_id,
        asset_id=imported.asset_id,
        snapshot_number=1,
        source_version="synthetic-cdx-1",
        observed_at=NOW,
        recorded_at=NOW,
    )
    values = dict(
        snapshot_id=imported.snapshot.snapshot_id,
        asset_id=imported.asset_id,
        tenant_id=access.tenant_id,
        adapter_version=SBOM_ADAPTER_VERSION,
        spec_version=parsed.spec_version,
        sidecar_sha256=parsed.sidecar_sha256,
        combined_semantic_sha256=parsed.combined_semantic_sha256,
        canonical_payload=document,
    )
    return schema_engine, values


def test_canonical_sidecar_hashes_payload_and_original_snapshot_are_preserved(sidecar_case):
    engine, values = sidecar_case
    before = row_snapshot(engine, ["asset_snapshots"])
    with engine.begin() as connection:
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(**values))
    with engine.connect() as connection:
        row = (
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id == values["snapshot_id"]
                )
            )
            .mappings()
            .one()
        )
    assert dict(row) == values
    expected_digest = hashlib.sha256(
        json.dumps(
            values["canonical_payload"], ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()
    assert row["sidecar_sha256"] == expected_digest
    assert row_snapshot(engine, ["asset_snapshots"]) == before


@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "foreign-tenant"),
        ("asset_id", "foreign-asset"),
        ("snapshot_id", "absent-snapshot"),
        ("adapter_version", ""),
        ("spec_version", ""),
        ("sidecar_sha256", "A" * 64),
        ("sidecar_sha256", "a" * 63),
        ("combined_semantic_sha256", "z" * 64),
        ("canonical_payload", []),
    ],
)
def test_security_sidecar_scope_identity_hash_and_json_checks_reject(sidecar_case, field, value):
    engine, values = sidecar_case
    before = row_snapshot(engine, ["asset_snapshot_sbom_sidecars", "asset_snapshots"])
    with pytest.raises(IntegrityError), engine.begin() as connection:
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(**{**values, field: value}))
    assert row_snapshot(engine, list(before)) == before


@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_security_sidecar_is_immutable_with_noop_update_also_rejected(sidecar_case, operation):
    engine, values = sidecar_case
    with engine.begin() as connection:
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(**values))
    before = row_snapshot(engine, ["asset_snapshot_sbom_sidecars"])
    statement = (
        "UPDATE asset_snapshot_sbom_sidecars SET canonical_payload=canonical_payload"
        if operation == "UPDATE"
        else "DELETE FROM asset_snapshot_sbom_sidecars"
    )
    with (
        pytest.raises(IntegrityError, match="SBOM sidecars are immutable"),
        engine.begin() as connection,
    ):
        connection.execute(
            text(statement + " WHERE snapshot_id=:snapshot"), {"snapshot": values["snapshot_id"]}
        )
    assert row_snapshot(engine, list(before)) == before


def test_sidecar_duplicate_concurrent_insert_keeps_single_receipt(sidecar_case):
    engine, values = sidecar_case

    def insert_once(_attempt):
        try:
            with engine.begin() as connection:
                connection.execute(insert(asset_snapshot_sbom_sidecars).values(**values))
            return "inserted"
        except IntegrityError as error:
            assert error.orig.sqlstate == "23505"
            return "duplicate"

    with ThreadPoolExecutor(max_workers=2) as executor:
        assert sorted(executor.map(insert_once, range(2))) == ["duplicate", "inserted"]
    with engine.connect() as connection:
        assert (
            connection.execute(
                select(asset_snapshot_sbom_sidecars).where(
                    asset_snapshot_sbom_sidecars.c.snapshot_id == values["snapshot_id"]
                )
            )
            .mappings()
            .one()
            == values
        )


def test_sidecar_transaction_rollback_leaves_snapshot_bytes_unchanged(sidecar_case):
    engine, values = sidecar_case
    before = row_snapshot(engine, ["asset_snapshot_sbom_sidecars", "asset_snapshots"])
    with (
        pytest.raises(RuntimeError, match="synthetic sidecar failure"),
        engine.begin() as connection,
    ):
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(**values))
        raise RuntimeError("synthetic sidecar failure")
    assert row_snapshot(engine, list(before)) == before


@pytest.fixture()
def assessed_case(schema_engine, tmp_path):
    seeded = rule_fixture.seed(schema_engine, tmp_path)
    rule_fixture.publish(schema_engine, seeded)
    imported = rule_fixture.asset(schema_engine, seeded)
    service = rule_fixture.assessor(schema_engine, seeded)
    receipt = service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )
    return schema_engine, seeded, receipt


@pytest.mark.parametrize("table", (*RULE_TABLES, *ASSESSMENT_TABLES), ids=lambda table: table.name)
@pytest.mark.parametrize("operation", ["UPDATE", "DELETE"])
def test_security_every_history_table_rejects_content_update_and_delete(
    assessed_case, table, operation
):
    engine, seeded, receipt = assessed_case
    key = "assessment_id" if table.name.startswith("assessment_") else "rule_id"
    identity = receipt.assessment_id if key == "assessment_id" else seeded["rule"].rule_id
    if operation == "DELETE":
        statement = f'DELETE FROM "{table.name}" WHERE "{key}"=:identity'
    elif table.name == "condition_rule_versions":
        statement = (
            "UPDATE condition_rule_versions SET condition_sha256=:digest WHERE rule_id=:identity"
        )
    else:
        statement = f'UPDATE "{table.name}" SET "{key}"="{key}" WHERE "{key}"=:identity'
    before = row_snapshot(engine, [table.name])
    with pytest.raises(IntegrityError) as failure, engine.begin() as connection:
        connection.execute(text(statement), {"identity": identity, "digest": "f" * 64})
    assert failure.value.orig.sqlstate == "23514"
    assert row_snapshot(engine, [table.name]) == before


@pytest.mark.parametrize(
    "table,field,value",
    [
        (RULE_TABLES[1], "evidence_id", "absent-evidence"),
        (RULE_TABLES[2], "evidence_id", "absent-bound-evidence"),
        (RULE_TABLES[3], "rule_version", 99999),
        (ASSESSMENT_TABLES[0], "tenant_id", "foreign-tenant"),
        (ASSESSMENT_TABLES[1], "assessment_id", "absent-assessment"),
    ],
    ids=[
        "binding-evidence",
        "review-binding",
        "validation-version",
        "assessment-tenant",
        "watch-assessment",
    ],
)
def test_security_new_foreign_keys_reject_missing_or_cross_tenant_parent(
    assessed_case, table, field, value
):
    engine, seeded, receipt = assessed_case
    key = "assessment_id" if table.name.startswith("assessment_") else "rule_id"
    identity = receipt.assessment_id if key == "assessment_id" else seeded["rule"].rule_id
    with engine.connect() as connection:
        values = dict(
            connection.execute(select(table).where(table.c[key] == identity)).mappings().first()
        )
    if table.name == "rule_leaf_reviews":
        values["review_id"] = uuid4().hex
    elif table.name == "rule_validation_receipts":
        values["receipt_id"] = uuid4().hex
    elif table.name == "assessment_results":
        values["assessment_id"] = uuid4().hex
        values["input_digest"] = hashlib.sha256(uuid4().bytes).hexdigest()
    values[field] = value
    before = row_snapshot(engine, [table.name])
    with pytest.raises(IntegrityError) as failure, engine.begin() as connection:
        connection.execute(insert(table).values(**values))
    assert failure.value.orig.sqlstate == "23503"
    assert row_snapshot(engine, [table.name]) == before


@pytest.mark.parametrize(
    "field,value,constraint",
    [
        ("version", 0, "ck_condition_rule_version"),
        ("visibility", "secret", ("ck_condition_rule_visibility", "ck_condition_rule_tenant")),
        ("tenant_id", None, "ck_condition_rule_tenant"),
        ("rule_kind", "arbitrary_python", "ck_condition_rule_kind"),
        ("status", "invented", "ck_condition_rule_status"),
        ("condition_sha256", "A" * 64, "ck_rule_condition_digest"),
        ("rule_payload", [], "ck_rule_payload"),
    ],
)
def test_security_rule_scope_type_and_payload_checks_are_real_pg_constraints(
    assessed_case, field, value, constraint
):
    engine, seeded, _receipt = assessed_case
    with engine.connect() as connection:
        values = dict(
            connection.execute(
                select(RULE_TABLES[0]).where(RULE_TABLES[0].c.rule_id == seeded["rule"].rule_id)
            )
            .mappings()
            .one()
        )
    values["rule_id"] = uuid4().hex
    values[field] = value
    with pytest.raises(IntegrityError) as failure, engine.begin() as connection:
        connection.execute(insert(RULE_TABLES[0]).values(**values))
    assert failure.value.orig.sqlstate == "23514"
    expected_constraints = (constraint,) if isinstance(constraint, str) else constraint
    assert failure.value.orig.diag.constraint_name in expected_constraints
