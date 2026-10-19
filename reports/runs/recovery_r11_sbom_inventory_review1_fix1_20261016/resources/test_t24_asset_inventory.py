"""T24真实隔离PG：合成manifest显式fixture，不计外部live或生产迁移通过。"""

import hashlib
import json
import os
import secrets
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Event
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine, event, func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_intel.api.auth_routes import build_auth_router
from ai_intel.api.auth_state import PgAuthenticationStateStore, auth_sessions
from ai_intel.api.authentication import AuthenticationSessionService, DatabaseUserDirectory
from ai_intel.assets.inventory import AssetNameConflictError, InvalidAssetCursor, InventoryService
from ai_intel.assets.inventory_models import asset_import_receipts, asset_snapshots, assets
from ai_intel.assets.inventory_routes import build_inventory_router
from ai_intel.assets.manifest_parser import ManifestValidationError
from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import job_runs, outbox_events, users
from ai_intel.knowledge.persistence_models import change_events

pytestmark = pytest.mark.real_pg
OBSERVED = datetime(2026, 10, 16, 0, tzinfo=UTC)
ORIGIN = "http://localhost:5173"


@pytest.fixture(scope="module")
def inventory_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database.startswith("test_dianzi_r11_inventory_review_fix1_")
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
    assert os.environ.get("DIANZI_TEST_RUN_ID", "").startswith("r11_inventory_review_fix1_")
    engine = create_engine(
        url,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=15000 -c lock_timeout=5000",
        },
        hide_parameters=True,
    )
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) in {
            "0016_source_response_receipts",
            "0018_asset_inventory",
        }
        assert connection.scalar(text("SELECT to_regclass('asset_snapshots')")) is not None
    yield engine
    engine.dispose()


def scope(engine, tenant=None, role=Role.TENANT_ADMIN):
    tenant = tenant or "test-tenant-" + uuid4().hex
    identity = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            insert(users).values(
                user_id=identity,
                username="test-user-" + identity,
                password_hash="synthetic-unused-password-hash",
                tenant_id=tenant,
                role=role.value,
                created_at=datetime.now(UTC),
            )
        )
    return AccessScope.for_authenticated_user(identity, tenant, role)


def manifest(version="1.0", **extra):
    return json.dumps(
        {
            "format_version": 1,
            "components": [{"ecosystem": "pypi", "package_name": "langchain", "version": version}],
            **extra,
        },
        separators=(",", ":"),
    ).encode()


def save(engine, access, raw=None, key=None, **options):
    with Session(engine) as session, session.begin():
        return InventoryService(session, access).import_manifest(
            manifest() if raw is None else raw,
            manifest_format=options.pop("manifest_format", "json_manifest_v1"),
            display_name=options.pop("display_name", "Synthetic test asset"),
            source_version=options.pop("source_version", "synthetic-test-1"),
            observed_at=options.pop("observed_at", OBSERVED),
            idempotency_key=key or str(uuid4()),
            **options,
        )


def counts(engine, tenant):
    with engine.connect() as connection:
        return {
            "assets": connection.scalar(
                select(func.count()).select_from(assets).where(assets.c.tenant_id == tenant)
            ),
            "snapshots": connection.scalar(
                select(func.count())
                .select_from(asset_snapshots)
                .where(asset_snapshots.c.tenant_id == tenant)
            ),
            "receipts": connection.scalar(
                select(func.count())
                .select_from(asset_import_receipts)
                .where(asset_import_receipts.c.tenant_id == tenant)
            ),
            "changes": connection.scalar(
                select(func.count())
                .select_from(change_events)
                .where(change_events.c.scope_key == "tenant:" + tenant)
            ),
            "jobs": connection.scalar(
                select(func.count()).select_from(job_runs).where(job_runs.c.tenant_id == tenant)
            ),
            "outbox": connection.scalar(
                select(func.count())
                .select_from(outbox_events.join(job_runs))
                .where(job_runs.c.tenant_id == tenant)
            ),
        }


