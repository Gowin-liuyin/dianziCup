"""Independent negative cases exercise final-state triggers and JSON/hash integrity."""

import hashlib
import importlib.util
import json
import sys
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from review_runner import ROOT, RUN
from sqlalchemy import insert, inspect, select, update
from sqlalchemy.exc import IntegrityError

from ai_intel.assets.aggregate_observations import total_result
from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.assets.aggregate_repository import (
    AggregatePersistenceError,
    AggregateServerPolicy,
    PostgresAggregateRepository,
)
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.domain.access import AccessScope, Role
from ai_intel.enrichment.job_models import enrichment_job_steps, enrichment_workflows
from ai_intel.infrastructure.database import run_migrations

INTEGRATION = ROOT / "backend/tests/integration"
sys.path.insert(0, str(INTEGRATION))


def load_original(name, filename):
    spec = importlib.util.spec_from_file_location(name, INTEGRATION / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


INVENTORY = load_original("unchanged_inventory_negatives", "test_t24_asset_inventory.py")
METADATA = load_original("unchanged_0017_metadata", "test_r07_enrichment_job_metadata_pg.py")
test_workflow_incomplete_or_invalid_identity_is_rejected = (
    METADATA.test_workflow_incomplete_or_invalid_identity_is_rejected
)
test_step_invalid_nullable_combinations_do_not_bypass_pg_checks = (
    METADATA.test_step_invalid_nullable_combinations_do_not_bypass_pg_checks
)
test_external_reservation_does_not_wait_for_the_handler_job_row = (
    METADATA.test_external_reservation_does_not_wait_for_the_handler_job_row
)


@pytest.fixture
def catalog_engine(migrated_engine):
    from sqlalchemy import create_engine

    schema = "review1_metadata_" + uuid4().hex
    with migrated_engine.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    isolated = migrated_engine.url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, hide_parameters=True)
    try:
        yield engine
    finally:
        engine.dispose()


def test_original_0017_metadata_tables_keep_job_authority(migrated_engine):
    inspector = inspect(migrated_engine)
    for name in ("enrichment_workflows", "enrichment_job_steps"):
        columns = {row["name"] for row in inspector.get_columns(name)}
        assert "status" not in columns
    for filename in (
        "backend/migrations/versions/0017_enrichment_job_workflows.py",
        "backend/src/ai_intel/enrichment/job_models.py",
        "backend/src/ai_intel/enrichment/job_contracts.py",
        "backend/tests/integration/test_r07_enrichment_job_metadata_pg.py",
    ):
        import subprocess

        original = subprocess.run(
            ["git", "show", "281371b072a696d972aa3c38519b8646393c98e2:" + filename],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        current = subprocess.run(
            ["git", "show", "99fec14d1a64f9c5adaa5beb294e804da3e1d18d:" + filename],
            cwd=ROOT,
            capture_output=True,
            check=True,
        ).stdout
        assert original == current


@pytest.mark.parametrize("target", ["workflow", "step"])
def test_0017_metadata_python_none_is_json_null_and_sqlcheck_rejects_it(
    catalog_engine, tmp_path, target
):
    migrated_engine = catalog_engine
    workflow, _, child = METADATA.seed_workflow(migrated_engine, tmp_path)
    table = enrichment_workflows if target == "workflow" else enrichment_job_steps
    key = table.c.workflow_id if target == "workflow" else table.c.job_id
    record_id = workflow if target == "workflow" else child
    field = "input_context" if target == "workflow" else "result_payload"
    check = (
        "ck_enrichment_workflow_initialized"
        if target == "workflow"
        else "ck_enrichment_step_result"
    )
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(table.c[field].is_(None)).where(key == record_id)) is True
    with pytest.raises(IntegrityError) as rejected, migrated_engine.begin() as connection:
        connection.execute(update(table).where(key == record_id).values(**{field: None}))
    assert rejected.value.orig.sqlstate == "23514"
    assert rejected.value.orig.diag.constraint_name == check
    with migrated_engine.connect() as connection:
        assert connection.scalar(select(table.c[field].is_(None)).where(key == record_id)) is True


