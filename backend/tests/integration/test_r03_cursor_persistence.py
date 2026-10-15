"""R03 游标在独立真实 PostgreSQL 中的事务、租约、重放和恢复验证。"""

from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from threading import Barrier
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion.cursor_repository import (
    PersistedPageEntry,
    SourceCursorLease,
    SourceCursorRepository,
    SourceLeaseLostError,
    StaleSourceCursorError,
    make_page_key,
)
from ai_intel.ingestion.scheduler import CursorCommitError
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    job_payloads,
    job_runs,
    outbox_events,
    source_cursors,
    source_page_receipts,
)
from ai_intel.knowledge.revisions import save_document_revision

pytestmark = pytest.mark.real_pg
NOW = datetime(2026, 10, 15, tzinfo=UTC)
ADMIN = AccessScope.for_authenticated_user("scheduler", None, Role.SYSTEM_ADMIN)


@dataclass
class Clock:
    now: datetime = NOW

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture()
def cursor_engine(isolated_test_database_url: str):
    """仅消费主控已经迁移的 R03 隔离库；本文件不迁移、不删除历史记录。"""
    engine = create_engine(
        isolated_test_database_url,
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=20000 -c lock_timeout=5000",
        },
    )
    with engine.connect() as connection:
        assert (
            connection.execute(text("SELECT current_database()")).scalar_one()
            == engine.url.database
        )
        assert connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one() == (
            "0012_source_page_fingerprint"
        )
    try:
        yield engine
    finally:
        engine.dispose()


def seed_source(engine: Engine, tenant_id: str | None = None) -> str:
    source_id = str(uuid4())
    with engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES (:id,:id,'vendor_advisory','https://example.invalid',:visibility,:tenant,:now)"
            ),
            {
                "id": source_id,
                "visibility": "tenant" if tenant_id else "public",
                "tenant": tenant_id,
                "now": NOW,
            },
        )
    return source_id


def claim(repository: SourceCursorRepository, *, stream_kind="live") -> SourceCursorLease:
    lease = repository.claim(
        stream_kind=stream_kind,
        lease_owner="worker",
        window_start=NOW - timedelta(days=7),
        window_end=NOW,
    )
    assert lease is not None
    return lease


def persist_revision(store: ContentStore, source_id: str, *, tenant_id: str | None = None):
    def persist(session: Session, entry: dict[str, object]) -> PersistedPageEntry:
        document_id = str(entry["document_id"])
        visibility = "tenant" if tenant_id else "public"
        if (
            session.execute(
                select(documents.c.document_id).where(documents.c.document_id == document_id)
            ).first()
            is None
        ):
            stored = store.store_bytes(b"")
            session.execute(
                insert(content_objects)
                .values(content_hash=stored.content_hash, size_bytes=0, created_at=NOW)
                .on_conflict_do_nothing()
            )
            session.execute(
                documents.insert().values(
                    document_id=document_id,
                    source_id=source_id,
                    kind="advisory",
                    title="cursor test",
                    published_at=None,
                    retrieved_at=NOW,
                    content_hash=stored.content_hash,
                    visibility=visibility,
                    tenant_id=tenant_id,
                    schema_version=1,
                )
            )
        saved = save_document_revision(
            session,
            store,
            document_id,
            str(entry.get("body", "A")).encode(),
            visibility,
            tenant_id,
            NOW,
        )
        return PersistedPageEntry(revision_id=saved.revision_id)

    return persist


def commit(
    repository,
    lease,
    entries=(),
    *,
    input_cursor=None,
    output_cursor=None,
    is_last_page=False,
    persist_entry=None,
    watermark=None,
):
    input_cursor = {} if input_cursor is None else input_cursor
    output_cursor = {"page": 1} if output_cursor is None else output_cursor
    return repository.commit_page(
        lease,
        page_key=make_page_key(lease, input_cursor),
        input_cursor=input_cursor,
        output_cursor=output_cursor,
        entries=entries,
        persist_entry=persist_entry or (lambda session, entry: False),
        is_last_page=is_last_page,
        watermark_published_at=watermark,
    )


def row(engine: Engine, source_id: str, stream_kind="live"):
    with engine.connect() as connection:
        return dict(
            connection.execute(
                select(source_cursors).where(
                    source_cursors.c.source_id == source_id,
                    source_cursors.c.stream_kind == stream_kind,
                )
            )
            .mappings()
            .one()
        )