def test_t24_c01_json_csv_same_canonical_snapshot_and_raw_bytes(inventory_engine):
    access = scope(inventory_engine)
    raw = (
        b'{ "format_version": 1, "components": [{"ecosystem":"pypi",'
        b'"package_name":"langchain","version":"1.0"}] }'
    )
    first = save(inventory_engine, access, raw)
    csv = b"Eco,Name,Ver\r\npypi,langchain,1.0\r\n"
    second = save(
        inventory_engine,
        access,
        csv,
        asset_id=first.asset_id,
        manifest_format="csv_components_v1",
        csv_column_mapping={"ecosystem": "Eco", "package_name": "Name", "version": "Ver"},
    )
    assert second.reused and second.snapshot.snapshot_id == first.snapshot.snapshot_id
    assert second.snapshot.snapshot_sha256 == first.snapshot.snapshot_sha256
    with inventory_engine.connect() as connection:
        row = (
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == first.snapshot.snapshot_id
                )
            )
            .mappings()
            .one()
        )
        assert bytes(row["raw_input"]) == raw
        assert row["raw_input_sha256"] == hashlib.sha256(raw).hexdigest()
        assert row["manifest_sha256"] == first.snapshot.snapshot_sha256
        assert row["canonical_payload"]["components"][0]["version"] == "1.0"
    assert counts(inventory_engine, access.tenant_id) == {
        "assets": 1,
        "snapshots": 1,
        "receipts": 2,
        "changes": 1,
        "jobs": 1,
        "outbox": 1,
    }


def test_t24_c02_key_replay_across_connections_preserves_original_snapshot(inventory_engine):
    access = scope(inventory_engine)
    key = str(uuid4())
    first = save(inventory_engine, access, key=key)
    changed = save(inventory_engine, access, manifest("2.0"), asset_id=first.asset_id)
    replay = save(inventory_engine, access, key=key)
    assert replay.reused and replay.snapshot.snapshot_id == first.snapshot.snapshot_id
    with Session(inventory_engine) as session:
        current = InventoryService(session, access).read_asset(first.asset_id)
        assert current.current_snapshot_id == changed.snapshot.snapshot_id
    assert counts(inventory_engine, access.tenant_id)["changes"] == 2


@pytest.mark.parametrize(
    "changed",
    [
        {"display_name": "Different"},
        {"source_version": "synthetic-2"},
        {"observed_at": OBSERVED + timedelta(seconds=1)},
        {"request_route": "asset-snapshots"},
    ],
)
def test_request_parameter_identity_and_route_partition(inventory_engine, changed):
    access = scope(inventory_engine)
    key = str(uuid4())
    save(inventory_engine, access, key=key)
    if "request_route" in changed:
        other = save(inventory_engine, access, key=key, **changed)
        assert not other.reused
        assert counts(inventory_engine, access.tenant_id)["assets"] == 2
    else:
        with pytest.raises(IdempotencyConflictError):
            save(inventory_engine, access, key=key, **changed)
        assert counts(inventory_engine, access.tenant_id)["snapshots"] == 1


def test_different_raw_or_csv_mapping_same_key_conflicts(inventory_engine):
    access = scope(inventory_engine)
    key = str(uuid4())
    csv = b"Eco,Name,Ver,Other\npypi,langchain,1.0,2.0\n"
    mapping = {
        "ecosystem": "Eco",
        "package_name": "Name",
        "version": "Ver",
        "display_name": "Other",
    }
    save(
        inventory_engine,
        access,
        csv,
        key,
        manifest_format="csv_components_v1",
        csv_column_mapping=mapping,
    )
    with pytest.raises(IdempotencyConflictError):
        save(
            inventory_engine,
            access,
            csv,
            key,
            manifest_format="csv_components_v1",
            csv_column_mapping={**mapping, "version": "Other", "display_name": "Ver"},
        )
    with pytest.raises(IdempotencyConflictError):
        save(
            inventory_engine,
            access,
            csv.replace(b",1.0,", b',"1.0",'),
            key,
            manifest_format="csv_components_v1",
            csv_column_mapping=mapping,
        )


