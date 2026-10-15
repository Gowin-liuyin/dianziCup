"""Review-only inputs, real isolated object store and synthetic loopback failure boundaries."""
from __future__ import annotations

import hashlib
import socket
import ssl
import subprocess
import time
from datetime import UTC, datetime
from io import BytesIO
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

import pytest
from conftest import isolated_test_database_url, migrated_engine
from minio import Minio
from pydantic import SecretStr
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_r02_minio_persistence import live_store, object_settings, seed_document

from ai_intel.infrastructure.minio_store import MinioContentStore, ObjectStoreUnavailableError
from ai_intel.knowledge.models import content_objects, document_revisions
from ai_intel.knowledge.revisions import cleanup_unreferenced_object, save_document_revision


def client(settings):
    return Minio(settings.minio_endpoint,
                 access_key=settings.minio_access_key.get_secret_value(),
                 secret_key=settings.minio_secret_key.get_secret_value(), secure=False)


def test_real_remote_empty_object_roundtrip(live_store):
    stored = live_store.store_bytes(b'')
    assert stored.content_hash == hashlib.sha256(b'').hexdigest()
    assert stored.size_bytes == 0
    assert live_store.read_verified(stored.content_hash) == b''


def test_real_remote_oversized_read_fails_with_bounded_adapter(object_settings):
    root = client(object_settings)
    payload = b'x' * 21
    digest = hashlib.sha256(payload).hexdigest()
    key = f'objects/{digest[:2]}/{digest}'
    root.put_object(object_settings.minio_bucket, key, BytesIO(payload), len(payload))
    bounded = MinioContentStore(object_settings.minio_endpoint, object_settings.minio_bucket,
                               object_settings.minio_access_key, object_settings.minio_secret_key,
                               secure=False, test_mode=True, max_object_bytes=20)
    try:
        with pytest.raises(ValueError, match='byte limit'):
            bounded.read_verified(digest)
    finally:
        root.remove_object(object_settings.minio_bucket, key)


def test_real_write_then_corruption_cannot_register_pg_metadata(migrated_engine, live_store,
                                                              object_settings, monkeypatch):
    document_id = str(uuid4())
    payload = ('independent-write-corruption-' + document_id).encode()
    digest = hashlib.sha256(payload).hexdigest()
    root = client(object_settings)
    original_put = live_store._client.put_object

    def corrupt_after_write(*args, **kwargs):
        result = original_put(*args, **kwargs)
        root.put_object(object_settings.minio_bucket, f'objects/{digest[:2]}/{digest}',
                        BytesIO(b'corrupt after acknowledged write'), 32)
        return result

    monkeypatch.setattr(live_store._client, 'put_object', corrupt_after_write)
    with Session(migrated_engine) as session, session.begin():
        seed_document(session, document_id)
    try:
        with pytest.raises(ValueError, match='checksum'), Session(migrated_engine) as session, session.begin():
            save_document_revision(session, live_store, document_id, payload, 'public', None,
                                   datetime.now(UTC))
        with Session(migrated_engine) as session:
            assert session.scalar(select(func.count()).select_from(document_revisions)
                                  .where(document_revisions.c.document_id == document_id)) == 0
            assert session.scalar(select(func.count()).select_from(content_objects)
                                  .where(content_objects.c.content_hash == digest)) == 0
    finally:
        root.remove_object(object_settings.minio_bucket, f'objects/{digest[:2]}/{digest}')


def test_rollback_orphan_can_be_reclaimed_without_deleting_referenced_objects(migrated_engine, live_store):
    document_id = str(uuid4())
    payload = ('independent-orphan-' + document_id).encode()
    digest = hashlib.sha256(payload).hexdigest()
    with Session(migrated_engine) as session, session.begin():
        seed_document(session, document_id)
    with pytest.raises(RuntimeError), Session(migrated_engine) as session, session.begin():
        save_document_revision(session, live_store, document_id, payload, 'public', None,
                               datetime.now(UTC))
        raise RuntimeError('controlled publication rollback')
    assert live_store.read_verified(digest) == payload
    with Session(migrated_engine) as session, session.begin():
        assert cleanup_unreferenced_object(session, live_store, digest)
    with pytest.raises(FileNotFoundError):
        live_store.read_verified(digest)
    with Session(migrated_engine) as session, session.begin():
        saved = save_document_revision(session, live_store, document_id, payload, 'public', None,
                                       datetime.now(UTC))
    with Session(migrated_engine) as session, session.begin():
        assert not cleanup_unreferenced_object(session, live_store, saved.content_hash)
    assert live_store.read_verified(digest) == payload