def test_revision_cursor_receipt_survive_session_restart_and_resume_frozen_window(
    cursor_engine, tmp_path
):
    source_id, clock = seed_source(cursor_engine), Clock()
    entry = {"entry_id": "first", "document_id": str(uuid4())}
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        lease = claim(repository)
        receipt = commit(
            repository,
            lease,
            (entry,),
            persist_entry=persist_revision(ContentStore(tmp_path), source_id),
            watermark=NOW - timedelta(days=1),
        )
    assert receipt.entry_count == 1 and len(receipt.revision_ids) == 1
    clock.now += timedelta(seconds=61)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        resumed = repository.claim(
            stream_kind="live", lease_owner="after-crash", window_start=None, window_end=clock.now
        )
        assert resumed.cursor_json == {"page": 1}
        assert resumed.window_end == NOW and resumed.window_start == NOW - timedelta(days=7)
        assert resumed.generation == lease.generation + 1
        saved = session.execute(
            select(document_revisions).where(
                document_revisions.c.revision_id == receipt.revision_ids[0]
            )
        ).one()
        assert saved.document_id == entry["document_id"]
    assert row(cursor_engine, source_id)["watermark_published_at"] is None
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        commit(repository, resumed, input_cursor={"page": 1}, output_cursor={}, is_last_page=True)
    assert row(cursor_engine, source_id)["watermark_published_at"] == NOW - timedelta(days=1)


@pytest.mark.parametrize("failure", ["false", "exception", "missing_reference"])
def test_failed_second_entry_rolls_back_revision_cursor_and_receipt_even_when_caught(
    cursor_engine, tmp_path, failure
):
    source_id = seed_source(cursor_engine)
    entries = (
        {"entry_id": "first", "document_id": str(uuid4())},
        {"entry_id": "second", "document_id": str(uuid4())},
    )
    persist = persist_revision(ContentStore(tmp_path), source_id)

    def failing(session, entry):
        if entry["entry_id"] == "second":
            if failure == "exception":
                raise RuntimeError("fixture persistence interruption")
            return False if failure == "false" else PersistedPageEntry(revision_id=str(uuid4()))
        return persist(session, entry)

    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
        with pytest.raises((RuntimeError, CursorCommitError)):
            commit(repository, lease, entries, persist_entry=failing)
    assert row(cursor_engine, source_id)["cursor_json"]["position"] == {}
    assert row(cursor_engine, source_id)["cursor_json"]["window_complete"] is False
    assert row(cursor_engine, source_id)["last_successful_page"] == 0
    with cursor_engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(documents)
                .where(documents.c.source_id == source_id)
            ).scalar_one()
            == 0
        )
        assert (
            connection.execute(
                select(func.count())
                .select_from(source_page_receipts)
                .where(source_page_receipts.c.source_id == source_id)
            ).scalar_one()
            == 0
        )


def test_missing_entry_identity_prevents_any_callback_and_cursor_advance(cursor_engine):
    source_id, called = seed_source(cursor_engine), []
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        lease = claim(repository)
        with pytest.raises(ValueError, match="entry_id"):
            commit(
                repository,
                lease,
                ({"entry_id": "valid"}, {}),
                persist_entry=lambda session, entry: called.append(entry),
            )
    assert called == [] and row(cursor_engine, source_id)["last_successful_page"] == 0


def test_durable_same_source_scope_recovery_job_allows_page_advance(cursor_engine):
    source_id = seed_source(cursor_engine)

    def persist(session, entry):
        job_id = enqueue_job(
            session,
            None,
            "source_recovery",
            json.dumps({"source_id": source_id, "entry_id": entry["entry_id"]}).encode(),
            NOW,
        )
        return PersistedPageEntry(failed_job_id=job_id)

    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        receipt = commit(
            repository, claim(repository), ({"entry_id": "fetch-failed"},), persist_entry=persist
        )
    assert receipt.revision_ids == () and len(receipt.failed_job_ids) == 1
    with cursor_engine.connect() as connection:
        assert connection.execute(
            select(job_payloads.c.payload).where(job_payloads.c.job_id == receipt.failed_job_ids[0])
        ).scalar_one()
        assert (
            connection.execute(
                select(func.count())
                .select_from(outbox_events)
                .where(outbox_events.c.job_id == receipt.failed_job_ids[0])
            ).scalar_one()
            == 1
        )
    assert row(cursor_engine, source_id)["last_successful_page"] == 1