def test_t24_c03_version_history_current_and_a_b_a(inventory_engine):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    second = save(inventory_engine, access, manifest("2.0"), asset_id=first.asset_id)
    third = save(inventory_engine, access, asset_id=first.asset_id)
    assert [value.snapshot.snapshot_number for value in (first, second, third)] == [1, 2, 3]
    assert third.snapshot.snapshot_id != first.snapshot.snapshot_id
    assert third.snapshot.snapshot_sha256 == first.snapshot.snapshot_sha256
    with Session(inventory_engine) as session:
        reader = InventoryService(session, access)
        assert reader.read_asset(first.asset_id).current_snapshot_id == third.snapshot.snapshot_id
        assert (
            reader.get_snapshot(first.asset_id, first.snapshot.snapshot_id).components[0].version
            == "1.0"
        )
        assert (
            reader.get_snapshot(first.asset_id, second.snapshot.snapshot_id).components[0].version
            == "2.0"
        )
        history = reader.list_snapshots(first.asset_id)
        assert [item.snapshot_number for item in history.items] == [3, 2, 1]
    with inventory_engine.connect() as connection:
        predecessors = (
            connection.execute(
                select(asset_snapshots.c.previous_snapshot_id)
                .where(asset_snapshots.c.asset_id == first.asset_id)
                .order_by(asset_snapshots.c.snapshot_number)
            )
            .scalars()
            .all()
        )
        assert predecessors == [None, first.snapshot.snapshot_id, second.snapshot.snapshot_id]


def test_t24_c04_unknown_manifest_preserves_no_exclusion_and_source_fields(inventory_engine):
    access = scope(inventory_engine)
    saved = save(
        inventory_engine,
        access,
        manifest(
            None,
            inventory_completeness="unknown",
            configuration={"trust_remote_code": None},
        ),
    )
    assert saved.snapshot.inventory_completeness == "unknown"
    assert saved.snapshot.declared_scope == ()
    assert saved.snapshot.components[0].version is None
    assert saved.snapshot.components[0].image_digest is None
    assert saved.snapshot.tool_permissions is None
    assert saved.snapshot.input_channels is None and saved.snapshot.network_exposure is None
    fields = {field.name: field for field in saved.snapshot.configuration}
    assert fields["trust_remote_code"].value is None
    assert fields["trust_remote_code"].source_field_locator == "/configuration/trust_remote_code"
    assert "excluded" not in saved.model_dump_json()


@pytest.mark.parametrize(
    "raw,options",
    [
        (
            b"Eco,Name,Ver\npypi,langchain\n",
            {
                "manifest_format": "csv_components_v1",
                "csv_column_mapping": {
                    "ecosystem": "Eco",
                    "package_name": "Name",
                    "version": "Ver",
                },
            },
        ),
        (
            b"Eco,Name,Ver\n" + b"pypi,langchain,1\n" * 10001,
            {
                "manifest_format": "csv_components_v1",
                "csv_column_mapping": {
                    "ecosystem": "Eco",
                    "package_name": "Name",
                    "version": "Ver",
                },
            },
        ),
        (b"x" * 1048577, {}),
        (b'{"format_version":1,"components":[],"file_path":"C:/private.txt"}', {}),
    ],
    ids=["csv_wrong_columns", "csv_10001_rows", "upload_1mib_plus_one", "private_file_path"],
)
def test_t24_c05_invalid_inputs_never_partially_commit(inventory_engine, raw, options):
    access = scope(inventory_engine)
    with pytest.raises(ManifestValidationError):
        save(inventory_engine, access, raw, **options)
    assert counts(inventory_engine, access.tenant_id) == {
        "assets": 0,
        "snapshots": 0,
        "receipts": 0,
        "changes": 0,
        "jobs": 0,
        "outbox": 0,
    }


def test_t24_c06_cross_tenant_asset_is_same_as_absent_and_read_denied(inventory_engine):
    owner = scope(inventory_engine)
    other = scope(inventory_engine)
    first = save(inventory_engine, owner)
    for identity in (first.asset_id, str(uuid4())):
        with pytest.raises(CrossTenantAccessError, match="resource not found"):
            save(inventory_engine, other, asset_id=identity)
        with Session(inventory_engine) as session, pytest.raises(CrossTenantAccessError):
            InventoryService(session, other).read_asset(identity)
    assert counts(inventory_engine, other.tenant_id)["snapshots"] == 0


def test_actor_receipts_same_key_do_not_cross_principal(inventory_engine):
    first_access = scope(inventory_engine)
    second_access = scope(inventory_engine, first_access.tenant_id)
    key = str(uuid4())
    first = save(inventory_engine, first_access, key=key)
    second = save(inventory_engine, second_access, key=key)
    assert first.asset_id != second.asset_id
    assert counts(inventory_engine, first_access.tenant_id)["receipts"] == 2