def test_deferred_current_guard_observes_final_state_and_commit_rollback(migrated_engine):
    scope = INVENTORY.scope(migrated_engine)
    stored = INVENTORY.save(migrated_engine, scope)
    selector = assets.c.asset_id == stored.asset_id
    with migrated_engine.begin() as connection:
        connection.execute(update(assets).where(selector).values(current_snapshot_id=None))
        assert connection.scalar(select(assets.c.current_snapshot_id).where(selector)) is None
        connection.execute(
            update(assets).where(selector).values(current_snapshot_id=stored.snapshot.snapshot_id)
        )
    with pytest.raises(IntegrityError) as rejected, migrated_engine.begin() as connection:
        connection.execute(update(assets).where(selector).values(current_snapshot_id=None))
        assert connection.scalar(select(assets.c.current_snapshot_id).where(selector)) is None
    assert rejected.value.orig.sqlstate == "23514"
    with migrated_engine.connect() as connection:
        assert (
            connection.scalar(select(assets.c.current_snapshot_id).where(selector))
            == stored.snapshot.snapshot_id
        )


def test_setting_current_guard_immediate_rejects_temporary_null(migrated_engine):
    scope = INVENTORY.scope(migrated_engine)
    stored = INVENTORY.save(migrated_engine, scope)
    with pytest.raises(IntegrityError) as rejected, migrated_engine.begin() as connection:
        connection.execute(
            update(assets)
            .where(assets.c.asset_id == stored.asset_id)
            .values(current_snapshot_id=None)
        )
        connection.exec_driver_sql("SET CONSTRAINTS asset_current_snapshot_required IMMEDIATE")
    assert rejected.value.orig.sqlstate == "23514"


def test_json_null_snapshot_payload_cannot_be_inserted(migrated_engine):
    scope = INVENTORY.scope(migrated_engine)
    stored = INVENTORY.save(migrated_engine, scope)
    with migrated_engine.connect() as connection:
        snapshot = dict(
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == stored.snapshot.snapshot_id
                )
            )
            .mappings()
            .one()
        )
    snapshot.update(snapshot_id=str(uuid4()), snapshot_number=2, canonical_payload=None)
    with pytest.raises(IntegrityError) as rejected, migrated_engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(**snapshot))
    assert rejected.value.orig.sqlstate == "23514"
    assert rejected.value.orig.diag.constraint_name == "ck_snapshot_payload"


def test_valid_hex_forged_aggregate_hash_is_rejected_by_authoritative_read(migrated_engine):
    now = datetime(2026, 10, 16, tzinfo=UTC)
    scope = AccessScope.for_authenticated_user("hash-fixture", None, Role.SYSTEM_ADMIN)
    policy = AggregateServerPolicy("negative-" + uuid4().hex, "fixture", True)
    repository = PostgresAggregateRepository(migrated_engine)
    stored = repository.save_observation(
        total_result("hunter", "ollama", 11, now, "fixture"), scope, policy, recorded_at=now
    )
    with migrated_engine.connect() as connection:
        row = dict(
            connection.execute(
                select(aggregate_observations).where(
                    aggregate_observations.c.observation_id == stored.observation_id
                )
            )
            .mappings()
            .one()
        )
    canonical = json.dumps(row["canonical_json"], sort_keys=True, separators=(",", ":"))
    assert hashlib.sha256(canonical.encode()).hexdigest() == row["payload_sha256"]
    row.update(observation_id=uuid4(), payload_sha256="0" * 64, recorded_at=now.replace(hour=1))
    with migrated_engine.begin() as connection:
        connection.execute(insert(aggregate_observations).values(**row))
    with pytest.raises(AggregatePersistenceError, match="aggregate storage integrity failed"):
        repository.read_latest("hunter", "ollama", scope, policy, now=now.replace(hour=2))
    (RUN / "negative_hash_boundary.json").write_text(
        json.dumps(
            {
                "test_mode": "synthetic fixture",
                "database_domain_accepts": "64 lowercase hex shape",
                "repository_read": "fails closed on canonical JSON/hash mismatch",
                "provider_calls": 0,
                "fee_status": "unknown",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