@pytest.mark.parametrize(
    "failure",
    ["wrong_source", "wrong_entry", "wrong_tenant", "missing_payload", "wrong_digest", "cancelled"],
)
def test_unrecoverable_or_foreign_job_rolls_back_page_and_job(cursor_engine, failure):
    source_id = seed_source(cursor_engine)
    created = []

    def persist(session, entry):
        payload = {
            "source_id": str(uuid4()) if failure == "wrong_source" else source_id,
            "entry_id": "another" if failure == "wrong_entry" else entry["entry_id"],
        }
        job_id = enqueue_job(
            session,
            "another-tenant" if failure == "wrong_tenant" else None,
            "source_recovery",
            json.dumps(payload).encode(),
            NOW,
        )
        created.append(job_id)
        if failure == "missing_payload":
            session.execute(job_payloads.delete().where(job_payloads.c.job_id == job_id))
        if failure == "wrong_digest":
            session.execute(
                job_runs.update()
                .where(job_runs.c.job_id == job_id)
                .values(payload_sha256="invalid")
            )
        if failure == "cancelled":
            session.execute(
                job_runs.update().where(job_runs.c.job_id == job_id).values(status="cancelled")
            )
        return PersistedPageEntry(failed_job_id=job_id)

    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        with pytest.raises(CursorCommitError):
            commit(repository, claim(repository), ({"entry_id": "failed"},), persist_entry=persist)
    assert row(cursor_engine, source_id)["last_successful_page"] == 0
    with cursor_engine.connect() as connection:
        assert (
            connection.execute(
                select(job_runs.c.job_id).where(job_runs.c.job_id.in_(created))
            ).all()
            == []
        )


def test_duplicate_final_page_reuses_receipt_then_new_window_changes_generation(cursor_engine):
    source_id, clock = seed_source(cursor_engine), Clock()
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        lease = claim(repository)
        first = commit(repository, lease, output_cursor={}, is_last_page=True)
        repeated = commit(repository, lease, output_cursor={}, is_last_page=True)
        assert repeated.reused and not first.reused and repeated.committed_at == first.committed_at
        repository.release(lease)
        clock.now += timedelta(days=1)
        new = repository.claim(
            stream_kind="live", lease_owner="worker", window_start=NOW, window_end=clock.now
        )
        assert new.window_end == clock.now and new.generation == lease.generation + 1
        with pytest.raises(SourceLeaseLostError):
            repository.renew(lease)
    assert row(cursor_engine, source_id)["last_successful_page"] == 0


def test_stale_input_and_same_owner_old_generation_cannot_commit_or_renew(cursor_engine):
    source_id, clock = seed_source(cursor_engine), Clock()
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        old = claim(repository)
        clock.now += timedelta(seconds=61)
        with pytest.raises(SourceLeaseLostError):
            commit(repository, old)
        new = claim(repository)
        for action in (lambda: repository.renew(old), lambda: commit(repository, old)):
            with pytest.raises(SourceLeaseLostError):
                action()
        with pytest.raises(StaleSourceCursorError):
            commit(repository, new, input_cursor={"page": 99})
        first = commit(repository, new)
        repeated = commit(repository, new)
        assert repeated.reused and repeated.page_key == first.page_key


def test_lease_expiring_during_callback_rolls_back_saved_revision(cursor_engine, tmp_path):
    source_id, clock = seed_source(cursor_engine), Clock()
    persist = persist_revision(ContentStore(tmp_path), source_id)

    def slow(session, entry):
        result = persist(session, entry)
        clock.now += timedelta(seconds=60)
        return result

    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        with pytest.raises(SourceLeaseLostError):
            commit(
                repository,
                claim(repository),
                ({"entry_id": "slow", "document_id": str(uuid4())},),
                persist_entry=slow,
            )
    assert row(cursor_engine, source_id)["last_successful_page"] == 0
    with cursor_engine.connect() as connection:
        assert (
            connection.execute(
                select(func.count())
                .select_from(documents)
                .where(documents.c.source_id == source_id)
            ).scalar_one()
            == 0
        )


def test_two_workers_cannot_claim_same_source_stream(cursor_engine):
    source_id, barrier = seed_source(cursor_engine), Barrier(2)

    def worker(index):
        with Session(cursor_engine) as session, session.begin():
            repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
            barrier.wait(timeout=10)
            return repository.claim(
                stream_kind="live", lease_owner=f"worker-{index}", window_start=None, window_end=NOW
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        claims = list(pool.map(worker, range(2)))
    assert sum(lease is not None for lease in claims) == 1
    assert row(cursor_engine, source_id)["generation"] == 1


def test_backfill_has_independent_cursor_and_never_changes_live_watermark(cursor_engine):
    source_id = seed_source(cursor_engine)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=Clock())
        live, backfill = claim(repository), claim(repository, stream_kind="backfill")
        commit(repository, live, watermark=NOW - timedelta(days=1), is_last_page=True)
        commit(repository, backfill, output_cursor={"history": 1}, watermark=NOW)
    assert row(cursor_engine, source_id)["watermark_published_at"] == NOW - timedelta(days=1)
    assert row(cursor_engine, source_id, "backfill")["watermark_published_at"] is None
    assert row(cursor_engine, source_id, "backfill")["cursor_json"]["position"] == {"history": 1}


