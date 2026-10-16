"""Owned real PostgreSQL reads use explicitly synthetic facts and no external provider."""

import hashlib
import json
import secrets
import time
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
import test_r14_tool_gateway_pg as original_tools
from pydantic import SecretStr
from sqlalchemy import create_engine, event, func, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool
from sqlalchemy.schema import CreateSchema, DropSchema
from test_r10_evidence_graph_pg import VERSION, publish_event, publish_fact
from test_r14_tool_gateway_pg import (
    seed_principal,
)

from ai_intel.api.actor_references import create_actor_reference
from ai_intel.api.auth_state import auth_sessions
from ai_intel.api.credential_models import api_keys
from ai_intel.api.credentials import ApiKeyCredential
from ai_intel.api.knowledge_contracts import EventDetailResponse
from ai_intel.api.knowledge_read_service import sources
from ai_intel.assets.inventory import InventoryService
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.database import run_migrations
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.read_adapters import MAX_CHANGE_CANDIDATES, PostgresReadToolAdapter
from ai_intel.investigation.tool_contracts import ChangesPage
from ai_intel.investigation.tool_gateway import BudgetLimits, ToolGateway
from ai_intel.knowledge.models import users
from ai_intel.knowledge.persistence_models import change_events, event_external_ids, events

pytestmark = pytest.mark.real_pg


@pytest.fixture()
def read_engine(isolated_test_database_url, register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(isolated_test_database_url))
    url = make_url(isolated_test_database_url)
    assert url.database == "test_dianzi_r14_read_tools_20261016"
    if url.password:
        register_sensitive_failure_value(SecretStr(url.password))
    schema = "test_r14_read_adapters_" + uuid4().hex
    base = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with base.begin() as connection:
        assert connection.scalar(text("SELECT current_database()")) == url.database
        connection.execute(CreateSchema(schema))
    isolated = url.update_query_dict(
        {"options": f"-c search_path={schema} -c statement_timeout=15000 -c lock_timeout=5000"}
    )
    run_migrations(isolated.render_as_string(hide_password=False))
    engine = create_engine(isolated, poolclass=NullPool, hide_parameters=True)
    try:
        yield engine
    finally:
        engine.dispose()
        with base.begin() as connection:
            connection.execute(DropSchema(schema, cascade=True))
        base.dispose()


@pytest.fixture()
def r14_engine(read_engine):
    """Run unchanged original read-evidence assertions against the owned isolated schema."""
    return read_engine


def limits(seconds=5):
    return BudgetLimits(
        max_calls=8,
        max_concurrent_calls=1,
        max_request_bytes=4096,
        max_total_input_bytes=32768,
        max_result_bytes=32768,
        max_total_output_bytes=262144,
        deadline_monotonic=time.monotonic() + seconds,
    )


def raw_call(tool, **arguments):
    return json.dumps({"tool_name": tool, "arguments": arguments, "goal_id": str(uuid4())}).encode()


def public_fact(engine, path):
    event_id = uuid4()
    submission = publish_fact(engine, path, event_id, VERSION)
    publish_event(engine, event_id, [submission])
    return event_id, submission


def store_asset(engine, principal, *, asset_id=None, version="1.0"):
    publisher_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            users.insert().values(
                user_id=publisher_id,
                username="fixture-inventory-publisher-" + publisher_id,
                password_hash="fixture-unused-password-hash",
                tenant_id=principal.tenant_id,
                role=Role.TENANT_ADMIN.value,
                created_at=datetime.now(UTC),
            )
        )
    scope = AccessScope.for_authenticated_user(publisher_id, principal.tenant_id, Role.TENANT_ADMIN)
    raw = json.dumps(
        {
            "format_version": 1,
            "components": [
                {"ecosystem": "pypi", "package_name": "fixture-package", "version": version}
            ],
        }
    ).encode()
    with Session(engine) as session, session.begin():
        return InventoryService(session, scope).import_manifest(
            raw,
            manifest_format="json_manifest_v1",
            display_name="fixture asset",
            source_version="fixture-1",
            observed_at=datetime.now(UTC),
            idempotency_key=uuid4().hex,
            asset_id=asset_id,
        )


def key_actor(engine, principal, register, permissions):
    token = secrets.token_urlsafe(32)
    register(SecretStr(token))
    now = datetime.now(UTC)
    key_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            api_keys.insert().values(
                key_id=key_id,
                token_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=principal.user_id,
                resource="urn:dianzi:api:v1",
                scopes=list(permissions),
                issued_at=now,
                expires_at=now + timedelta(minutes=5),
                version=1,
            )
        )
        reference = create_actor_reference(connection, ApiKeyCredential(SecretStr(token)), now)
    return reference, key_id


