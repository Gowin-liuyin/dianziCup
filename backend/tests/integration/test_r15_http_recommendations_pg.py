"""Explicit synthetic evidence through real PG migrations, HTTP and business services."""

import hashlib
import json
import os
import re
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Event
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.pool import NullPool
from test_r11_pg_assessments import asset, seed
from test_r15_persistent_subscriptions_pg import actor, add_withdrawal, semantic_source

from ai_intel.api.auth_state import PgAuthenticationStateStore, auth_sessions
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.api.recommendation_routes import build_recommendation_router
from ai_intel.domain.access import Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import scope_epochs, users
from ai_intel.knowledge.persistence_models import claims, event_documents, events
from ai_intel.recommendations.mutation_receipts import recommendation_mutation_receipts
from ai_intel.recommendations.persistence_models import (
    r15_generations,
    r15_subscriptions,
)
from ai_intel.recommendations.service_contracts import canonical_json_bytes

pytestmark = pytest.mark.real_pg
ORIGIN = "http://testserver"


@pytest.fixture(scope="module")
def r15_http_engine():
    database_url = os.environ.get("TEST_DATABASE_URL", "")
    run_id = os.environ.get("DIANZI_TEST_RUN_ID", "")
    if not database_url or re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", run_id) is None:
        raise pytest.UsageError("blocked: standard TEST_DATABASE_URL/DIANZI_TEST_RUN_ID required")
    url = make_url(database_url)
    if url.database is None or not url.database.startswith("test_"):
        raise pytest.UsageError("blocked: owned test database required")
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    with engine.connect() as connection:
        database, schema = connection.execute(
            text("SELECT current_database(),current_schema()")
        ).one()
        assert database == url.database and schema.startswith("test_") and schema != "public"
        assert (
            connection.scalar(text("SELECT version_num FROM alembic_version"))
            == "0029_recommendation_receipts"
        )
        assert connection.scalar(text("SELECT to_regclass('recommendation_mutation_receipts')"))
    yield engine
    engine.dispose()


@pytest.fixture(scope="session", autouse=True)
def unpooled_original_resource_fixture():
    """Original assertions are byte-identical; only their connection pooling is bounded."""
    import test_r15_persistent_subscriptions_pg as original

    patch = pytest.MonkeyPatch()

    def no_pool(url, **options):
        options.pop("pool_size", None)
        options.pop("max_overflow", None)
        return create_engine(url, **options, poolclass=NullPool)

    patch.setattr(original, "create_engine", no_pool)
    yield
    patch.undo()


@pytest.fixture(scope="module")
def shared_store():
    return ContentStore(
        Path(tempfile.gettempdir()) / "dianzi-test-http-content" / os.environ["DIANZI_TEST_RUN_ID"]
    )


