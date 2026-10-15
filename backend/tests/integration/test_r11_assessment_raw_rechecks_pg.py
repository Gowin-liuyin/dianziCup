"""Real-PG CAS rechecks reproduce independent Must inputs; approvals remain synthetic."""

from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from sqlalchemy import event, select, update
from sqlalchemy.orm import Session
from test_r11_pg_assessments import actor, assessor, asset, count, publish, seed
from test_r11_pg_assessments import pg_engine as pg_engine

from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.knowledge.models import document_revisions, documents
from ai_intel.knowledge.revisions import cleanup_unreferenced_object

pytestmark = pytest.mark.real_pg
DAMAGED_RAW = b"independent review: damaged CAS object"


def prepared_case(engine, directory, *, public=False):
    seeded = seed(engine, directory, public=public)
    publish(engine, seeded)
    imported = asset(engine, seeded)
    service = assessor(engine, seeded)
    prepared = service.prepare(
        imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
    )
    return seeded, service, prepared


def corrupt_raw(seeded, prepared):
    digest = prepared.inputs.sources[0].content_sha256
    seeded["store"].object_path_for_hash(digest).write_bytes(DAMAGED_RAW)


def test_prepare_then_corrupt_raw_must_not_commit_current(pg_engine, tmp_path):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    corrupt_raw(seeded, prepared)
    before = count(pg_engine, assessment_results)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.commit(prepared)
    assert count(pg_engine, assessment_results) == before


def test_current_history_read_checks_raw_integrity(pg_engine, tmp_path):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    receipt = service.commit(prepared)
    corrupt_raw(seeded, prepared)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.read(receipt.assessment_id)


@pytest.mark.parametrize("operation", ["commit", "read", "replay"])
def test_missing_raw_never_writes_or_returns_current(pg_engine, tmp_path, operation):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    receipt = service.commit(prepared) if operation in {"read", "replay"} else None
    digest = prepared.inputs.sources[0].content_sha256
    seeded["store"].delete_object(digest)
    before = count(pg_engine, assessment_results)
    with pytest.raises(FileNotFoundError):
        if operation == "read":
            service.read(receipt.assessment_id)
        else:
            service.commit(prepared)
    assert count(pg_engine, assessment_results) == before
    if receipt is not None:
        with pg_engine.connect() as connection:
            saved = connection.scalar(
                select(assessment_results.c.result_payload).where(
                    assessment_results.c.assessment_id == receipt.assessment_id
                )
            )
        assert saved == receipt.model_dump(mode="json")


def test_commit_read_and_replay_do_not_cache_raw_verification(pg_engine, tmp_path, monkeypatch):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    real_read = seeded["store"].read_verified
    checked = []

    def tracked_read(content_hash):
        checked.append(content_hash)
        return real_read(content_hash)

    monkeypatch.setattr(seeded["store"], "read_verified", tracked_read)
    first = service.commit(prepared)
    assert checked and first.freshness == "current"
    commit_checks = len(checked)
    assert service.read(first.assessment_id).freshness == "current"
    assert len(checked) > commit_checks
    read_checks = len(checked)
    assert service.commit(prepared).reused
    assert len(checked) > read_checks
    corrupt_raw(seeded, prepared)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.commit(prepared)


@pytest.mark.parametrize("operation", ["commit", "read"])
@pytest.mark.parametrize("damage", ["size", "hash"])
def test_verified_store_response_is_independently_size_hash_checked(
    pg_engine,
    tmp_path,
    monkeypatch,
    operation,
    damage,
):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    receipt = service.commit(prepared) if operation == "read" else None
    real_read = seeded["store"].read_verified

    def altered_read(digest):
        body = real_read(digest)
        return body + b"!" if damage == "size" else bytes([body[0] ^ 1]) + body[1:]

    monkeypatch.setattr(seeded["store"], "read_verified", altered_read)
    before = count(pg_engine, assessment_results)
    with pytest.raises(ValueError, match="source_blob_integrity_invalid"):
        service.read(receipt.assessment_id) if operation == "read" else service.commit(prepared)
    assert count(pg_engine, assessment_results) == before


