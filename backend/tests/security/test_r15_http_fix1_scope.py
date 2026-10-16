"""Offline regression inputs; mocks and SQLite do not prove PG cookie authentication."""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.recommendations.policy import generate_recommendation_candidates
from ai_intel.recommendations.service import RecommendationService
from ai_intel.recommendations.service_contracts import (
    GenerationContent,
    RecommendationIntegrityError,
    SubscriptionRecord,
    SubscriptionSpec,
    content_sha256,
)


@pytest.mark.parametrize("end", ["commit", "rollback"])
@pytest.mark.parametrize("nested", [False, True])
def test_replacement_transaction_never_inherits_original_binding(tmp_path, end, nested):
    engine = create_engine("sqlite://")
    service = RecommendationService(engine, "fixture-nonsecret", ContentStore(tmp_path))
    with Session(engine) as session:
        original = session.begin()
        with service.in_transaction(session) as bound:
            getattr(original, end)()
            with session.begin():
                if nested:
                    with (
                        session.begin_nested(),
                        pytest.raises(ValueError, match="expired"),
                        bound._transaction(),
                    ):
                        pytest.fail("replacement nested transaction accepted")
                else:
                    with pytest.raises(ValueError, match="expired"), bound._transaction():
                        pytest.fail("replacement transaction accepted")
        assert bound._request_session is None and bound._request_transaction is None
    engine.dispose()


def test_nested_transaction_is_rejected_then_original_binding_still_works(tmp_path):
    engine = create_engine("sqlite://")
    service = RecommendationService(engine, "fixture-nonsecret", ContentStore(tmp_path))
    with Session(engine) as session, session.begin(), service.in_transaction(session) as bound:
        with (
            session.begin_nested(),
            pytest.raises(ValueError, match="expired"),
            bound._transaction(),
        ):
            pytest.fail("nested transaction accepted")
        with bound._transaction() as actual:
            assert actual is session
        with pytest.raises(ValueError, match="required"), bound.in_transaction(session):
            pytest.fail("bound service rebound")
    engine.dispose()


def test_binding_rejects_an_engine_from_another_service(tmp_path):
    engine, other_engine = create_engine("sqlite://"), create_engine("sqlite://")
    service = RecommendationService(engine, "fixture-nonsecret", ContentStore(tmp_path))
    with (
        Session(other_engine) as session,
        session.begin(),
        pytest.raises(ValueError, match="required"),
        service.in_transaction(session),
    ):
        pytest.fail("different engine accepted")
    engine.dispose()
    other_engine.dispose()


@pytest.fixture
def asset_fence_session():
    engine = create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(text("CREATE TABLE assets(asset_id TEXT,tenant_id TEXT,active BOOLEAN)"))
        connection.execute(
            text("INSERT INTO assets VALUES('own','tenant-a',false),('other','tenant-b',true)")
        )
    with Session(engine) as session, session.begin():
        yield session
    engine.dispose()


def test_inactive_owned_asset_can_pass_privacy_fence_for_unsubscribe(asset_fence_session):
    scope = AccessScope.for_authenticated_user("fixture-user", "tenant-a", Role.ANALYST)
    RecommendationService._lock_assets(asset_fence_session, scope, ("own", "own"))
    for asset_id in ("other", "missing"):
        with pytest.raises(CrossTenantAccessError, match="not found"):
            RecommendationService._lock_assets(asset_fence_session, scope, (asset_id,))


def test_public_viewer_does_not_gain_asset_privilege_from_ownership(asset_fence_session):
    scope = AccessScope.for_authenticated_user("fixture-user", "tenant-a", Role.VIEWER)
    RecommendationService._lock_assets(asset_fence_session, scope, ())
    with pytest.raises(PermissionDeniedError):
        RecommendationService._lock_assets(asset_fence_session, scope, ("own",))


@pytest.fixture
def scoped_subscription(tmp_path, monkeypatch):
    engine = create_engine("sqlite://")
    service = RecommendationService(engine, "fixture-nonsecret", ContentStore(tmp_path))
    scope = AccessScope.for_authenticated_user("fixture-user", "tenant-a", Role.VIEWER)
    monkeypatch.setattr(RecommendationService, "_scope", lambda self, session: scope)
    subscription_id, asset_id = uuid4(), uuid4()
    spec = SubscriptionSpec(asset_ids=(asset_id,), enabled=False)
    row = dict(
        id=str(subscription_id),
        tenant_id="tenant-a",
        user_id="fixture-user",
        version=1,
        enabled=False,
        spec_payload=spec.model_dump(mode="json"),
        spec_sha256=content_sha256(spec.model_dump(mode="json")),
        created_at=datetime(2026, 10, 16, tzinfo=UTC),
        updated_at=datetime(2026, 10, 16, tzinfo=UTC),
    )
    with Session(engine) as session, session.begin():
        execute = MagicMock()
        execute.return_value.mappings.return_value.first.return_value = row
        execute.return_value.first.return_value = (str(asset_id),)
        monkeypatch.setattr(session, "execute", execute)
        monkeypatch.setattr(session, "scalars", lambda query: (str(subscription_id),))
        with service.in_transaction(session) as bound:
            yield bound, subscription_id, row, execute
    engine.dispose()