def test_concurrent_same_request_creates_one_snapshot_and_one_outbox(inventory_engine):
    access = scope(inventory_engine)
    key = str(uuid4())
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: save(inventory_engine, access, key=key), range(4)))
    assert len({item.snapshot.snapshot_id for item in results}) == 1
    assert sum(not item.reused for item in results) == 1
    assert counts(inventory_engine, access.tenant_id) == {
        "assets": 1,
        "snapshots": 1,
        "receipts": 1,
        "changes": 1,
        "jobs": 1,
        "outbox": 1,
    }


@pytest.mark.parametrize("version", ["1.0", "2.0"])
def test_existing_asset_name_change_is_explicit_conflict_without_partial_write(
    inventory_engine, version
):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    before = counts(inventory_engine, access.tenant_id)
    with pytest.raises(AssetNameConflictError):
        save(
            inventory_engine,
            access,
            manifest(version),
            asset_id=first.asset_id,
            display_name="Changed asset name",
        )
    assert counts(inventory_engine, access.tenant_id) == before
    with Session(inventory_engine) as session:
        assert (
            InventoryService(session, access).read_asset(first.asset_id).display_name
            == "Synthetic test asset"
        )


def test_concurrent_versions_have_linear_history_and_current(inventory_engine):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(
            pool.map(
                lambda number: save(
                    inventory_engine, access, manifest(str(number)), asset_id=first.asset_id
                ),
                range(2, 6),
            )
        )
    assert sorted(item.snapshot.snapshot_number for item in results) == [2, 3, 4, 5]
    with Session(inventory_engine) as session:
        current = InventoryService(session, access).read_asset(first.asset_id)
        assert current.snapshot.snapshot_number == 5
    assert counts(inventory_engine, access.tenant_id)["changes"] == 5


def test_concurrent_different_body_same_key_has_one_commit_and_one_conflict(inventory_engine):
    access = scope(inventory_engine)
    key = str(uuid4())

    def import_version(version):
        try:
            return save(inventory_engine, access, manifest(version), key=key)
        except IdempotencyConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(import_version, ["1.0", "2.0"]))
    assert sum(result == "conflict" for result in results) == 1
    assert counts(inventory_engine, access.tenant_id) == {
        "assets": 1,
        "snapshots": 1,
        "receipts": 1,
        "changes": 1,
        "jobs": 1,
        "outbox": 1,
    }


def test_asset_row_then_scope_lock_does_not_invert_assessment_order(inventory_engine):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    row_attempted = Event()

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "FROM assets" in statement and "FOR UPDATE" in statement:
            row_attempted.set()

    with Session(inventory_engine) as assessment, assessment.begin():
        assessment.execute(
            select(assets).where(assets.c.asset_id == first.asset_id).with_for_update()
        ).first()
        event.listen(inventory_engine, "before_cursor_execute", observe)
        try:
            with ThreadPoolExecutor(max_workers=1) as pool:
                writer = pool.submit(
                    save, inventory_engine, access, manifest("2.0"), asset_id=first.asset_id
                )
                assert row_attempted.wait(5)
                assessment.execute(
                    select(
                        func.pg_advisory_xact_lock(
                            func.hashtextextended(
                                "knowledge-publication:tenant:" + access.tenant_id, 0
                            )
                        )
                    )
                )
                assessment.commit()
                assert writer.result(5).snapshot.snapshot_number == 2
        finally:
            event.remove(inventory_engine, "before_cursor_execute", observe)


def test_concurrent_identical_current_with_different_keys_does_not_publish_twice(inventory_engine):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(
            pool.map(
                lambda _: save(inventory_engine, access, manifest("2.0"), asset_id=first.asset_id),
                range(2),
            )
        )
    assert sum(not result.reused for result in results) == 1
    assert len({result.snapshot.snapshot_id for result in results}) == 1
    assert counts(inventory_engine, access.tenant_id)["changes"] == 2