def test_real_pg_advisory_and_changes_reuse_shared_dtos_and_persisted_records(
    read_engine, tmp_path, register_sensitive_failure_value
):
    event_id, submission = public_fact(read_engine, tmp_path)
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    statements = []
    with read_engine.connect() as connection:
        event.listen(
            connection,
            "before_cursor_execute",
            lambda connection, cursor, statement, parameters, context, executemany: (
                statements.append(statement)
            ),
        )
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        )
        advisory = subject.execute(
            AgentRole.ENRICHER, raw_call("get_advisory", event_id=str(event_id))
        )
        assert advisory.status == "succeeded", advisory.error_code
        assert (
            isinstance(advisory.data, EventDetailResponse)
            and advisory.data.event.event_id == event_id
        )
        assert advisory.data.claims and advisory.data.revisions and advisory.evidence_ids == ()
        changes = subject.execute(
            AgentRole.REPORTER, raw_call("find_changes", event_id=str(event_id), limit=25)
        )
        assert changes.status == "succeeded", changes.error_code
        assert isinstance(changes.data, ChangesPage) and len(changes.data.items) == 2
        assert {item.change_type for item in changes.data.items} == {
            "events_published",
            "knowledge_published",
        }
        assert changes.is_synthetic and changes.evidence_ids == ()
        assert submission.source_id.value not in changes.model_dump_json()
        assert "payload" not in changes.data.model_dump_json()
        assert not connection.in_transaction()
    assert all(statement.lstrip().upper().startswith("SELECT") for statement in statements)


def test_real_pg_inventory_current_unknown_and_historical_stale_are_distinct(
    read_engine, register_sensitive_failure_value
):
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    first = store_asset(read_engine, principal)
    second = store_asset(read_engine, principal, asset_id=first.asset_id, version="2.0")
    with read_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        )
        old = subject.execute(
            AgentRole.ASSESSOR,
            raw_call(
                "get_inventory", asset_id=first.asset_id, snapshot_id=first.snapshot.snapshot_id
            ),
        )
        current = subject.execute(
            AgentRole.ASSESSOR,
            raw_call(
                "get_inventory", asset_id=second.asset_id, snapshot_id=second.snapshot.snapshot_id
            ),
        )
    assert isinstance(old.data, AssetSnapshotResponse) and old.data.components[0].version == "1.0"
    assert old.status == "partial" and old.error_code == "inventory_snapshot_not_current"
    assert (
        isinstance(current.data, AssetSnapshotResponse)
        and current.data.components[0].version == "2.0"
    )
    assert current.status == "partial" and current.error_code == "inventory_scope_incomplete"
    assert old.observed_at == first.snapshot.observed_at


@pytest.mark.parametrize("tenant,role", [("other", Role.ANALYST), ("owner", Role.VIEWER)])
def test_real_pg_inventory_cross_tenant_and_viewer_never_return_fields(
    read_engine, register_sensitive_failure_value, tenant, role
):
    owner, _ = seed_principal(read_engine, register_sensitive_failure_value)
    asset = store_asset(read_engine, owner)
    principal, token = seed_principal(
        read_engine, register_sensitive_failure_value, tenant=tenant, role=role
    )
    with read_engine.connect() as connection:
        result = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        ).execute(
            AgentRole.ASSESSOR,
            raw_call(
                "get_inventory", asset_id=asset.asset_id, snapshot_id=asset.snapshot.snapshot_id
            ),
        )
    assert result.status == "denied" and result.data is None and result.evidence_ids == ()
    assert "fixture-package" not in result.model_dump_json()


@pytest.mark.parametrize(
    "permission,tool,allowed",
    [
        ("read:public", "get_advisory", True),
        ("read:public", "get_inventory", False),
        ("read:asset", "get_advisory", False),
        ("read:asset", "get_inventory", True),
        ("read:public", "find_changes", True),
        ("read:asset", "find_changes", False),
    ],
)
def test_real_pg_narrow_bearer_permission_intersection(
    read_engine, tmp_path, register_sensitive_failure_value, permission, tool, allowed
):
    event_id, _ = public_fact(read_engine, tmp_path)
    principal, _ = seed_principal(read_engine, register_sensitive_failure_value)
    asset = store_asset(read_engine, principal)
    actor, _ = key_actor(read_engine, principal, register_sensitive_failure_value, [permission])
    arguments = (
        {"asset_id": asset.asset_id, "snapshot_id": asset.snapshot.snapshot_id}
        if tool == "get_inventory"
        else {"event_id": str(event_id)}
    )
    role = {
        "get_advisory": AgentRole.ENRICHER,
        "get_inventory": AgentRole.ASSESSOR,
        "find_changes": AgentRole.REPORTER,
    }[tool]
    with read_engine.connect() as connection:
        result = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, actor, "fixture"),
        ).execute(role, raw_call(tool, **arguments))
    assert (result.status in {"succeeded", "partial"}) == allowed, result.error_code
    if not allowed:
        assert result.status == "denied" and result.data is None


