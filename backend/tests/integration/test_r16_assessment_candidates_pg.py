"""Synthetic discovery scenarios on an owned real PostgreSQL production-migrated schema."""

import base64
import json
import os
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, insert, select, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from tests.integration.test_r11_pg_assessments import actor, assessor, asset, publish, seed

from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.rule_service import RuleService
from ai_intel.assets.inventory_models import asset_snapshots, assets
from ai_intel.domain.access import CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.database import run_migrations
from ai_intel.knowledge.persistence import publication_payload_digest, save_change_publication
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.revalidation.candidates import CandidateDiscoveryError, CandidateDiscoveryService

pytestmark = pytest.mark.real_pg
RUN_ID = "r16_candidates_20261016"
SYNTHETIC_KEY = SecretStr("01" * 32)


@pytest.fixture(scope="module")
def pg_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database == "test_dianzi_" + RUN_ID
    assert url.host == "127.0.0.1" and url.port == 25432
    assert url.username is not None and url.username.startswith("test_")
    assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID
    schema = "test_r16_candidates_" + uuid4().hex
    base = create_engine(
        url, hide_parameters=True, poolclass=NullPool, connect_args={"connect_timeout": 5}
    )
    with base.begin() as connection:
        connection.exec_driver_sql(f'CREATE SCHEMA "{schema}"')
    base.dispose()
    migration_url = url.update_query_dict({"options": f"-c search_path={schema}"})
    run_migrations(migration_url.render_as_string(hide_password=False), "head")
    engine = create_engine(
        url.update_query_dict(
            {
                "options": f"-c search_path={schema},public "
                "-c statement_timeout=15000 -c lock_timeout=5000"
            }
        ),
        hide_parameters=True,
        poolclass=NullPool,
        connect_args={"connect_timeout": 5},
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")) == schema
        revision = connection.scalar(text("SELECT version_num FROM alembic_version"))
        assert revision == "0022_sbom_sidecars"
    evidence = os.environ.get("R16_CANDIDATES_EVIDENCE_DIR")
    if evidence:
        from pathlib import Path

        (Path(evidence) / "schema_receipt.json").write_text(
            json.dumps(
                dict(
                    schema=schema,
                    database=url.database,
                    forward_only=True,
                    retained=True,
                    synthetic=True,
                    metadata_create_all=False,
                    revision=revision,
                )
            ),
            encoding="utf-8",
        )
    yield engine
    engine.dispose()
    base.dispose()


@pytest.fixture(autouse=True)
def redact_connection_credentials(register_sensitive_failure_value):
    url = make_url(os.environ["TEST_DATABASE_URL"])
    register_sensitive_failure_value(SecretStr(os.environ["TEST_DATABASE_URL"]))
    if url.password:
        register_sensitive_failure_value(SecretStr(url.password))


def discovery(engine, seeded):
    return CandidateDiscoveryService(engine, seeded["asset_token"], SYNTHETIC_KEY)


def latest_change(engine, scope_key, *, change_type=None):
    query = select(change_events).where(change_events.c.scope_key == scope_key)
    if change_type:
        query = query.where(change_events.c.change_type == change_type)
    with engine.connect() as connection:
        return (
            connection.execute(query.order_by(change_events.c.epoch.desc()).limit(1))
            .mappings()
            .one()
        )


def synthetic_change(
    engine, seeded, change_type="range_expanded", *, public=False, payload=None, ids=()
):
    visibility = VisibilityScope(
        visibility="public" if public else "tenant", tenant_id=None if public else seeded["tenant"]
    )
    payload = {} if payload is None else payload
    with Session(engine) as session, session.begin():
        receipt = save_change_publication(
            session,
            visibility,
            "fixture-r16:" + uuid4().hex,
            payload,
            publication_payload_digest(payload),
            (),
            ids,
            datetime.now(UTC),
            change_type,
        )
    return receipt


def assessment(engine, seeded, imported):
    service = assessor(engine, seeded)
    return service.commit(
        service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    )


def collect_pages(service, change_id, epoch, *, limit=2):
    candidates = []
    continuation = None
    for _ in range(1000):
        page = service.discover(change_id, epoch, limit=limit, continuation=continuation)
        candidates.extend(page.candidates)
        if page.status == "complete":
            assert page.continuation is None
            return candidates
        assert page.continuation and page.scanned_count <= 500
        continuation = page.continuation
    raise AssertionError("candidate discovery did not terminate")


def test_union_covers_old_hit_empty_result_new_asset_and_full_final_snapshot(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path / "one")
    other = seed(pg_engine, tmp_path / "two")
    empty_asset = asset(pg_engine, seeded, "1.4.8")
    empty = assessment(pg_engine, seeded, empty_asset)
    assert empty.prepared.scope_watch.no_published_rule and empty.rule_result is None
    publish(pg_engine, seeded)
    hit_asset = asset(pg_engine, seeded, "1.4.1")
    hit = assessment(pg_engine, seeded, hit_asset)
    excluded_asset = asset(pg_engine, seeded, "1.4.8")
    excluded = assessment(pg_engine, seeded, excluded_asset)
    added = asset(pg_engine, seeded, "1.4.9")
    foreign_asset = asset(pg_engine, other)
    foreign = assessment(pg_engine, other, foreign_asset)
    with pg_engine.connect() as connection:
        original = (
            connection.execute(
                select(assessment_results.c.result_payload)
                .where(
                    assessment_results.c.assessment_id.in_(
                        (empty.assessment_id, hit.assessment_id, excluded.assessment_id)
                    )
                )
                .order_by(assessment_results.c.assessment_id)
            )
            .scalars()
            .all()
        )
    change = synthetic_change(pg_engine, seeded, ids=(seeded["rule"].rule_id,))
    candidates = collect_pages(discovery(pg_engine, seeded), change.change_id, change.epoch)
    expected = {
        (empty_asset.asset_id, None),
        (hit_asset.asset_id, None),
        (excluded_asset.asset_id, None),
        (added.asset_id, None),
        (empty_asset.asset_id, empty.assessment_id),
        (hit_asset.asset_id, hit.assessment_id),
        (excluded_asset.asset_id, excluded.assessment_id),
    }
    assert {(item.asset_id, item.assessment_id) for item in candidates} == expected
    assert len(candidates) == len(expected)
    assert all(
        item.asset_id != foreign_asset.asset_id and item.assessment_id != foreign.assessment_id
        for item in candidates
    )
    assert (
        "empty_rule_scope"
        in next(item for item in candidates if item.assessment_id == empty.assessment_id).reasons
    )
    with pg_engine.connect() as connection:
        assert (
            connection.execute(
                select(assessment_results.c.result_payload)
                .where(
                    assessment_results.c.assessment_id.in_(
                        (empty.assessment_id, hit.assessment_id, excluded.assessment_id)
                    )
                )
                .order_by(assessment_results.c.assessment_id)
            )
            .scalars()
            .all()
            == original
        )


@pytest.mark.parametrize(
    "change_type", ["range_shrunk", "alias_added", "event_withdrawn", "unknown_change"]
)
def test_unknown_scopes_conservatively_retain_old_and_unassessed_assets(
    pg_engine, tmp_path, change_type
):
    seeded = seed(pg_engine, tmp_path)
    imported = asset(pg_engine, seeded)
    prior = assessment(pg_engine, seeded, imported)
    change = synthetic_change(pg_engine, seeded, change_type)
    page = discovery(pg_engine, seeded).discover(change.change_id, change.epoch)
    assert (
        page.status == "complete" and page.fallback_reason == "unknown_or_incomplete_change_scope"
    )
    assert {(item.asset_id, item.assessment_id) for item in page.candidates} == {
        (imported.asset_id, None),
        (imported.asset_id, prior.assessment_id),
    }


def test_retired_rule_preserves_readable_old_hit_and_exact_package_candidates(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    publish(pg_engine, seeded)
    imported = asset(pg_engine, seeded)
    prior = assessment(pg_engine, seeded, imported)
    RuleService(pg_engine, seeded["reviewer_token"], seeded["store"]).retire(
        seeded["rule"].rule_id, 1
    )
    change = latest_change(
        pg_engine, "tenant:" + seeded["tenant"], change_type="condition_rule_retired"
    )
    page = discovery(pg_engine, seeded).discover(change["change_id"], change["epoch"])
    assert page.fallback_reason is None and page.status == "complete"
    assert prior.prepared.scope_watch.scope_epoch_map["public"] is None
    assert next(
        item for item in page.candidates if item.assessment_id == prior.assessment_id
    ).reasons == ("old_dependency", "partition_fallback", "scope_watch")
    assert next(item for item in page.candidates if item.assessment_id is None).reasons == (
        "new_package_association",
    )


def test_asset_snapshot_change_uses_current_pg_ref_and_preserves_history(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    imported = asset(pg_engine, seeded)
    prior = assessment(pg_engine, seeded, imported)
    changed = asset(pg_engine, seeded, "1.5.0", asset_id=imported.asset_id)
    change = latest_change(
        pg_engine, "tenant:" + seeded["tenant"], change_type="asset_snapshot_changed"
    )
    page = discovery(pg_engine, seeded).discover(change["change_id"], change["epoch"])
    assert {item.asset_snapshot_id for item in page.candidates} == {changed.snapshot.snapshot_id}
    historical = next(item for item in page.candidates if item.assessment_id == prior.assessment_id)
    assert historical.previous_asset_snapshot_id == imported.snapshot.snapshot_id
    assert prior.asset_snapshot_id == imported.snapshot.snapshot_id


def test_replay_paging_is_deterministic_and_tampering_is_rejected(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    for _ in range(3):
        asset(pg_engine, seeded)
    change = synthetic_change(pg_engine, seeded)
    service = discovery(pg_engine, seeded)
    first = service.discover(change.change_id, change.epoch, limit=1)
    assert first == service.discover(change.change_id, change.epoch, limit=1)
    assert first.status == "partial" and first.continuation
    candidates = collect_pages(service, change.change_id, change.epoch, limit=1)
    assert len(candidates) == 3 and len({item.asset_id for item in candidates}) == 3
    raw = bytearray(base64.urlsafe_b64decode(first.continuation))
    raw[-1] ^= 1
    with pytest.raises(CandidateDiscoveryError, match="cursor_invalid"):
        service.discover(
            change.change_id,
            change.epoch,
            limit=1,
            continuation=base64.urlsafe_b64encode(raw).decode(),
        )
    with pytest.raises(CandidateDiscoveryError, match="context_changed"):
        service.discover(change.change_id, change.epoch, limit=2, continuation=first.continuation)


def test_old_cursor_rejected_after_new_asset_and_out_of_order_change_coalesces(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    for _ in range(2):
        asset(pg_engine, seeded)
    change = synthetic_change(pg_engine, seeded)
    service = discovery(pg_engine, seeded)
    first = service.discover(change.change_id, change.epoch, limit=1)
    added = asset(pg_engine, seeded)
    with pytest.raises(CandidateDiscoveryError, match="context_changed"):
        service.discover(change.change_id, change.epoch, limit=1, continuation=first.continuation)
    current = service.discover(change.change_id, change.epoch)
    assert (
        current.target_epoch > change.epoch and current.fallback_reason == "coalesced_scope_epoch"
    )
    assert added.asset_id in {item.asset_id for item in current.candidates}
    with pytest.raises(CandidateDiscoveryError, match="target_epoch_invalid"):
        service.discover(change.change_id, current.target_epoch + 1)


def test_private_change_and_cursor_cannot_cross_tenants(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path / "one")
    other = seed(pg_engine, tmp_path / "two")
    for _ in range(2):
        asset(pg_engine, seeded)
    change = synthetic_change(pg_engine, seeded)
    page = discovery(pg_engine, seeded).discover(change.change_id, change.epoch, limit=1)
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        discovery(pg_engine, other).discover(
            change.change_id, change.epoch, limit=1, continuation=page.continuation
        )


def test_public_research_role_cannot_discover_private_asset_count(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path)
    change = synthetic_change(pg_engine, seeded, public=True)
    _, token = actor(pg_engine, seeded["tenant"], Role.VIEWER)
    with pytest.raises(PermissionDeniedError, match="read:asset"):
        CandidateDiscoveryService(pg_engine, token, SYNTHETIC_KEY).discover(
            change.change_id, change.epoch
        )


def test_public_event_cannot_expose_private_source_even_to_source_owner(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path, public=True)
    imported = asset(pg_engine, seeded)
    assessment(pg_engine, seeded, imported)
    change = synthetic_change(
        pg_engine, seeded, public=True, payload={"event_id": seeded["event_id"]}
    )
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE sources SET visibility='tenant',tenant_id=:tenant WHERE source_id=:source"
            ),
            dict(tenant=seeded["tenant"], source=seeded["source_id"]),
        )
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        discovery(pg_engine, seeded).discover(change.change_id, change.epoch)


def test_acl_change_rejects_old_cursor_before_returning_invisible_assessments(pg_engine, tmp_path):
    seeded = seed(pg_engine, tmp_path, public=True)
    imported = asset(pg_engine, seeded)
    prior = assessment(pg_engine, seeded, imported)
    change = synthetic_change(pg_engine, seeded, public=True)
    service = discovery(pg_engine, seeded)
    page = service.discover(change.change_id, change.epoch, limit=1)
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE sources SET visibility='tenant',tenant_id=:tenant WHERE source_id=:source"
            ),
            dict(tenant="fixture-other-tenant", source=seeded["source_id"]),
        )
    with pytest.raises(CandidateDiscoveryError, match="context_changed"):
        service.discover(change.change_id, change.epoch, limit=1, continuation=page.continuation)
    current = service.discover(change.change_id, change.epoch)
    assert current.scanned_count == 1 and current.status == "complete"
    assert {item.assessment_id for item in current.candidates} == {None}
    assert prior.assessment_id not in {item.assessment_id for item in current.candidates}


def test_scan_budget_returns_partial_even_when_first_500_authorized_rows_have_no_match(
    pg_engine, tmp_path
):
    seeded = seed(pg_engine, tmp_path)
    imported = asset(pg_engine, seeded)
    with pg_engine.begin() as connection:
        asset_template = dict(
            connection.execute(select(assets).where(assets.c.asset_id == imported.asset_id))
            .mappings()
            .one()
        )
        snapshot_template = dict(
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == imported.snapshot.snapshot_id
                )
            )
            .mappings()
            .one()
        )
        asset_rows, snapshot_rows = [], []
        for index in range(501):
            asset_id, snapshot_id = (
                f"fixture-budget-asset-{index:04d}",
                f"fixture-budget-snapshot-{index:04d}",
            )
            payload = imported.snapshot.model_copy(
                update={"asset_id": asset_id, "snapshot_id": snapshot_id}
            ).model_dump(mode="json")
            asset_rows.append(
                {**asset_template, "asset_id": asset_id, "current_snapshot_id": snapshot_id}
            )
            snapshot_rows.append(
                {
                    **snapshot_template,
                    "asset_id": asset_id,
                    "snapshot_id": snapshot_id,
                    "canonical_payload": payload,
                }
            )
        connection.execute(insert(assets), asset_rows)
        connection.execute(insert(asset_snapshots), snapshot_rows)
    target = "fixture-budget-asset-0500"
    change = synthetic_change(
        pg_engine, seeded, "asset_snapshot_changed", payload={"asset_id": target}, ids=(target,)
    )
    service = discovery(pg_engine, seeded)
    first = service.discover(change.change_id, change.epoch)
    assert first.status == "partial" and first.scanned_count == 500 and first.candidates == ()
    second = service.discover(change.change_id, change.epoch, continuation=first.continuation)
    assert second.status == "complete" and second.scanned_count == 2
    assert {(item.asset_id, item.assessment_id) for item in second.candidates} == {(target, None)}