def test_failed_change_write_rolls_back_asset_snapshot_pointer_and_receipt(
    inventory_engine, monkeypatch
):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    before = counts(inventory_engine, access.tenant_id)

    def fail(*args, **kwargs):
        raise RuntimeError("synthetic change write failure")

    monkeypatch.setattr("ai_intel.assets.inventory.save_change_publication", fail)
    with pytest.raises(RuntimeError, match="synthetic change write failure"):
        save(inventory_engine, access, manifest("2.0"), asset_id=first.asset_id)
    assert counts(inventory_engine, access.tenant_id) == before
    with Session(inventory_engine) as session:
        assert (
            InventoryService(session, access).read_asset(first.asset_id).current_snapshot_id
            == first.snapshot.snapshot_id
        )


def test_database_rejects_snapshot_mutation_and_missing_current(inventory_engine):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    for statement in (
        update(asset_snapshots)
        .where(asset_snapshots.c.snapshot_id == first.snapshot.snapshot_id)
        .values(source_version="changed"),
        asset_snapshots.delete().where(asset_snapshots.c.snapshot_id == first.snapshot.snapshot_id),
        update(assets).where(assets.c.asset_id == first.asset_id).values(current_snapshot_id=None),
    ):
        with pytest.raises(IntegrityError), inventory_engine.begin() as connection:
            connection.execute(statement)
    with pytest.raises(IntegrityError), inventory_engine.begin() as connection:
        connection.execute(
            insert(assets).values(
                asset_id=str(uuid4()),
                tenant_id=access.tenant_id,
                display_name="Missing",
                created_at=OBSERVED,
                updated_at=OBSERVED,
            )
        )


def test_database_composite_fk_rejects_foreign_tenant_current(inventory_engine):
    owner = scope(inventory_engine)
    other = scope(inventory_engine)
    first, foreign = save(inventory_engine, owner), save(inventory_engine, other)
    with pytest.raises(IntegrityError), inventory_engine.begin() as connection:
        connection.execute(
            update(assets)
            .where(assets.c.asset_id == first.asset_id)
            .values(current_snapshot_id=foreign.snapshot.snapshot_id)
        )


def test_database_predecessor_receipt_and_actor_fk_cannot_cross_or_delete_history(inventory_engine):
    owner = scope(inventory_engine)
    other = scope(inventory_engine)
    first, foreign = save(inventory_engine, owner), save(inventory_engine, other)
    with inventory_engine.connect() as connection:
        original = dict(
            connection.execute(
                select(asset_snapshots).where(
                    asset_snapshots.c.snapshot_id == first.snapshot.snapshot_id
                )
            )
            .mappings()
            .one()
        )
    original.update(
        snapshot_id=str(uuid4()),
        snapshot_number=2,
        previous_snapshot_id=foreign.snapshot.snapshot_id,
    )
    with pytest.raises(IntegrityError), inventory_engine.begin() as connection:
        connection.execute(insert(asset_snapshots).values(**original))
    with pytest.raises(IntegrityError), inventory_engine.begin() as connection:
        connection.execute(
            insert(asset_import_receipts).values(
                tenant_id=owner.tenant_id,
                actor_user_id=owner.user_id,
                request_route="asset-imports",
                idempotency_key=str(uuid4()),
                request_sha256="0" * 64,
                asset_id=first.asset_id,
                snapshot_id=foreign.snapshot.snapshot_id,
                created_at=OBSERVED,
            )
        )
    with pytest.raises(IntegrityError), inventory_engine.begin() as connection:
        connection.execute(users.delete().where(users.c.user_id == owner.user_id))


def test_stable_cursor_ignores_pointer_update_and_rejects_scope_or_filter_reuse(inventory_engine):
    access = scope(inventory_engine)
    saved = [save(inventory_engine, access) for _ in range(4)]
    with Session(inventory_engine) as session:
        page = InventoryService(session, access).list_assets(limit=2)
    save(inventory_engine, access, manifest("2.0"), asset_id=saved[0].asset_id)
    with Session(inventory_engine) as session:
        reader = InventoryService(session, access)
        second = reader.list_assets(limit=2, cursor=page.next_cursor)
        assert [item.asset_id for item in (*page.items, *second.items)] == [
            item.asset_id for item in saved
        ]
        assert second.next_cursor is None
        with pytest.raises(InvalidAssetCursor):
            reader.list_assets(cursor=page.next_cursor, product="different")
        with pytest.raises(InvalidAssetCursor):
            InventoryService(session, scope(inventory_engine)).list_assets(cursor=page.next_cursor)
        assert len(reader.list_assets(product="langchain").items) == 4
        assert reader.list_assets(product="absent").items == ()