@pytest.mark.parametrize(
    "operation",
    [
        "read_subscription",
        "list_subscriptions",
        "replace_subscription",
        "set_enabled",
        "prepare_generation",
        "generate",
        "generate_current",
        "read_generation",
        "list_recommendations",
        "mark_read",
        "create_report",
        "list_reports",
        "read_report",
    ],
)
def test_all_current_asset_interest_ports_reject_revoked_role_before_effect(
    scoped_subscription, operation
):
    bound, subscription_id, row, execute = scoped_subscription
    historical_id = uuid4()
    with pytest.raises(PermissionDeniedError):
        if operation == "list_subscriptions":
            bound.list_subscriptions()
        elif operation == "replace_subscription":
            bound.replace_subscription(
                subscription_id,
                expected_version=1,
                spec=SubscriptionSpec(product_keys=("public:x",)),
            )
        elif operation == "set_enabled":
            bound.set_enabled(subscription_id, expected_version=1, enabled=False)
        elif operation in {"prepare_generation", "generate"}:
            getattr(bound, operation)(subscription_id, expected_version=1, event_ids=())
        elif operation == "generate_current":
            bound.generate_current(subscription_id)
        elif operation in {"read_generation", "mark_read", "read_report"}:
            getattr(bound, operation)(subscription_id, historical_id)
        elif operation == "create_report":
            bound.create_report(subscription_id, historical_id, frequency="week")
        else:
            getattr(bound, operation)(subscription_id)
    assert execute.call_count == 1 and row["version"] == 1 and row["enabled"] is False


def test_public_only_viewer_subscription_read_remains_available(scoped_subscription, monkeypatch):
    bound, subscription_id, row, execute = scoped_subscription
    spec = SubscriptionSpec(product_keys=("public:x",), enabled=False)
    row.update(
        spec_payload=spec.model_dump(mode="json"),
        spec_sha256=content_sha256(spec.model_dump(mode="json")),
    )
    loader = MagicMock()
    monkeypatch.setattr(bound, "_loader", lambda session, scope: loader)
    assert bound.read_subscription(subscription_id).spec == spec
    assert bound.list_subscriptions().items[0].spec == spec
    assert execute.call_count == 2


def test_unsubscribe_does_not_require_active_snapshot_after_privacy_check(
    scoped_subscription, monkeypatch
):
    bound, subscription_id, row, execute = scoped_subscription
    scope = AccessScope.for_authenticated_user("fixture-user", "tenant-a", Role.ANALYST)
    monkeypatch.setattr(bound, "_scope", lambda session: scope)

    def active_validation_forbidden(session, current_scope):
        raise AssertionError("inactive asset must not prevent unsubscribe")

    monkeypatch.setattr(bound, "_loader", active_validation_forbidden)
    record = bound.set_enabled(subscription_id, expected_version=1, enabled=False)
    assert record.version == 2 and record.spec.enabled is False and record.spec.asset_ids
    assert execute.call_count == 3 and row["version"] == 1


def test_empty_history_keeps_original_asset_interest_after_current_spec_removed_assets(
    scoped_subscription,
):
    bound, subscription_id, row, execute = scoped_subscription
    original = SubscriptionRecord(
        subscription_id=subscription_id,
        tenant_id=row["tenant_id"],
        user_id=row["user_id"],
        version=1,
        spec=SubscriptionSpec.model_validate(row["spec_payload"]),
        spec_sha256=row["spec_sha256"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
    batch = generate_recommendation_candidates(
        original.policy_subscription(), (), cutoff_at=row["created_at"]
    )
    content = GenerationContent(
        subscription=original,
        batch=batch,
        report_batch=batch,
        gaps=(),
        event_ids=(),
        scope_epochs={},
        input_sha256="a" * 64,
        material_versions={},
        partial=False,
        data_mode="fixture",
    )
    payload = content.model_dump(mode="json")
    stored = dict(
        result_payload=payload,
        content_sha256=content_sha256(payload),
        subscription_id=str(subscription_id),
        tenant_id=original.tenant_id,
        user_id=original.user_id,
        subscription_version=1,
        cutoff_at=batch.cutoff_at,
        input_sha256=content.input_sha256,
    )
    execute.return_value.mappings.return_value.one.return_value = stored
    current_spec = SubscriptionSpec(product_keys=("public:x",), enabled=False)
    row.update(
        spec_payload=current_spec.model_dump(mode="json"),
        spec_sha256=content_sha256(current_spec.model_dump(mode="json")),
    )
    scope = AccessScope.for_authenticated_user("fixture-user", "tenant-a", Role.VIEWER)
    with bound._transaction() as session:
        assert bound._subscription(session, scope, subscription_id).spec.asset_ids == ()
        generation_id = str(uuid4())
        original_ids = bound._generation_asset_ids(
            session, scope, subscription_id, (generation_id, generation_id)
        )
        assert original_ids == original.spec.asset_ids and content.batch.candidates == ()
        with pytest.raises(PermissionDeniedError):
            bound._history_fence(session, scope, (), asset_ids=original_ids)
        assert stored["content_sha256"] == content_sha256(stored["result_payload"])
        stored["content_sha256"] = "b" * 64
        with pytest.raises(RecommendationIntegrityError, match="hash_mismatch"):
            bound._generation_asset_ids(session, scope, subscription_id, (generation_id,))