def client_for(engine, token, store):
    authentication = AuthenticationSessionService(
        DatabaseUserDirectory(engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(engine),
    )
    app = FastAPI()
    router = build_recommendation_router(lambda: authentication, engine, store, data_mode="fixture")
    app.include_router(router, prefix="/v1")
    app.include_router(router, prefix="/api/v1")
    client = TestClient(app)
    client.cookies.set("ai_intel_session", token)
    client.headers.update({"Origin": ORIGIN, "X-CSRF-Token": "fixture-unused"})
    return client


def post(client, path, payload=None, *, key=None):
    return client.post(path, json=payload or {}, headers={"Idempotency-Key": key or uuid4().hex})


def subscription(client, product):
    response = post(client, "/v1/subscriptions", {"spec": {"product_keys": ["PyPI:" + product]}})
    assert response.status_code == 201, response.text
    return response.json()


def generation(client, subscription_id, *, key=None):
    response = post(client, f"/v1/subscriptions/{subscription_id}/generate", key=key)
    assert response.status_code == 200, response.text
    return response.json()


def report(client, subscription_id, generation_id, *, frequency="day", key=None):
    response = post(
        client,
        "/v1/reports",
        {
            "subscription_id": subscription_id,
            "generation_id": generation_id,
            "frequency": frequency,
        },
        key=key,
    )
    assert response.status_code == 200, response.text
    return response.json()


def row_count(engine, table, owner):
    with engine.connect() as connection:
        return connection.scalar(
            select(func.count()).select_from(table).where(table.c.user_id == owner)
        )


def test_http_create_replay_changed_input_alias_and_owner_isolation(r15_http_engine, shared_store):
    tenant = "fixture-http-owner-" + uuid4().hex
    owner, token = actor(r15_http_engine, tenant)
    other, other_token = actor(r15_http_engine, tenant)
    client = client_for(r15_http_engine, token, shared_store)
    other_client = client_for(r15_http_engine, other_token, shared_store)
    key = uuid4().hex
    payload = {"spec": {"product_keys": ["PyPI:alpha"], "minimum_priority": 1}}
    first = post(client, "/v1/subscriptions", payload, key=key)
    replay = post(client, "/api/v1/subscriptions", payload, key=key)
    assert first.status_code == replay.status_code == 201
    assert first.json() == replay.json()
    assert first.json()["spec"]["maximum_priority_bucket"] == 1
    collision = post(
        client, "/v1/subscriptions", {"spec": {"product_keys": ["PyPI:beta"]}}, key=key
    )
    assert collision.status_code == 409
    isolated = post(other_client, "/v1/subscriptions", payload, key=key)
    assert (
        isolated.status_code == 201
        and isolated.json()["subscription_id"] != first.json()["subscription_id"]
    )
    assert row_count(r15_http_engine, r15_subscriptions, owner.user_id) == 1
    assert row_count(r15_http_engine, recommendation_mutation_receipts, owner.user_id) == 1
    assert row_count(r15_http_engine, recommendation_mutation_receipts, other.user_id) == 1
    assert (
        other_client.get("/v1/subscriptions/" + first.json()["subscription_id"]).status_code == 404
    )


def test_two_users_actual_different_interest_full_paths_and_json_export(
    r15_http_engine, shared_store
):
    alpha_product, beta_product = "alpha-" + uuid4().hex, "beta-" + uuid4().hex
    alpha = semantic_source(r15_http_engine, shared_store, package=alpha_product)
    beta = semantic_source(r15_http_engine, shared_store, package=beta_product)
    owner, token = actor(r15_http_engine, "fixture-http-a-" + uuid4().hex)
    _, other_token = actor(r15_http_engine, "fixture-http-b-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    other = client_for(r15_http_engine, other_token, shared_store)
    a_sub = subscription(client, alpha_product)["subscription_id"]
    b_sub = subscription(other, beta_product)["subscription_id"]
    a_key = uuid4().hex
    a_generation = generation(client, a_sub, key=a_key)
    b_generation = generation(other, b_sub)
    replay = generation(client, a_sub, key=a_key)
    assert replay["generation_id"] == a_generation["generation_id"] and replay["reused"]
    assert row_count(r15_http_engine, r15_generations, owner.user_id) == 1
    a_list = client.get(f"/v1/subscriptions/{a_sub}/recommendations").json()
    b_list = other.get(f"/api/v1/subscriptions/{b_sub}/recommendations").json()
    assert {item["content"]["key"]["event_id"] for item in a_list["items"]} == {
        str(alpha["event_id"])
    }
    assert {item["content"]["key"]["event_id"] for item in b_list["items"]} == {
        str(beta["event_id"])
    }
    recommendation_id = a_generation["recommendation_ids"][0]
    read_key = uuid4().hex
    read = post(
        client,
        f"/v1/recommendations/{recommendation_id}/read?subscription_id={a_sub}",
        key=read_key,
    )
    again = post(
        client,
        f"/v1/recommendations/{recommendation_id}/read?subscription_id={a_sub}",
        key=read_key,
    )
    assert read.status_code == again.status_code == 200
    assert read.json()["read_at"] == again.json()["read_at"]
    report_key = uuid4().hex
    saved = report(client, a_sub, a_generation["generation_id"], key=report_key)
    repeated = report(client, a_sub, a_generation["generation_id"], key=report_key)
    assert repeated["report_id"] == saved["report_id"] and repeated["reused"]
    report(client, a_sub, a_generation["generation_id"], frequency="week")
    identifier = saved["report_id"]
    detail = client.get(f"/v1/reports/{identifier}?subscription_id={a_sub}")
    exported = client.get(f"/api/v1/reports/{identifier}/export?subscription_id={a_sub}")
    assert exported.status_code == detail.status_code == 200
    assert exported.json()["content"] == detail.json()["content"] == saved["content"]
    assert exported.headers["content-type"] == "application/json"
    assert (
        exported.headers["content-disposition"]
        == f'attachment; filename="report-{identifier}.json"'
    )
    assert exported.headers["cache-control"] == "no-store"
    assert len(client.get(f"/v1/subscriptions/{a_sub}/reports").json()["items"]) == 2
    assert client.get("/v1/subscriptions").json()["items"][0]["subscription_id"] == a_sub
    assert other.get(f"/v1/reports/{identifier}/export?subscription_id={b_sub}").status_code == 404
    assert len(b_generation["recommendation_ids"]) == 1


def test_patch_cas_same_route_key_collision_and_unsubscribe_history(r15_http_engine, shared_store):
    _, token = actor(r15_http_engine, "fixture-http-edit-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    sub = subscription(client, "alpha")
    identifier = sub["subscription_id"]
    generated = generation(client, identifier)
    saved = report(client, identifier, generated["generation_id"])
    key = uuid4().hex
    payload = {"expected_version": 1, "enabled": False}
    first = client.patch(
        f"/v1/subscriptions/{identifier}", json=payload, headers={"Idempotency-Key": key}
    )
    replay = client.patch(
        f"/api/v1/subscriptions/{identifier}", json=payload, headers={"Idempotency-Key": key}
    )
    assert first.status_code == replay.status_code == 200 and replay.json()["version"] == 2
    stale_cas = client.patch(
        f"/v1/subscriptions/{identifier}", json=payload, headers={"Idempotency-Key": uuid4().hex}
    )
    assert stale_cas.status_code == 409
    different_shape = client.patch(
        f"/v1/subscriptions/{identifier}",
        json={"expected_version": 2, "spec": {"product_keys": ["PyPI:beta"]}},
        headers={"Idempotency-Key": key},
    )
    assert different_shape.status_code == 409
    stopped = generation(client, identifier)
    assert stopped["recommendation_ids"] == []
    detail = client.get(f"/v1/reports/{saved['report_id']}?subscription_id={identifier}").json()
    listed = client.get(f"/v1/subscriptions/{identifier}/reports").json()["items"][0]
    assert (
        detail["current_reason"]
        == listed["current_reason"]
        == "subscription_disabled_history_retained"
    )
    assert detail["content"] == saved["content"]
    replacement = client.patch(
        f"/v1/subscriptions/{identifier}",
        json={"expected_version": 2, "spec": {"product_keys": ["PyPI:beta"]}},
        headers={"Idempotency-Key": uuid4().hex},
    )
    assert replacement.status_code == 200 and replacement.json()["version"] == 3
    changed = client.get(f"/v1/reports/{saved['report_id']}?subscription_id={identifier}").json()
    assert changed["current_status"] == "stale" and changed["content"] == saved["content"]


@pytest.mark.parametrize("fault_phase", ["before_cursor_execute", "after_cursor_execute"])
def test_receipt_insert_failure_rolls_back_effect_and_receipt(
    r15_http_engine, shared_store, fault_phase
):
    owner, token = actor(r15_http_engine, "fixture-http-fault-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    key = uuid4().hex

    def fail(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO recommendation_mutation_receipts"):
            raise DBAPIError(
                "fixture injected receipt insert failure", None, RuntimeError("fixture")
            )

    event.listen(r15_http_engine, fault_phase, fail)
    try:
        response = post(
            client, "/v1/subscriptions", {"spec": {"product_keys": ["PyPI:alpha"]}}, key=key
        )
    finally:
        event.remove(r15_http_engine, fault_phase, fail)
    assert response.status_code == 503
    assert row_count(r15_http_engine, r15_subscriptions, owner.user_id) == 0
    assert row_count(r15_http_engine, recommendation_mutation_receipts, owner.user_id) == 0
    assert (
        post(
            client, "/v1/subscriptions", {"spec": {"product_keys": ["PyPI:alpha"]}}, key=key
        ).status_code
        == 201
    )


def test_concurrent_same_key_has_one_effect(r15_http_engine, shared_store):
    owner, token = actor(r15_http_engine, "fixture-http-race-" + uuid4().hex)
    key = uuid4().hex

    def create():
        client = client_for(r15_http_engine, token, shared_store)
        return post(
            client, "/v1/subscriptions", {"spec": {"product_keys": ["PyPI:alpha"]}}, key=key
        )

    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(create) for _ in range(2)]
        responses = [future.result() for future in futures]
    assert [response.status_code for response in responses] == [201, 201]
    assert responses[0].json()["subscription_id"] == responses[1].json()["subscription_id"]
    assert row_count(r15_http_engine, r15_subscriptions, owner.user_id) == 1
    assert row_count(r15_http_engine, recommendation_mutation_receipts, owner.user_id) == 1


@pytest.mark.parametrize("attack", ["origin", "csrf", "expired", "body_tenant", "missing_key"])
def test_http_auth_and_input_failures_create_no_effect(r15_http_engine, shared_store, attack):
    owner, token = actor(r15_http_engine, "fixture-http-auth-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    payload = {"spec": {"product_keys": ["PyPI:alpha"]}}
    headers = {"Idempotency-Key": uuid4().hex}
    if attack == "origin":
        headers["Origin"] = "https://other.invalid"
    if attack == "csrf":
        headers["X-CSRF-Token"] = "wrong"
    if attack == "expired":
        with r15_http_engine.begin() as connection:
            connection.execute(
                update(auth_sessions)
                .where(auth_sessions.c.user_id == owner.user_id)
                .values(
                    issued_at=datetime.now(UTC) - timedelta(hours=1),
                    expires_at=datetime.now(UTC) - timedelta(seconds=1),
                )
            )
    if attack == "body_tenant":
        payload["tenant_id"] = "other"
    if attack == "missing_key":
        headers = {}
    response = client.post("/v1/subscriptions", json=payload, headers=headers)
    assert (
        response.status_code
        == {"origin": 403, "csrf": 403, "expired": 401, "body_tenant": 400, "missing_key": 400}[
            attack
        ]
    )
    assert row_count(r15_http_engine, r15_subscriptions, owner.user_id) == 0
    assert row_count(r15_http_engine, recommendation_mutation_receipts, owner.user_id) == 0
    if attack == "expired":
        assert "Max-Age=0" in response.headers["set-cookie"]


def test_replay_and_export_use_fresh_source_parent_acl_and_withdrawal(
    r15_http_engine, shared_store
):
    product = "fresh-" + uuid4().hex
    source = semantic_source(r15_http_engine, shared_store, package=product)
    _, token = actor(r15_http_engine, "fixture-http-history-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    sub_id = subscription(client, product)["subscription_id"]
    key = uuid4().hex
    generated = generation(client, sub_id, key=key)
    saved = report(client, sub_id, generated["generation_id"])
    frozen = canonical_json_bytes(saved["content"])
    add_withdrawal(r15_http_engine, source)
    exported = client.get(f"/v1/reports/{saved['report_id']}/export?subscription_id={sub_id}")
    assert exported.status_code == 200 and exported.json()["current_status"] == "withdrawn"
    assert canonical_json_bytes(exported.json()["content"]) == frozen
    assert generation(client, sub_id, key=key)["generation_id"] == generated["generation_id"]
    with r15_http_engine.begin() as connection:
        connection.execute(
            text("UPDATE sources SET visibility='tenant',tenant_id=:tenant WHERE source_id=:id"),
            {"tenant": "fixture-http-denied-" + uuid4().hex, "id": source["source_id"]},
        )
    replay = post(client, f"/v1/subscriptions/{sub_id}/generate", key=key)
    assert replay.status_code == 404
    assert (
        client.get(f"/v1/reports/{saved['report_id']}/export?subscription_id={sub_id}").status_code
        == 404
    )


def test_empty_report_becomes_stale_and_preserves_history_on_http_read_list_export(
    r15_http_engine, shared_store
):
    product = "empty-" + uuid4().hex
    source = semantic_source(r15_http_engine, shared_store, package=product)
    _, token = actor(r15_http_engine, "fixture-http-empty-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    sub_id = subscription(client, product)["subscription_id"]
    with r15_http_engine.begin() as connection:
        connection.execute(
            update(claims).where(claims.c.claim_id == source["claim_id"]).values(freshness="stale")
        )
    generated = generation(client, sub_id)
    saved = report(client, sub_id, generated["generation_id"])
    assert not saved["content"]["report"]["intelligence_updates"]
    frozen = canonical_json_bytes(saved["content"])
    with r15_http_engine.begin() as connection:
        connection.execute(
            update(claims)
            .where(claims.c.claim_id == source["claim_id"])
            .values(freshness="current")
        )
        connection.execute(
            update(scope_epochs)
            .where(scope_epochs.c.scope_key == "public")
            .values(epoch=scope_epochs.c.epoch + 1)
        )
    assert len(generation(client, sub_id)["recommendation_ids"]) == 1
    for path in [
        f"/v1/reports/{saved['report_id']}?subscription_id={sub_id}",
        f"/v1/reports/{saved['report_id']}/export?subscription_id={sub_id}",
    ]:
        current = client.get(path)
        assert current.status_code == 200 and current.json()["current_status"] == "stale"
        assert canonical_json_bytes(current.json()["content"]) == frozen
    assert (
        client.get(f"/v1/subscriptions/{sub_id}/reports").json()["items"][0]["current_status"]
        == "stale"
    )


def test_immutable_receipt_unique_shape_and_raw_key_not_stored(r15_http_engine, shared_store):
    owner, token = actor(r15_http_engine, "fixture-http-immut-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    key = uuid4().hex
    created = post(client, "/v1/subscriptions", {"spec": {"product_keys": ["PyPI:alpha"]}}, key=key)
    assert created.status_code == 201
    with r15_http_engine.connect() as connection:
        row = (
            connection.execute(
                select(recommendation_mutation_receipts).where(
                    recommendation_mutation_receipts.c.user_id == owner.user_id
                )
            )
            .mappings()
            .one()
        )
        assert row["idempotency_sha256"] == hashlib.sha256(key.encode()).hexdigest()
        assert key not in json.dumps(dict(row), default=str) and token not in json.dumps(
            dict(row), default=str
        )
    for statement in [
        "UPDATE recommendation_mutation_receipts SET status_code=200 WHERE id=:id",
        "DELETE FROM recommendation_mutation_receipts WHERE id=:id",
    ]:
        with pytest.raises(IntegrityError), r15_http_engine.begin() as connection:
            connection.execute(text(statement), {"id": row["id"]})


def test_owner_scoped_pagination_and_foreign_cursor(r15_http_engine, shared_store):
    _, token = actor(r15_http_engine, "fixture-http-pages-" + uuid4().hex)
    _, other_token = actor(r15_http_engine, "fixture-http-pages-other-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    other = client_for(r15_http_engine, other_token, shared_store)
    first = subscription(client, "alpha")
    second = subscription(client, "beta")
    foreign = subscription(other, "alpha")
    page = client.get("/v1/subscriptions?limit=1").json()
    assert len(page["items"]) == 1 and page["next_cursor"]
    next_page = client.get("/v1/subscriptions?limit=1&cursor=" + page["next_cursor"]).json()
    assert {page["items"][0]["subscription_id"], next_page["items"][0]["subscription_id"]} == {
        first["subscription_id"],
        second["subscription_id"],
    }
    assert client.get("/v1/subscriptions?cursor=" + foreign["subscription_id"]).status_code == 404


def test_asset_subscription_replay_rechecks_role_and_foreign_tenant(
    r15_http_engine, shared_store, tmp_path
):
    seeded = seed(r15_http_engine, tmp_path)
    snapshot = asset(r15_http_engine, seeded)
    owner = seeded["asset_actor"]
    client = client_for(r15_http_engine, seeded["asset_token"], shared_store)
    key = uuid4().hex
    payload = {"spec": {"asset_ids": [snapshot.asset_id]}}
    first = post(client, "/v1/subscriptions", payload, key=key)
    assert first.status_code == 201
    _, other_token = actor(r15_http_engine, "fixture-http-other-asset-" + uuid4().hex)
    other = client_for(r15_http_engine, other_token, shared_store)
    assert post(other, "/v1/subscriptions", payload).status_code == 404
    with r15_http_engine.begin() as connection:
        connection.execute(
            update(users).where(users.c.user_id == owner.user_id).values(role=Role.VIEWER.value)
        )
    assert post(client, "/v1/subscriptions", payload, key=key).status_code == 403
    assert client.get("/v1/subscriptions/" + first.json()["subscription_id"]).status_code == 403
    assert row_count(r15_http_engine, r15_subscriptions, owner.user_id) == 1


def test_role_change_between_http_auth_and_locked_write_rejects(
    r15_http_engine, shared_store, monkeypatch
):
    owner, token = actor(r15_http_engine, "fixture-http-role-race-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    original = AuthenticationSessionService.build_access_scope

    def change_role(authentication, supplied_token):
        before = original(authentication, supplied_token)
        with r15_http_engine.begin() as connection:
            connection.execute(
                update(users).where(users.c.user_id == owner.user_id).values(role=Role.VIEWER.value)
            )
        return before

    monkeypatch.setattr(AuthenticationSessionService, "build_access_scope", change_role)
    assert (
        post(client, "/v1/subscriptions", {"spec": {"product_keys": ["PyPI:alpha"]}}).status_code
        == 403
    )
    assert row_count(r15_http_engine, r15_subscriptions, owner.user_id) == 0
    assert row_count(r15_http_engine, recommendation_mutation_receipts, owner.user_id) == 0


def test_http_generation_owner_lock_orders_unsubscribe(r15_http_engine, shared_store):
    product = "lock-" + uuid4().hex
    semantic_source(r15_http_engine, shared_store, package=product)
    _, token = actor(r15_http_engine, "fixture-http-unsubscribe-race-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    sub_id = subscription(client, product)["subscription_id"]
    inserted, release = Event(), Event()

    def pause(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("INSERT INTO r15_generations"):
            inserted.set()
            assert release.wait(10)

    event.listen(r15_http_engine, "before_cursor_execute", pause)
    try:
        with ThreadPoolExecutor(max_workers=2) as workers:
            active = workers.submit(generation, client, sub_id)
            assert inserted.wait(10)
            other = client_for(r15_http_engine, token, shared_store)
            stopping = workers.submit(
                other.patch,
                f"/v1/subscriptions/{sub_id}",
                json={"expected_version": 1, "enabled": False},
                headers={"Idempotency-Key": uuid4().hex},
            )
            assert not stopping.done()
            release.set()
            assert len(active.result()["recommendation_ids"]) == 1
            assert stopping.result().status_code == 200
    finally:
        release.set()
        event.remove(r15_http_engine, "before_cursor_execute", pause)
    assert generation(client, sub_id)["recommendation_ids"] == []


def test_http_server_scope_over_2000_is_partial_not_complete(r15_http_engine, shared_store):
    source = semantic_source(r15_http_engine, shared_store, package="budget-" + uuid4().hex)
    _, token = actor(r15_http_engine, "fixture-http-budget-" + uuid4().hex)
    client = client_for(r15_http_engine, token, shared_store)
    sub_id = subscription(client, "budget-absent")["subscription_id"]
    stamp = datetime.now(UTC)
    identifiers = [str(uuid4()) for _ in range(2001)]
    with r15_http_engine.begin() as connection:
        connection.execute(
            insert(events),
            [
                {
                    "event_id": value,
                    "event_type": "vulnerability",
                    "title": "Explicit scope budget fixture",
                    "status": "active",
                    "first_seen_at": stamp,
                    "visibility": "public",
                    "tenant_id": None,
                    "scope_key": "public",
                }
                for value in identifiers
            ],
        )
        connection.execute(
            insert(event_documents),
            [
                {
                    "event_id": value,
                    "revision_id": source["revision_id"],
                    "active": True,
                    "associated_at": stamp,
                }
                for value in identifiers
            ],
        )
    result = generation(client, sub_id)
    assert result["partial"] and any(gap["code"] == "input_scope_partial" for gap in result["gaps"])
    with r15_http_engine.connect() as connection:
        stored = (
            connection.execute(
                select(r15_generations).where(r15_generations.c.id == result["generation_id"])
            )
            .mappings()
            .one()
        )
        assert 1 <= len(stored["result_payload"]["event_ids"]) <= 2000
        assert stored["cutoff_at"] <= datetime.now(UTC) and stored["result_payload"]["partial"]