def test_history_cursor_preserves_old_page_after_new_version(inventory_engine):
    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    for version in ("2.0", "3.0"):
        save(inventory_engine, access, manifest(version), asset_id=first.asset_id)
    with Session(inventory_engine) as session:
        page = InventoryService(session, access).list_snapshots(first.asset_id, limit=2)
    save(inventory_engine, access, manifest("4.0"), asset_id=first.asset_id)
    with Session(inventory_engine) as session:
        last = InventoryService(session, access).list_snapshots(
            first.asset_id, cursor=page.next_cursor
        )
        assert [item.snapshot_number for item in (*page.items, *last.items)] == [3, 2, 1]


def test_boolean_history_cursor_and_foreign_snapshot_are_rejected(inventory_engine):
    import base64

    access = scope(inventory_engine)
    first = save(inventory_engine, access)
    other = save(inventory_engine, access)
    encoded = base64.urlsafe_b64encode(
        json.dumps(["snapshots-v1", access.tenant_id, first.asset_id, True]).encode()
    ).decode()
    with Session(inventory_engine) as session:
        reader = InventoryService(session, access)
        with pytest.raises(InvalidAssetCursor):
            reader.list_snapshots(first.asset_id, cursor=encoded)
        with pytest.raises(CrossTenantAccessError):
            reader.get_snapshot(first.asset_id, other.snapshot.snapshot_id)