@pytest.mark.parametrize("damage", ["replacement", "missing"])
def test_damage_during_pg_parent_lock_wait_is_not_hidden_by_preparation_cache(
    pg_engine, tmp_path, damage
):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    attempting = Event()

    def observe_lock(connection, cursor, statement, parameters, context, executemany):
        if "FROM document_revisions JOIN documents" in statement and "FOR SHARE" in statement:
            attempting.set()

    before = count(pg_engine, assessment_results)
    event.listen(pg_engine, "before_cursor_execute", observe_lock)
    try:
        with pg_engine.connect() as connection, connection.begin():
            connection.execute(
                update(documents)
                .where(documents.c.document_id == seeded["document_id"])
                .values(title=documents.c.title)
            )
            with ThreadPoolExecutor(max_workers=1) as pool:
                pending = pool.submit(service.commit, prepared)
                assert attempting.wait(5)
                if damage == "replacement":
                    corrupt_raw(seeded, prepared)
                else:
                    seeded["store"].delete_object(prepared.inputs.sources[0].content_sha256)
                connection.commit()
                failure = ValueError if damage == "replacement" else FileNotFoundError
                with pytest.raises(failure):
                    pending.result(timeout=10)
    finally:
        event.remove(pg_engine, "before_cursor_execute", observe_lock)
    assert count(pg_engine, assessment_results) == before


def test_raw_verification_occurs_while_pg_revision_writer_is_blocked(
    pg_engine,
    tmp_path,
    monkeypatch,
):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    reading, writer_started, release = Event(), Event(), Event()
    real_read = seeded["store"].read_verified

    def paused_read(content_hash):
        reading.set()
        assert release.wait(5)
        return real_read(content_hash)

    def observe_write(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("UPDATE document_revisions SET"):
            writer_started.set()

    def revise():
        with pg_engine.begin() as connection:
            connection.execute(
                update(document_revisions)
                .where(document_revisions.c.revision_id == seeded["revision_id"])
                .values(parse_status="failed")
            )

    monkeypatch.setattr(seeded["store"], "read_verified", paused_read)
    event.listen(pg_engine, "before_cursor_execute", observe_write)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(service.commit, prepared)
            assert reading.wait(5)
            writer = pool.submit(revise)
            assert writer_started.wait(5)
            assert not writer.done()
            release.set()
            receipt = pending.result(timeout=10)
            writer.result(timeout=10)
        assert receipt.freshness == "current"
        assert service.read(receipt.assessment_id).freshness == "stale"
    finally:
        release.set()
        event.remove(pg_engine, "before_cursor_execute", observe_write)


def test_invisible_assessment_never_opens_source_raw(pg_engine, tmp_path, monkeypatch):
    seeded, service, prepared = prepared_case(pg_engine, tmp_path)
    receipt = service.commit(prepared)
    _, token = actor(pg_engine, "fixture-unrelated-tenant")

    def unexpected_read(content_hash):
        raise AssertionError("invisible evidence must not be opened")

    monkeypatch.setattr(seeded["store"], "read_verified", unexpected_read)
    from ai_intel.assessment.assessment_service import AssessmentService

    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        AssessmentService(pg_engine, token, seeded["store"]).read(receipt.assessment_id)


def test_normal_store_write_and_gc_cannot_replace_or_delete_referenced_raw(pg_engine, tmp_path):
    seeded, _, prepared = prepared_case(pg_engine, tmp_path)
    digest = prepared.inputs.sources[0].content_sha256
    body = seeded["store"].read_verified(digest)
    assert seeded["store"].store_bytes(body).content_hash == digest
    with Session(pg_engine) as session, session.begin():
        assert not cleanup_unreferenced_object(session, seeded["store"], digest)
    assert seeded["store"].read_verified(digest) == body
    corrupt_raw(seeded, prepared)
    with pytest.raises(ValueError, match="existing object corrupted"):
        seeded["store"].store_bytes(body)
    assert seeded["store"].object_path_for_hash(digest).read_bytes() == DAMAGED_RAW
