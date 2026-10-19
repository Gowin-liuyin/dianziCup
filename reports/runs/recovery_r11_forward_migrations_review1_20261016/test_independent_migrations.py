"""Independent PostgreSQL cases for frozen forward DDL, history and service boundaries."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from alembic.operations import Operations
from sqlalchemy import MetaData, Table, create_engine, insert, inspect, select, text, update
from sqlalchemy.exc import IntegrityError
from tests.integration import test_r11_forward_rules_sbom_schema as history
from tests.integration import test_r11_pg_assessments as fixtures
from tests.r11_forward_fixtures import (
    HEAD,
    forbid_business_table_creation,
    forbid_metadata_creation,
    migrated_schema,
    owned_url,
)

from ai_intel.assessment.persistence_contracts import PreparedAssessment
from ai_intel.assessment.rule_persistence import RulePersistenceError, condition_rule_versions
from ai_intel.assets.sbom_persistence_models import asset_snapshot_sbom_sidecars
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.infrastructure.database import current_migration_revision, run_migrations
from ai_intel.knowledge.models import scope_epochs

pytestmark = pytest.mark.real_pg
NEW_TABLES = {table.name for table in history.TABLES}


@pytest.fixture(scope="module")
def own_engine():
    with migrated_schema() as (engine, _url, _schema):
        yield engine


@pytest.fixture()
def candidate(own_engine, tmp_path):
    return own_engine, fixtures.seed(own_engine, tmp_path)


@pytest.fixture()
def committed(own_engine, tmp_path):
    seeded = fixtures.seed(own_engine, tmp_path)
    fixtures.publish(own_engine, seeded)
    imported = fixtures.asset(own_engine, seeded)
    service = fixtures.assessor(own_engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    receipt = service.commit(prepared)
    return own_engine, seeded, imported, service, prepared, receipt


def rule_row(engine, seeded):
    with engine.connect() as connection:
        return dict(
            connection.execute(
                select(condition_rule_versions).where(
                    condition_rule_versions.c.rule_id == seeded["rule"].rule_id,
                    condition_rule_versions.c.version == 1,
                )
            )
            .mappings()
            .one()
        )


def mutate_rule(engine, seeded, values):
    with engine.begin() as connection:
        connection.execute(
            update(condition_rule_versions)
            .where(
                condition_rule_versions.c.rule_id == seeded["rule"].rule_id,
                condition_rule_versions.c.version == 1,
            )
            .values(**values)
        )


def test_real_empty_owned_database_public_upgrade_has_only_production_creation(monkeypatch):
    url = owned_url()
    engine = create_engine(url, hide_parameters=True)
    try:
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT current_schema()")) == "public"
            assert connection.scalar(text("SELECT to_regclass('public.alembic_version')")) is None
        monkeypatch.setattr(MetaData, "create_all", forbid_metadata_creation)
        monkeypatch.setattr(Table, "create", forbid_business_table_creation)
        run_migrations(url.render_as_string(hide_password=False))
        assert current_migration_revision(url.render_as_string(hide_password=False)) == HEAD
        assert set(inspect(engine).get_table_names(schema="public")) >= NEW_TABLES
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT count(*) FROM public.assessment_results")) == 0
            assert (
                connection.scalar(text("SELECT count(*) FROM public.asset_snapshot_sbom_sidecars"))
                == 0
            )
    finally:
        engine.dispose()


def test_intermediate_0021_namespace_fk_functions_and_order_are_exact():
    with migrated_schema("0020_hybrid_retrieval") as (engine, url, schema):
        old_tables = set(inspect(engine).get_table_names(schema=schema))
        with engine.connect() as connection:
            old_functions = set(
                connection.execute(
                    text(
                        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n "
                        "ON n.oid=p.pronamespace WHERE n.nspname=:schema"
                    ),
                    {"schema": schema},
                ).scalars()
            )
        run_migrations(url.render_as_string(hide_password=False), "0021_condition_assessments")
        assert set(inspect(engine).get_table_names(schema=schema)) - old_tables == NEW_TABLES - {
            "asset_snapshot_sbom_sidecars"
        }
        assert (
            current_migration_revision(url.render_as_string(hide_password=False))
            == "0021_condition_assessments"
        )
        with engine.connect() as connection:
            functions = (
                connection.execute(
                    text(
                        "SELECT p.proname FROM pg_proc p JOIN pg_namespace n "
                        "ON n.oid=p.pronamespace WHERE n.nspname=:schema"
                    ),
                    {"schema": schema},
                )
                .scalars()
                .all()
            )
            assert set(functions) - old_functions == {
                "r11_require_immutable_rule",
                "r11_require_append_only",
            }
            pairs = connection.execute(
                text(
                    "SELECT c.relname,n2.nspname FROM pg_constraint fk "
                    "JOIN pg_class c ON c.oid=fk.conrelid "
                    "JOIN pg_namespace n ON n.oid=c.relnamespace "
                    "JOIN pg_class parent ON parent.oid=fk.confrelid "
                    "JOIN pg_namespace n2 ON n2.oid=parent.relnamespace "
                    "WHERE n.nspname=:schema AND fk.contype='f'"
                ),
                {"schema": schema},
            ).all()
            assert all(
                parent_schema == schema for name, parent_schema in pairs if name in NEW_TABLES
            )
        run_migrations(url.render_as_string(hide_password=False), HEAD)
        with engine.connect() as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == HEAD
            assert (
                connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_trigger t JOIN pg_class c ON c.oid=t.tgrelid "
                        "JOIN pg_namespace n ON n.oid=c.relnamespace WHERE n.nspname=:schema "
                        "AND NOT t.tgisinternal AND c.relname = ANY(:names)"
                    ),
                    {"schema": schema, "names": sorted(NEW_TABLES)},
                )
                == 7
            )
        assert set(inspect(engine).get_table_names(schema=schema)) - old_tables == NEW_TABLES


def test_real_normal_alembic_failure_after_0022_table_preserves_0020_rows_and_stamp(monkeypatch):
    with migrated_schema("0020_hybrid_retrieval") as (engine, url, schema):
        identities, _asset, change = history.seed_history(engine)
        history.fill_0020_history(engine, identities, change)
        names = sorted(set(inspect(engine).get_table_names(schema=schema)) - {"alembic_version"})
        before = history.row_snapshot(engine, names)
        real_execute = Operations.execute

        def fail_on_sidecar_trigger(operation, statement, *arguments, **keywords):
            if "CREATE OR REPLACE FUNCTION prevent_sbom_sidecar_changes" in str(statement):
                raise RuntimeError("independent synthetic migration interruption")
            return real_execute(operation, statement, *arguments, **keywords)

        with monkeypatch.context() as patch:
            patch.setattr(Operations, "execute", fail_on_sidecar_trigger)
            with pytest.raises(RuntimeError, match="independent synthetic migration interruption"):
                run_migrations(url.render_as_string(hide_password=False))
        assert (
            current_migration_revision(url.render_as_string(hide_password=False))
            == "0020_hybrid_retrieval"
        )
        assert not NEW_TABLES.intersection(inspect(engine).get_table_names(schema=schema))
        assert history.row_snapshot(engine, names) == before
        run_migrations(url.render_as_string(hide_password=False))
        run_migrations(url.render_as_string(hide_password=False))
        engine.dispose()
        restarted = create_engine(engine.url, hide_parameters=True)
        try:
            assert history.row_snapshot(restarted, names) == before
            assert current_migration_revision(url.render_as_string(hide_password=False)) == HEAD
            history.retain_history_evidence(
                "independent_normal_upgrade_rollback_restart",
                before,
                history.row_snapshot(restarted, names),
                schema,
            )
        finally:
            restarted.dispose()


@pytest.mark.parametrize("target", ["published", "retired", "invented"])
def test_rule_candidate_cannot_skip_forward_lifecycle(candidate, target):
    engine, seeded = candidate
    before = rule_row(engine, seeded)
    with pytest.raises(IntegrityError) as failure:
        mutate_rule(engine, seeded, {"status": target, "published_at": datetime.now(UTC)})
    assert failure.value.orig.sqlstate == "23514"
    assert rule_row(engine, seeded) == before


@pytest.mark.parametrize(
    "field", ["published_at", "published_by", "rule_payload", "condition_sha256"]
)
def test_published_rule_fields_are_write_once(candidate, field):
    engine, seeded = candidate
    fixtures.publish(engine, seeded)
    before = rule_row(engine, seeded)
    changes = {
        "published_at": before["published_at"] + timedelta(seconds=1),
        "published_by": seeded["asset_actor"].user_id,
        "rule_payload": {"altered": True},
        "condition_sha256": "a" * 64,
    }
    with pytest.raises(IntegrityError) as failure:
        mutate_rule(engine, seeded, {field: changes[field]})
    assert failure.value.orig.sqlstate == "23514"
    assert rule_row(engine, seeded) == before


def test_retired_rule_cannot_revive_or_rewrite_retirement(candidate):
    engine, seeded = candidate
    fixtures.publish(engine, seeded)
    mutate_rule(engine, seeded, {"status": "retired", "retired_at": datetime.now(UTC)})
    before = rule_row(engine, seeded)
    for values in (
        {"status": "published", "retired_at": None},
        {"retired_at": before["retired_at"] + timedelta(seconds=1)},
    ):
        with pytest.raises(IntegrityError) as failure:
            mutate_rule(engine, seeded, values)
        assert failure.value.orig.sqlstate == "23514"
        assert rule_row(engine, seeded) == before


def test_partial_unique_rejects_second_published_then_keeps_retired_history(candidate):
    engine, seeded = candidate
    fixtures.publish(engine, seeded)
    before = rule_row(engine, seeded)
    second = dict(before, version=2)
    with pytest.raises(IntegrityError) as failure, engine.begin() as connection:
        connection.execute(insert(condition_rule_versions).values(**second))
    assert failure.value.orig.sqlstate == "23505"
    assert failure.value.orig.diag.constraint_name == "uq_current_published_rule_family"
    mutate_rule(engine, seeded, {"status": "retired", "retired_at": datetime.now(UTC)})
    with engine.begin() as connection:
        connection.execute(insert(condition_rule_versions).values(**second))
    with engine.connect() as connection:
        assert connection.execute(
            select(condition_rule_versions.c.version, condition_rule_versions.c.status)
            .where(condition_rule_versions.c.rule_id == seeded["rule"].rule_id)
            .order_by(condition_rule_versions.c.version)
        ).all() == [(1, "retired"), (2, "published")]


def test_asset_current_change_does_not_rewrite_saved_assessment_or_replay_current(committed):
    engine, seeded, imported, service, prepared, receipt = committed
    before = history.row_snapshot(engine, ["assessment_results", "assessment_scope_watches"])
    new_snapshot = fixtures.asset(engine, seeded, version="1.4.2", asset_id=imported.asset_id)
    assert new_snapshot.snapshot.snapshot_id != imported.snapshot.snapshot_id
    assert service.read(receipt.assessment_id).freshness == "stale"
    replay = service.commit(prepared)
    assert (
        replay.reused
        and replay.assessment_id == receipt.assessment_id
        and replay.freshness == "stale"
    )
    assert (
        history.row_snapshot(engine, ["assessment_results", "assessment_scope_watches"]) == before
    )


def test_nonpublic_scope_epoch_change_is_not_hidden_by_null_public_epoch(committed):
    engine, seeded, _imported, service, prepared, receipt = committed
    assert prepared.inputs.scope_epoch_map["public"] is None
    before = history.row_snapshot(engine, ["assessment_results", "assessment_scope_watches"])
    with engine.begin() as connection:
        result = connection.execute(
            update(scope_epochs)
            .where(scope_epochs.c.scope_key == "tenant:" + seeded["tenant"])
            .values(epoch=scope_epochs.c.epoch + 1)
        )
        assert result.rowcount == 1
    assert service.read(receipt.assessment_id).freshness == "stale"
    replay = service.commit(prepared)
    assert replay.reused and replay.freshness == "stale"
    assert (
        history.row_snapshot(engine, ["assessment_results", "assessment_scope_watches"]) == before
    )


def test_forged_preparation_does_not_add_assessment_rows(committed):
    engine, _seeded, _imported, service, prepared, _receipt = committed
    before = history.row_snapshot(engine, ["assessment_results", "assessment_scope_watches"])
    forged = PreparedAssessment.model_validate(
        prepared.model_copy(update={"input_digest": "f" * 64}).model_dump()
    )
    with pytest.raises(RulePersistenceError, match="assessment_preparation_receipt_mismatch"):
        service.commit(forged)
    assert (
        history.row_snapshot(engine, ["assessment_results", "assessment_scope_watches"]) == before
    )


def test_cross_tenant_assessment_read_has_only_not_found(committed):
    engine, _seeded, _imported, _service, _prepared, receipt = committed
    _scope, token = fixtures.actor(engine, "independent-other-tenant-" + uuid4().hex)
    service = fixtures.AssessmentService(engine, token, _seeded["store"])
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        service.read(receipt.assessment_id)


@pytest.mark.parametrize(
    "field,value",
    [("adapter_version", ""), ("spec_version", "x" * 201), ("canonical_payload", None)],
)
def test_sidecar_version_lengths_and_json_null_are_rejected(own_engine, field, value):
    access = history.inventory_fixture.scope(own_engine)
    imported = history.inventory_fixture.save(own_engine, access)
    values = dict(
        snapshot_id=imported.snapshot.snapshot_id,
        asset_id=imported.asset_id,
        tenant_id=access.tenant_id,
        adapter_version="independent-fixture-1",
        spec_version="1.5",
        sidecar_sha256="a" * 64,
        combined_semantic_sha256="b" * 64,
        canonical_payload={"synthetic": True},
    )
    values[field] = value
    before = history.row_snapshot(own_engine, ["asset_snapshots", "asset_snapshot_sbom_sidecars"])
    with pytest.raises(IntegrityError) as failure, own_engine.begin() as connection:
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(**values))
    assert failure.value.orig.sqlstate in {"23514", "23502"}
    assert (
        history.row_snapshot(own_engine, ["asset_snapshots", "asset_snapshot_sbom_sidecars"])
        == before
    )


def test_sidecar_existing_snapshot_wrong_asset_is_composite_fk_rejected(own_engine):
    access = history.inventory_fixture.scope(own_engine)
    first = history.inventory_fixture.save(own_engine, access)
    second = history.inventory_fixture.save(own_engine, access)
    assert first.asset_id != second.asset_id
    values = dict(
        snapshot_id=first.snapshot.snapshot_id,
        asset_id=second.asset_id,
        tenant_id=access.tenant_id,
        adapter_version="independent-fixture-1",
        spec_version="1.5",
        sidecar_sha256="a" * 64,
        combined_semantic_sha256="b" * 64,
        canonical_payload={"synthetic": True},
    )
    before = history.row_snapshot(own_engine, ["asset_snapshots", "asset_snapshot_sbom_sidecars"])
    with pytest.raises(IntegrityError) as failure, own_engine.begin() as connection:
        connection.execute(insert(asset_snapshot_sbom_sidecars).values(**values))
    assert failure.value.orig.sqlstate == "23503"
    assert failure.value.orig.diag.constraint_name == "fk_sbom_sidecar_snapshot_tenant"
    assert (
        history.row_snapshot(own_engine, ["asset_snapshots", "asset_snapshot_sbom_sidecars"])
        == before
    )