@pytest.fixture
def inventory_api(inventory_engine, register_sensitive_failure_value):
    authentication = AuthenticationSessionService(
        DatabaseUserDirectory(inventory_engine),
        (ORIGIN,),
        False,
        state_store=PgAuthenticationStateStore(inventory_engine),
    )
    app = FastAPI()
    settings = ApplicationSettings(app_env="test", data_mode="fixture")
    app.include_router(build_auth_router(lambda: authentication, settings), prefix="/api")
    app.include_router(
        build_inventory_router(lambda: authentication, inventory_engine), prefix="/api"
    )
    clients = []

    def login(role=Role.TENANT_ADMIN, tenant=None):
        tenant = tenant or "test-api-" + uuid4().hex
        username, password = "test-" + uuid4().hex, secrets.token_urlsafe(24)
        register_sensitive_failure_value(SecretStr(password))
        account = authentication.create_precreated_user(username, password, tenant, role)
        client = TestClient(app)
        clients.append(client)
        response = client.post(
            "/api/auth/login",
            headers={"Origin": ORIGIN},
            json={"username": username, "password": password},
        )
        assert response.status_code == 200
        csrf = response.json()["csrf_token"]
        register_sensitive_failure_value(SecretStr(csrf))
        register_sensitive_failure_value(SecretStr(client.cookies.get("ai_intel_session")))
        headers = {"Origin": ORIGIN, "X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())}
        return client, headers, account

    yield login, authentication
    for client in clients:
        client.close()


def snapshot_request(**extra):
    return {
        "display_name": "Synthetic API asset",
        "source_version": "synthetic-api-1",
        "observed_at": OBSERVED.isoformat(),
        "snapshot": json.loads(manifest()),
        **extra,
    }


def test_api_write_current_history_idempotency_and_upload_bytes(inventory_engine, inventory_api):
    login, _ = inventory_api
    client, headers, account = login()
    first = client.post("/api/asset-snapshots", json=snapshot_request(), headers=headers)
    assert first.status_code == 201
    identity = first.json()["asset_id"]
    assert (
        client.post("/api/asset-snapshots", json=snapshot_request(), headers=headers).json()[
            "snapshot"
        ]["snapshot_id"]
        == first.json()["snapshot"]["snapshot_id"]
    )
    headers = {**headers, "Idempotency-Key": str(uuid4())}
    raw = b"Eco,Name,Ver\r\npypi,langchain,2.0\r\n"
    uploaded = client.post(
        "/api/asset-imports",
        content=raw,
        params={
            "asset_id": identity,
            "display_name": "Synthetic API asset",
            "source_version": "synthetic-api-2",
            "observed_at": OBSERVED.isoformat(),
            "manifest_format": "csv_components_v1",
            "csv_column_mapping": json.dumps(
                {"ecosystem": "Eco", "package_name": "Name", "version": "Ver"}
            ),
        },
        headers=headers,
    )
    assert uploaded.status_code == 201
    snapshot_id = uploaded.json()["snapshot"]["snapshot_id"]
    assert client.get("/api/assets/" + identity).json()["current_snapshot_id"] == snapshot_id
    history = client.get(f"/api/assets/{identity}/snapshots").json()
    assert [item["snapshot_number"] for item in history["items"]] == [2, 1]
    old_id = first.json()["snapshot"]["snapshot_id"]
    assert (
        client.get(f"/api/assets/{identity}/snapshots/{old_id}").json()["components"][0]["version"]
        == "1.0"
    )
    assert "raw_input" not in client.get("/api/assets/" + identity).text
    assert counts(inventory_engine, account.tenant_id)["outbox"] == 2
    with inventory_engine.connect() as connection:
        row = (
            connection.execute(
                select(asset_snapshots).where(asset_snapshots.c.snapshot_id == snapshot_id)
            )
            .mappings()
            .one()
        )
        assert (
            bytes(row["raw_input"]) == raw
            and row["raw_input_sha256"] == hashlib.sha256(raw).hexdigest()
        )


def test_api_cross_tenant_and_unknown_asset_are_indistinguishable(inventory_api):
    login, _ = inventory_api
    owner, headers, _ = login()
    created = owner.post("/api/asset-snapshots", json=snapshot_request(), headers=headers).json()
    foreign, other_headers, _ = login()
    hidden = foreign.get("/api/assets/" + created["asset_id"])
    absent = foreign.get("/api/assets/" + str(uuid4()))
    assert hidden.status_code == absent.status_code == 404
    assert hidden.json()["error"]["code"] == absent.json()["error"]["code"] == "not_found"
    rejected = foreign.post(
        "/api/asset-snapshots",
        json=snapshot_request(asset_id=created["asset_id"]),
        headers=other_headers,
    )
    assert rejected.status_code == 404
    assert foreign.get("/api/assets").json()["items"] == []


@pytest.mark.parametrize(
    "change,status",
    [
        ({"Origin": "http://untrusted.invalid"}, 403),
        ({"X-CSRF-Token": "bad"}, 403),
        ({"Idempotency-Key": ""}, 422),
    ],
)
def test_api_security_headers_reject_without_writes(
    inventory_engine, inventory_api, change, status
):
    login, _ = inventory_api
    client, headers, account = login()
    response = client.post(
        "/api/asset-snapshots", json=snapshot_request(), headers={**headers, **change}
    )
    assert response.status_code == status
    assert counts(inventory_engine, account.tenant_id)["assets"] == 0


@pytest.mark.parametrize("role", [Role.ANALYST, Role.VIEWER])
def test_api_server_role_controls_write_and_read(inventory_engine, inventory_api, role):
    login, _ = inventory_api
    client, headers, account = login(role=role)
    assert (
        client.post("/api/asset-snapshots", json=snapshot_request(), headers=headers).status_code
        == 403
    )
    assert client.get("/api/assets").status_code == (200 if role == Role.ANALYST else 403)
    assert counts(inventory_engine, account.tenant_id)["assets"] == 0


@pytest.mark.parametrize(
    "extra",
    [
        {"tenant_id": "forged"},
        {"role": "system_admin"},
        {"file_path": "C:/private"},
        {"observed_at": "2026-10-16T00:00:00"},
    ],
)
def test_api_rejects_spoofed_identity_paths_and_unknown_time(
    inventory_engine, inventory_api, extra
):
    login, _ = inventory_api
    client, headers, account = login()
    response = client.post("/api/asset-snapshots", json=snapshot_request(**extra), headers=headers)
    assert response.status_code == 422
    assert "forged" not in response.text and "C:/private" not in response.text
    assert counts(inventory_engine, account.tenant_id)["assets"] == 0


def test_api_idempotency_conflict_and_upload_size_limit(inventory_engine, inventory_api):
    login, _ = inventory_api
    client, headers, account = login()
    assert (
        client.post("/api/asset-snapshots", json=snapshot_request(), headers=headers).status_code
        == 201
    )
    conflict = client.post(
        "/api/asset-snapshots", json=snapshot_request(display_name="different"), headers=headers
    )
    assert conflict.status_code == 409
    size = client.post("/api/asset-imports", content=b"x" * 1048577, headers=headers)
    assert size.status_code == 413
    assert counts(inventory_engine, account.tenant_id)["assets"] == 1


def test_api_duplicate_json_keys_and_name_mutation_are_explicitly_rejected(
    inventory_engine, inventory_api
):
    login, _ = inventory_api
    client, headers, account = login()
    first = client.post("/api/asset-snapshots", json=snapshot_request(), headers=headers)
    identity = first.json()["asset_id"]
    renamed = client.post(
        "/api/asset-snapshots",
        json=snapshot_request(asset_id=identity, display_name="Changed"),
        headers={**headers, "Idempotency-Key": str(uuid4())},
    )
    assert renamed.status_code == 409 and renamed.json()["error"]["code"] == "asset_name_conflict"
    duplicate = (
        b'{"display_name":"fixture","source_version":"test",'
        b'"observed_at":"2026-10-16T00:00:00Z","snapshot":{"format_version":1,'
        b'"components":[{"ecosystem":"pypi","package_name":"langchain",'
        b'"version":"1","version":"2"}]}}'
    )
    assert (
        client.post("/api/asset-snapshots", content=duplicate, headers=headers).status_code == 422
    )
    assert counts(inventory_engine, account.tenant_id)["snapshots"] == 1


def test_api_revoked_or_role_changed_before_transaction_cannot_write(
    inventory_engine, inventory_api, monkeypatch
):
    login, authentication = inventory_api
    client, headers, account = login()
    original = authentication.build_access_scope

    def change_role(token):
        initial = original(token)
        with inventory_engine.begin() as connection:
            connection.execute(
                update(users)
                .where(users.c.user_id == account.user_id)
                .values(role=Role.ANALYST.value)
            )
        return initial

    monkeypatch.setattr(authentication, "build_access_scope", change_role)
    assert (
        client.post("/api/asset-snapshots", json=snapshot_request(), headers=headers).status_code
        == 403
    )
    assert counts(inventory_engine, account.tenant_id)["assets"] == 0


def test_authentication_lock_orders_role_change_after_asset_commit(
    inventory_engine, inventory_api, monkeypatch
):
    login, _ = inventory_api
    client, headers, account = login()
    entered, release, role_started = Event(), Event(), Event()
    original = InventoryService.import_manifest

    def paused(self, *args, **kwargs):
        entered.set()
        assert release.wait(5)
        return original(self, *args, **kwargs)

    def change_role():
        role_started.set()
        with inventory_engine.begin() as connection:
            connection.execute(
                update(users)
                .where(users.c.user_id == account.user_id)
                .values(role=Role.ANALYST.value)
            )

    monkeypatch.setattr(InventoryService, "import_manifest", paused)
    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(
            client.post, "/api/asset-snapshots", json=snapshot_request(), headers=headers
        )
        assert entered.wait(5)
        role_change = pool.submit(change_role)
        assert role_started.wait(5)
        assert not role_change.done()
        release.set()
        assert request.result(5).status_code == 201
        role_change.result(5)
    assert (
        client.post(
            "/api/asset-snapshots",
            json=snapshot_request(),
            headers={**headers, "Idempotency-Key": str(uuid4())},
        ).status_code
        == 403
    )


def test_api_revoked_session_returns_401(inventory_engine, inventory_api):
    login, _ = inventory_api
    client, headers, account = login()
    with inventory_engine.begin() as connection:
        connection.execute(
            update(auth_sessions)
            .where(auth_sessions.c.user_id == account.user_id)
            .values(revoked_at=datetime.now(UTC))
        )
    assert (
        client.post("/api/asset-snapshots", json=snapshot_request(), headers=headers).status_code
        == 401
    )
    assert client.get("/api/assets").status_code == 401


def test_service_write_permission_and_null_tenant_denied(inventory_engine):
    analyst = scope(inventory_engine, role=Role.ANALYST)
    with pytest.raises(PermissionDeniedError):
        save(inventory_engine, analyst)
    global_admin = AccessScope.for_authenticated_user(str(uuid4()), None, Role.SYSTEM_ADMIN)
    with pytest.raises(PermissionDeniedError):
        save(inventory_engine, global_admin)