def test_real_denied_write_remains_unavailable_and_does_not_create_object(object_settings):
    denied = MinioContentStore(object_settings.minio_endpoint, object_settings.minio_bucket,
                              SecretStr('review-denied-identity'), SecretStr('review-denied-password'),
                              secure=False, test_mode=True, timeout_seconds=1)
    payload = ('independent-denied-' + str(uuid4())).encode()
    digest = hashlib.sha256(payload).hexdigest()
    with pytest.raises(ObjectStoreUnavailableError, match='read unavailable'):
        denied.store_bytes(payload)
    root = client(object_settings)
    with pytest.raises(Exception) as failure:
        root.stat_object(object_settings.minio_bucket, f'objects/{digest[:2]}/{digest}')
    assert failure.value.code == 'NoSuchKey'


def test_sdk_stalled_socket_has_read_timeout():
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(1)
    port = listener.getsockname()[1]
    stop = Event()
    received = Event()

    def hold_request():
        connection, _ = listener.accept()
        with connection:
            connection.recv(8192)
            received.set()
            stop.wait(3)

    worker = Thread(target=hold_request, daemon=True)
    worker.start()
    store = MinioContentStore(f'127.0.0.1:{port}', 'test-review-timeout',
                              SecretStr('fixture-access'), SecretStr('fixture-secret'),
                              secure=False, test_mode=True, timeout_seconds=0.2)
    started = time.monotonic()
    try:
        with pytest.raises(ObjectStoreUnavailableError, match='read unavailable'):
            store.read_verified('a' * 64)
        elapsed = time.monotonic() - started
        assert received.is_set()
        assert 0.1 <= elapsed < 2
    finally:
        stop.set()
        listener.close()
        worker.join(timeout=3)


def test_sdk_tls_default_requires_certificate_validation():
    store = MinioContentStore('127.0.0.1:29400', 'test-review-tls',
                              SecretStr('fixture-access'), SecretStr('fixture-secret'))
    assert store._client._base_url.is_https
    assert store._client._http.connection_pool_kw['cert_reqs'] == 'CERT_REQUIRED'
    retry = store._client._http.connection_pool_kw['retries']
    assert retry.total is False
    assert retry.redirect == 0
    assert store._client._http.connection_pool_kw['timeout'].connect_timeout == 5
    assert store._client._http.connection_pool_kw['timeout'].read_timeout == 5


def test_sdk_real_tls_rejects_untrusted_ca_then_reads_with_explicit_ca(tmp_path):
    certificate = tmp_path / 'local-test-cert.pem'
    key = tmp_path / 'local-test-key.pem'

    def linux_path(path):
        drive, tail = str(path).split(':', 1)
        return '/mnt/' + drive.lower() + tail.replace('\\', '/')

    generated = subprocess.run(['wsl.exe', '-d', 'Ubuntu-22.04', '-u', 'root', '--exec',
                               'openssl', 'req', '-x509', '-newkey', 'rsa:2048', '-nodes',
                               '-keyout', linux_path(key), '-out', linux_path(certificate),
                               '-days', '1', '-subj', '/CN=localhost', '-addext',
                               'subjectAltName=IP:127.0.0.1'], capture_output=True, timeout=20)
    assert generated.returncode == 0
    payload = b'explicit synthetic TLS object'
    digest = hashlib.sha256(payload).hexdigest()

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Content-Type', 'application/octet-stream')
            self.end_headers()
            self.wfile.write(payload)

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certificate, key)
    server.socket = context.wrap_socket(server.socket, server_side=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    endpoint = f'127.0.0.1:{server.server_address[1]}'
    try:
        untrusted = MinioContentStore(endpoint, 'test-review-tls', SecretStr('fixture-access'),
                                      SecretStr('fixture-secret'), timeout_seconds=1)
        with pytest.raises(ObjectStoreUnavailableError, match='read unavailable'):
            untrusted.read_verified(digest)
        trusted = MinioContentStore(endpoint, 'test-review-tls', SecretStr('fixture-access'),
                                    SecretStr('fixture-secret'), ca_file=str(certificate),
                                    timeout_seconds=1)
        assert trusted.read_verified(digest) == payload
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