@pytest.mark.parametrize(
    "scope",
    [
        AccessScope.for_authenticated_user("foreign", "other", Role.TENANT_ADMIN),
        AccessScope.for_authenticated_user("viewer", "owner", Role.VIEWER),
    ],
)
def test_configured_source_scope_controls_claim_not_request_scope(cursor_engine, scope):
    source_id = seed_source(cursor_engine, "owner")
    with (
        Session(cursor_engine) as session,
        session.begin(),
        pytest.raises((CrossTenantAccessError, PermissionDeniedError)),
    ):
        claim(SourceCursorRepository(session, scope, source_id, clock=Clock()))


def test_payload_cannot_reassign_source_or_tenant_scope(cursor_engine):
    source_id = seed_source(cursor_engine, "owner")
    scope = AccessScope.for_authenticated_user("owner-admin", "owner", Role.TENANT_ADMIN)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, scope, source_id, clock=Clock())
        lease = claim(repository)
        with pytest.raises(CursorCommitError, match="configured source scope"):
            commit(repository, lease, ({"entry_id": "spoof", "tenant_id": "other"},))


@pytest.mark.parametrize(
    "envelope",
    [
        {"position": {}, "window_complete": "false"},
        {"window_complete": False},
        {"position": [], "window_complete": False},
        {"position": {}, "window_complete": False, "pending_watermark_published_at": "2026-10-15"},
        {"position": {}, "window_complete": False, "pending_watermark_published_at": 1},
    ],
)
def test_malformed_persisted_cursor_envelope_is_rejected(cursor_engine, envelope):
    source_id, clock = seed_source(cursor_engine), Clock()
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        claim(repository)
        session.execute(
            source_cursors.update()
            .where(source_cursors.c.source_id == source_id)
            .values(cursor_json=envelope, lease_owner=None, lease_expires_at=None)
        )
        with pytest.raises((ValueError, CursorCommitError)):
            claim(repository)


def test_existing_raw_cursor_keeps_unfinished_window_during_takeover(cursor_engine):
    source_id, clock = seed_source(cursor_engine), Clock()
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        original = claim(repository)
        session.execute(
            source_cursors.update()
            .where(source_cursors.c.source_id == source_id)
            .values(cursor_json={"position": 123}, lease_owner=None, lease_expires_at=None)
        )
        clock.now += timedelta(days=1)
        resumed = repository.claim(
            stream_kind="live", lease_owner="recovery", window_start=None, window_end=clock.now
        )
        assert resumed.cursor_json == {"position": 123}
        assert resumed.window_end == original.window_end


def test_completed_window_replay_and_overlap_revision_keep_history_without_duplicates(
    cursor_engine, tmp_path
):
    source_id, clock = seed_source(cursor_engine), Clock()
    first = {"entry_id": "first", "document_id": str(uuid4()), "body": "A"}
    second = {"entry_id": "second", "document_id": str(uuid4()), "body": "B"}
    persist = persist_revision(ContentStore(tmp_path), source_id)
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        lease = claim(repository)
        commit(
            repository, lease, (first,), persist_entry=persist, watermark=NOW - timedelta(days=2)
        )
        final = commit(
            repository,
            lease,
            (second,),
            input_cursor={"page": 1},
            output_cursor={},
            is_last_page=True,
            persist_entry=persist,
            watermark=NOW - timedelta(days=1),
        )
    callbacks = []
    with Session(cursor_engine) as session, session.begin():
        repository = SourceCursorRepository(session, ADMIN, source_id, clock=clock)
        repeated = commit(
            repository,
            lease,
            (second,),
            input_cursor={"page": 1},
            output_cursor={},
            is_last_page=True,
            persist_entry=lambda session, entry: callbacks.append(entry),
            watermark=NOW - timedelta(days=1),
        )
        assert repeated.reused and repeated.revision_ids == final.revision_ids
        repository.release(lease)
        clock.now += timedelta(days=1)
        overlap = repository.claim(
            stream_kind="live",
            lease_owner="worker",
            window_start=NOW - timedelta(days=3),
            window_end=clock.now,
        )
        revised = dict(first, body="A revised")
        commit(
            repository,
            overlap,
            (revised,),
            is_last_page=True,
            output_cursor={},
            persist_entry=persist,
        )
    assert callbacks == []
    with cursor_engine.connect() as connection:
        revisions = connection.execute(
            select(document_revisions)
            .where(document_revisions.c.document_id == first["document_id"])
            .order_by(document_revisions.c.revision_number)
        ).all()
        assert len(revisions) == 2
        assert revisions[1].previous_revision_id == revisions[0].revision_id
        assert revisions[0].is_current is False and revisions[1].is_current is True
        assert (
            connection.execute(
                select(func.count())
                .select_from(documents)
                .where(documents.c.source_id == source_id)
            ).scalar_one()
            == 2
        )
    assert row(cursor_engine, source_id)["watermark_published_at"] == NOW - timedelta(days=1)