@pytest.mark.parametrize("tool", ["get_advisory", "find_changes", "get_inventory"])
def test_real_pg_actor_replay_rejects_revocation(
    read_engine, tmp_path, register_sensitive_failure_value, tool
):
    event_id, _ = public_fact(read_engine, tmp_path)
    principal, _ = seed_principal(read_engine, register_sensitive_failure_value)
    asset = store_asset(read_engine, principal)
    actor, key_id = key_actor(
        read_engine, principal, register_sensitive_failure_value, ["read:asset", "read:public"]
    )
    arguments = (
        {"asset_id": asset.asset_id, "snapshot_id": asset.snapshot.snapshot_id}
        if tool == "get_inventory"
        else {"event_id": str(event_id)}
    )
    role = {
        "get_advisory": AgentRole.ENRICHER,
        "get_inventory": AgentRole.ASSESSOR,
        "find_changes": AgentRole.REPORTER,
    }[tool]
    with read_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, actor, "fixture"),
        )
        call = raw_call(tool, **arguments)
        assert subject.execute(role, call).data is not None
        with read_engine.begin() as writer:
            writer.execute(
                update(api_keys)
                .where(api_keys.c.key_id == key_id)
                .values(revoked_at=datetime.now(UTC))
            )
        revoked = subject.execute(role, call)
        assert revoked.status == "denied" and revoked.data is None and not revoked.usage.cached


def test_real_pg_source_acl_revocation_removes_history_and_invalidates_cursor_without_epoch_bump(
    read_engine, tmp_path, register_sensitive_failure_value
):
    event_id, submission = public_fact(read_engine, tmp_path)
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    with read_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        )
        first = subject.execute(
            AgentRole.REPORTER, raw_call("find_changes", event_id=str(event_id), limit=1)
        )
        assert first.status == "succeeded" and first.data.next_cursor is not None
        cursor = first.data.next_cursor
        with read_engine.begin() as writer:
            writer.execute(
                update(sources)
                .where(sources.c.source_id == submission.source_id.value)
                .values(visibility="tenant", tenant_id="hidden")
            )
        later = subject.execute(
            AgentRole.REPORTER,
            raw_call("find_changes", event_id=str(event_id), limit=1, cursor=cursor),
        )
        assert (
            later.status == "partial"
            and later.error_code == "read_snapshot_changed"
            and later.data is None
        )
        hidden = subject.execute(
            AgentRole.REPORTER, raw_call("find_changes", event_id=str(event_id), limit=25)
        )
        assert hidden.status == "partial" and hidden.error_code == "change_history_incomplete"
        assert (
            hidden.data.items == () and submission.source_id.value not in hidden.model_dump_json()
        )
        advisory = subject.execute(
            AgentRole.ENRICHER, raw_call("get_advisory", event_id=str(event_id))
        )
        assert (
            advisory.status == "partial"
            and advisory.data.revisions == ()
            and advisory.data.claims == ()
        )


def test_real_pg_changes_cursor_stable_pages_and_empty_scope_are_not_global_absence(
    read_engine, tmp_path, register_sensitive_failure_value
):
    event_id, _ = public_fact(read_engine, tmp_path)
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    with read_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        )
        first = subject.execute(
            AgentRole.REPORTER, raw_call("find_changes", event_id=str(event_id), limit=1)
        )
        second = subject.execute(
            AgentRole.REPORTER,
            raw_call(
                "find_changes", event_id=str(event_id), limit=1, cursor=first.data.next_cursor
            ),
        )
        assert len(first.data.items) == len(second.data.items) == 1
        assert (
            first.data.items[0].change_id != second.data.items[0].change_id
            and second.data.next_cursor is None
        )
        after_end = subject.execute(
            AgentRole.REPORTER,
            raw_call(
                "find_changes", event_id=str(event_id), limit=1, cursor=first.data.next_cursor
            ),
        )
        assert after_end.data == second.data and not after_end.usage.cached


