"""New independent raw-input and observed PG lock boundaries for the frozen CAS fix."""

import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.orm import Session

from test_independent_boundaries import prepared_case
from test_original_pg_resourceadapt import original
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.knowledge.models import content_objects, documents
from ai_intel.knowledge.revisions import cleanup_unreferenced_object, save_document_revision

RUN = Path(__file__).resolve().parent
DAMAGED = b"independent review: damaged CAS object"


def record(name, **values):
    with (RUN / "independent_fix_observations.jsonl").open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(dict(case=name, fixture_data=True, human_labels=0, **values), ensure_ascii=False) + "\n")


def payload(engine, assessment_id):
    with engine.connect() as connection:
        return connection.scalar(select(assessment_results.c.result_payload).where(assessment_results.c.assessment_id == assessment_id))


def wait_for_pg_lock(engine, backend_pid):
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            row = connection.execute(text("SELECT wait_event_type,wait_event FROM pg_stat_activity WHERE pid=:pid"), dict(pid=backend_pid)).first()
        if row and row[0] == "Lock":
            return dict(wait_event_type=row[0], wait_event=row[1], backend_pid=backend_pid)
        time.sleep(0.02)
    raise AssertionError("expected actual PostgreSQL lock wait was not observed")


@pytest.mark.parametrize("operation", ["commit", "read", "replay"])
@pytest.mark.parametrize("damage", ["missing", "equal_length_replacement", "pg_size"])
def test_raw_error_never_returns_current_or_overwrites_history(pg_engine, tmp_path, operation, damage):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    receipt = service.commit(prepared) if operation != "commit" else None
    saved = payload(pg_engine, receipt.assessment_id) if receipt else None
    source_hash = prepared.inputs.sources[0].content_sha256
    before = original.count(pg_engine, assessment_results)
    path = seeded["store"].object_path_for_hash(source_hash)
    if damage == "missing":
        path.unlink()
        failure, match = FileNotFoundError, None
    elif damage == "equal_length_replacement":
        body = path.read_bytes()
        path.write_bytes(bytes([body[0] ^ 1]) + body[1:])
        failure, match = ValueError, "hash mismatch"
    else:
        with pg_engine.begin() as connection:
            original_size = connection.scalar(select(content_objects.c.size_bytes).where(content_objects.c.content_hash == source_hash))
            connection.execute(update(content_objects).where(content_objects.c.content_hash == source_hash).values(size_bytes=content_objects.c.size_bytes + 1))
        failure, match = ValueError, "source_blob_integrity_invalid"
    try:
        with pytest.raises(failure, match=match):
            service.read(receipt.assessment_id) if operation == "read" else service.commit(prepared)
        assert original.count(pg_engine, assessment_results) == before
        if receipt:
            assert payload(pg_engine, receipt.assessment_id) == saved
    finally:
        if damage == "pg_size":
            with pg_engine.begin() as connection:
                connection.execute(update(content_objects).where(content_objects.c.content_hash == source_hash).values(size_bytes=original_size))
    record("raw_error", operation=operation, damage=damage, exception=failure.__name__, result_row_delta=0, historical_payload_unchanged=receipt is not None)


@pytest.mark.parametrize("damage", ["replacement", "missing"])
def test_actual_pg_lock_wait_releases_then_rechecks_raw(pg_engine, tmp_path, damage):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    attempting = Event()
    backend_pid = []
    before = original.count(pg_engine, assessment_results)

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "FROM document_revisions JOIN documents" in statement and "FOR SHARE" in statement:
            backend_pid.append(connection.connection.driver_connection.info.backend_pid)
            attempting.set()

    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with pg_engine.connect() as connection, connection.begin():
            connection.execute(update(documents).where(documents.c.document_id == seeded["document_id"]).values(title=documents.c.title))
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(service.commit, prepared)
                assert attempting.wait(5)
                observed = wait_for_pg_lock(pg_engine, backend_pid[0])
                assert not pending.done()
                path = seeded["store"].object_path_for_hash(prepared.inputs.sources[0].content_sha256)
                if damage == "replacement":
                    path.write_bytes(DAMAGED)
                else:
                    path.unlink()
                connection.commit()
                with pytest.raises(ValueError if damage == "replacement" else FileNotFoundError):
                    pending.result(timeout=10)
        assert original.count(pg_engine, assessment_results) == before
        record("actual_parent_lock_wait", damage=damage, result_row_delta=0, **observed)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe)


