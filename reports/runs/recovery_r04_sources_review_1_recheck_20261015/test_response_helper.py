"""Independent response helper integrity and real database error checks."""

from dataclasses import replace
from datetime import UTC, datetime
from threading import Thread

import pytest
from sqlalchemy import event, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from test_independent_boundaries import own_schema_engine as own_schema_engine
from test_independent_boundaries import seed_document
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.knowledge.models import content_objects, fetch_attempts
from ai_intel.knowledge.revisions import cleanup_unreferenced_object, register_response_content


def test_response_helper_keeps_exact_bytes_and_one_pg_record(own_schema_engine, tmp_path):
    payload = '原始\x00响应🙂'.encode('utf-8')
    store = ContentStore(tmp_path / 'objects')
    when = datetime(2026, 10, 15, 4, 0, 0, 123456, tzinfo=UTC)
    with Session(own_schema_engine) as session, session.begin():
        first = register_response_content(session, store, payload, when)
        second = register_response_content(session, store, payload, when)
        assert first == second
        assert store.read_verified(first.content_hash) == payload
        rows = session.execute(select(content_objects)).mappings().all()
        assert len(rows) == 1
        assert rows[0]['size_bytes'] == len(payload) and rows[0]['created_at'] == when


@pytest.mark.parametrize('payload,when', [
    ('not-bytes', datetime.now(UTC)),
    (bytearray(b'not-immutable'), datetime.now(UTC)),
    (b'naive-time', datetime(2026, 10, 15)),
])
def test_response_helper_rejects_invalid_input_without_registration(
    own_schema_engine, tmp_path, payload, when
):
    store = ContentStore(tmp_path / 'objects')
    with Session(own_schema_engine) as session, session.begin():
        with pytest.raises(ValueError):
            register_response_content(session, store, payload, when)
        assert session.execute(select(content_objects)).all() == []


@pytest.mark.parametrize('failure', ['hash', 'size', 'read_mismatch', 'store_error', 'read_error'])
def test_response_helper_never_registers_bad_or_unreadable_storage(
    own_schema_engine, tmp_path, failure
):
    real_store = ContentStore(tmp_path / 'objects')

    class BrokenStore:
        def store_bytes(self, payload):
            if failure == 'store_error':
                raise OSError('independent storage write failure')
            stored = real_store.store_bytes(payload)
            if failure == 'hash':
                return replace(stored, content_hash='0' * 64)
            if failure == 'size':
                return replace(stored, size_bytes=stored.size_bytes + 1)
            return stored

        def read_verified(self, content_hash):
            if failure == 'read_error':
                raise OSError('independent storage read failure')
            if failure == 'read_mismatch':
                return b'wrong response bytes'
            return real_store.read_verified(content_hash)

    expected_error = OSError if failure.endswith('_error') else ValueError
    with Session(own_schema_engine) as session, session.begin():
        with pytest.raises(expected_error):
            register_response_content(session, BrokenStore(), b'exact original bytes', datetime.now(UTC))
        assert session.execute(select(content_objects)).all() == []


def test_gc_23503_competition_returns_false_keeps_bytes_and_session_usable(
    own_schema_engine, tmp_path
):
    store = ContentStore(tmp_path / 'objects')
    when = datetime.now(UTC)
    with Session(own_schema_engine) as session, session.begin():
        seed_document(session, 'document', 'public', None)
        source_id = session.scalar(text("SELECT source_id FROM documents WHERE document_id='document'"))
        stored = register_response_content(session, store, b'raw response', when)
    wrote = []

    def create_response_reference():
        with Session(own_schema_engine) as writer, writer.begin():
            writer.execute(fetch_attempts.insert().values(attempt_id='response-attempt',
                source_id=source_id, attempted_at=when, outcome='succeeded',
                new_event_count=0, response_content_hash=stored.content_hash))
        wrote.append(True)

    with Session(own_schema_engine) as collector, collector.begin():
        collector_connection = collector.connection()

        def interleave(_connection, _cursor, statement, _parameters, _context, _executemany):
            if statement.startswith('DELETE FROM content_objects') and not wrote:
                writer = Thread(target=create_response_reference)
                writer.start()
                writer.join(timeout=5)
                assert not writer.is_alive() and wrote == [True]

        event.listen(collector_connection, 'before_cursor_execute', interleave)
        try:
            assert cleanup_unreferenced_object(collector, store, stored.content_hash) is False
        finally:
            event.remove(collector_connection, 'before_cursor_execute', interleave)
        assert collector.scalar(select(content_objects.c.content_hash)
            .where(content_objects.c.content_hash == stored.content_hash)) == stored.content_hash
        assert store.read_verified(stored.content_hash) == b'raw response'


def test_gc_propagates_non_fk_database_error_without_deleting_bytes(
    own_schema_engine, tmp_path
):
    store = ContentStore(tmp_path / 'objects')
    with Session(own_schema_engine) as session, session.begin():
        stored = register_response_content(session, store, b'kept response', datetime.now(UTC))
        session.execute(text("CREATE FUNCTION review_refuse_cleanup() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'independent check failure' "
            "USING ERRCODE='23514'; END $$"))
        session.execute(text("CREATE TRIGGER review_refuse_cleanup BEFORE DELETE ON content_objects "
            "FOR EACH ROW EXECUTE FUNCTION review_refuse_cleanup()"))
    with Session(own_schema_engine) as collector, collector.begin():
        with pytest.raises(IntegrityError) as rejected:
            cleanup_unreferenced_object(collector, store, stored.content_hash)
        assert rejected.value.orig.sqlstate == '23514'
        assert collector.scalar(select(content_objects.c.content_hash)) == stored.content_hash
        assert store.read_verified(stored.content_hash) == b'kept response'