def test_real_pg_change_candidate_bound_reports_partial_and_keeps_continuation(
    read_engine, tmp_path, register_sensitive_failure_value
):
    event_id, _ = public_fact(read_engine, tmp_path)
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    now = datetime.now(UTC)
    with read_engine.begin() as writer:
        previous_epoch = writer.scalar(select(func.max(change_events.c.epoch))) or 0
        writer.execute(
            change_events.insert(),
            [
                {
                    "change_id": str(uuid4()),
                    "scope_key": "public",
                    "epoch": previous_epoch + index + 1,
                    "change_type": "unknown_fixture_type",
                    "entity_ids": [str(event_id)],
                    "payload": {"private_source_id": "must-not-return"},
                    "created_at": now,
                }
                for index in range(MAX_CHANGE_CANDIDATES + 1)
            ],
        )
    with read_engine.connect() as connection:
        result = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        ).execute(AgentRole.REPORTER, raw_call("find_changes", event_id=str(event_id), limit=25))
    assert result.status == "partial" and result.error_code == "change_history_incomplete"
    assert result.data.items == () and result.data.next_cursor is not None
    assert "must-not-return" not in result.model_dump_json()


def test_real_pg_missing_object_and_expired_cookie_do_not_fabricate_no_result(
    read_engine, register_sensitive_failure_value
):
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    with read_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        )
        missing = subject.execute(
            AgentRole.ENRICHER, raw_call("get_advisory", event_id=str(uuid4()))
        )
        assert missing.status == "denied" and missing.data is None
        with read_engine.begin() as writer:
            writer.execute(
                update(auth_sessions)
                .where(auth_sessions.c.session_hash == hashlib.sha256(token.encode()).hexdigest())
                .values(
                    issued_at=datetime.now(UTC) - timedelta(minutes=2),
                    expires_at=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
        expired = subject.execute(
            AgentRole.ENRICHER, raw_call("get_advisory", event_id=str(uuid4()))
        )
        assert expired.status == "denied" and expired.data is None


def test_real_pg_empty_change_scope_preserves_no_result_without_global_claim(
    read_engine, register_sensitive_failure_value
):
    event_id = uuid4()
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    with read_engine.begin() as writer:
        writer.execute(
            events.insert().values(
                event_id=str(event_id),
                event_type="fixture",
                title="empty fixture",
                scope_key="public",
                visibility="public",
                tenant_id=None,
                status="active",
                first_seen_at=datetime.now(UTC),
                business_version=1,
            )
        )
    with read_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        )
        call = raw_call("find_changes", event_id=str(event_id))
        result = subject.execute(AgentRole.REPORTER, call)
        assert result.status == "no_result" and isinstance(result.data, ChangesPage)
        assert result.data.items == () and result.searched_scope.event_id == event_id
        assert subject.execute(AgentRole.REPORTER, call).usage.service_calls == 1
        assert result.limitations and "全历史" in result.limitations[0]


def test_real_pg_parent_closure_bound_is_partial_before_unbounded_business_read(
    read_engine, tmp_path, register_sensitive_failure_value
):
    event_id, _ = public_fact(read_engine, tmp_path)
    principal, token = seed_principal(read_engine, register_sensitive_failure_value)
    with read_engine.begin() as writer:
        writer.execute(
            event_external_ids.insert(),
            [
                {
                    "event_id": str(event_id),
                    "scope_key": "public",
                    "id_type": "fixture",
                    "id_value": "fixture-" + str(index),
                }
                for index in range(257)
            ],
        )
    with read_engine.connect() as connection:
        subject = ToolGateway(
            principal,
            uuid4(),
            limits(),
            read_adapter=PostgresReadToolAdapter(connection, token, "fixture"),
        )
        result = subject.execute(
            AgentRole.ENRICHER, raw_call("get_advisory", event_id=str(event_id))
        )
    assert (
        result.status == "partial"
        and result.error_code == "read_candidate_limit"
        and result.data is None
    )


test_original_current_supported_read = (
    original_tools.test_real_pg_current_supported_read_uses_both_business_services
)
test_original_private_asset_role = (
    original_tools.test_real_pg_private_read_is_only_available_to_asset_role
)
test_original_cross_tenant_and_permission = (
    original_tools.test_real_pg_cross_tenant_and_missing_permission_never_return_private_fields
)
test_original_replay_fresh_authentication = (
    original_tools.test_real_pg_success_or_partial_replay_rechecks_current_authentication
)