def test_normal_revision_writer_is_actually_locked_during_raw_check_then_result_is_stale(pg_engine, tmp_path, monkeypatch):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    reading, attempting, release = Event(), Event(), Event()
    writer_pid = []
    real_read = seeded["store"].read_verified

    def paused_read(digest):
        reading.set()
        assert release.wait(5)
        return real_read(digest)

    def observe(connection, cursor, statement, parameters, context, executemany):
        if "FROM documents" in statement and "FOR UPDATE" in statement:
            writer_pid.append(connection.connection.driver_connection.info.backend_pid)
            attempting.set()

    def write():
        with Session(pg_engine) as session, session.begin():
            return save_document_revision(session, seeded["store"], seeded["document_id"], b"independent legitimate revised source bytes", "tenant", seeded["tenant"], original.STAMP)

    monkeypatch.setattr(seeded["store"], "read_verified", paused_read)
    event.listen(pg_engine, "before_cursor_execute", observe)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(service.commit, prepared)
            assert reading.wait(5)
            writer = pool.submit(write)
            assert attempting.wait(5)
            observed = wait_for_pg_lock(pg_engine, writer_pid[0])
            assert not writer.done()
            release.set()
            receipt = pending.result(timeout=10)
            saved = payload(pg_engine, receipt.assessment_id)
            revision = writer.result(timeout=10)
        assert receipt.freshness == "current"
        assert revision.revision_id != seeded["revision_id"]
        assert service.read(receipt.assessment_id).freshness == "stale"
        assert payload(pg_engine, receipt.assessment_id) == saved
        record("normal_writer_blocked", persisted_history_unchanged=True, before_writer="current", after_writer="stale", **observed)
    finally:
        release.set()
        event.remove(pg_engine, "before_cursor_execute", observe)


def test_source_acl_failure_precedes_opening_raw(pg_engine, tmp_path, monkeypatch):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path, public=True)
    receipt = service.commit(prepared)
    before = original.count(pg_engine, assessment_results)
    with pg_engine.begin() as connection:
        connection.execute(text("UPDATE sources SET visibility='tenant',tenant_id=:tenant WHERE source_id=:source"), dict(tenant="independent-unrelated-private-tenant", source=seeded["source_id"]))

    def unopened(digest):
        raise AssertionError("ACL error must happen before source raw IO")

    monkeypatch.setattr(seeded["store"], "read_verified", unopened)
    with pytest.raises(original.CrossTenantAccessError, match="resource not found"):
        service.read(receipt.assessment_id)
    with pytest.raises(original.CrossTenantAccessError, match="resource not found"):
        service.commit(prepared)
    assert original.count(pg_engine, assessment_results) == before


def test_healthy_replay_reopens_raw_and_normal_gc_preserves_reference(pg_engine, tmp_path, monkeypatch):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    digest = prepared.inputs.sources[0].content_sha256
    body = seeded["store"].read_verified(digest)
    assert seeded["store"].store_bytes(body).content_hash == digest
    with Session(pg_engine) as session, session.begin():
        assert not cleanup_unreferenced_object(session, seeded["store"], digest)
    checks = []
    real_read = seeded["store"].read_verified

    def tracked(digest):
        checks.append(digest)
        return real_read(digest)

    monkeypatch.setattr(seeded["store"], "read_verified", tracked)
    receipt = service.commit(prepared)
    first_count = len(checks)
    assert first_count > 0
    assert service.read(receipt.assessment_id).freshness == "current"
    assert len(checks) > first_count
    read_count = len(checks)
    replay = service.commit(prepared)
    assert replay.assessment_id == receipt.assessment_id and replay.reused
    assert len(checks) > read_count
    saved = payload(pg_engine, receipt.assessment_id)
    seeded["store"].object_path_for_hash(digest).write_bytes(DAMAGED)
    with pytest.raises(ValueError, match="existing object corrupted"):
        seeded["store"].store_bytes(body)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.commit(prepared)
    assert payload(pg_engine, receipt.assessment_id) == saved
    record("healthy_replay_then_damage", raw_reopens=len(checks), result_history_sha256=hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest(), replay_identity_preserved=True, damaged_replay_denied=True)
