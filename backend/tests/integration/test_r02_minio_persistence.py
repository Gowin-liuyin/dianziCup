"""隔离真实MinIO与PostgreSQL的原文、事务、并发和重建客户端回归。"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from io import BytesIO
from threading import Barrier
from uuid import uuid4

import pytest
from minio import Minio
from pydantic import SecretStr
from sqlalchemy import func, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.infrastructure.content_storage_factory import build_content_storage
from ai_intel.infrastructure.minio_store import MinioContentStore, ObjectStoreUnavailableError
from ai_intel.infrastructure.settings import load_application_settings
from ai_intel.knowledge.models import content_objects, document_revisions, documents
from ai_intel.knowledge.revisions import save_document_revision

pytestmark = [pytest.mark.real_pg, pytest.mark.real_services]


@pytest.fixture
def object_settings():
    """只有显式test配置可连接loopback隔离对象服务；缺配置按错误报告。"""
    required = (
        "TEST_MINIO_ENDPOINT",
        "TEST_MINIO_BUCKET",
        "TEST_MINIO_ACCESS_KEY",
        "TEST_MINIO_SECRET_KEY",
    )
    if any(not os.environ.get(name) for name in required):
        raise pytest.UsageError("blocked: isolated MinIO test configuration missing")
    if os.environ["TEST_MINIO_ENDPOINT"] != "127.0.0.1:29400":
        raise pytest.UsageError("blocked: MinIO endpoint is outside this isolated test run")
    if not os.environ["TEST_MINIO_BUCKET"].startswith("test-dianzi-r02-"):
        raise pytest.UsageError("blocked: MinIO test bucket identity invalid")
    return load_application_settings(
        app_env="test",
        content_store_backend="minio",
        minio_secure=False,
        minio_endpoint=os.environ["TEST_MINIO_ENDPOINT"],
        minio_bucket=os.environ["TEST_MINIO_BUCKET"],
        minio_access_key=SecretStr(os.environ["TEST_MINIO_ACCESS_KEY"]),
        minio_secret_key=SecretStr(os.environ["TEST_MINIO_SECRET_KEY"]),
        dependency_timeout_seconds=2,
    )


@pytest.fixture
def live_store(object_settings):
    client = Minio(
        object_settings.minio_endpoint,
        access_key=object_settings.minio_access_key.get_secret_value(),
        secret_key=object_settings.minio_secret_key.get_secret_value(),
        secure=False,
    )
    if not client.bucket_exists(object_settings.minio_bucket):
        client.make_bucket(object_settings.minio_bucket)
    return build_content_storage(object_settings)


def seed_document(session: Session, document_id: str) -> None:
    """固定标记的合成原文只进入隔离库，不计真实来源或采集指标。"""
    observed_at = datetime.now(UTC)
    source_id = str(uuid4())
    initial_hash = uuid4().hex + uuid4().hex
    session.execute(
        content_objects.insert().values(
            content_hash=initial_hash, size_bytes=0, created_at=observed_at
        )
    )
    session.execute(
        text(
            "INSERT INTO sources(source_id,name,category,base_origin,visibility,tenant_id,"
            "created_at) "
            "VALUES (:source,:name,'vendor_advisory','https://example.invalid','public',NULL,:now)"
        ),
        {"source": source_id, "name": "test-minio-" + source_id, "now": observed_at},
    )
    session.execute(
        documents.insert().values(
            document_id=document_id,
            source_id=source_id,
            kind="advisory",
            title="test synthetic MinIO document",
            published_at=None,
            retrieved_at=observed_at,
            content_hash=initial_hash,
            visibility="public",
            tenant_id=None,
            schema_version=1,
        )
    )


def test_real_object_reopened_in_independent_process(live_store) -> None:
    payload = ("test原文-" + str(uuid4())).encode()
    stored = live_store.store_bytes(payload)
    assert live_store.read_verified(stored.content_hash) == payload
    environment = {**os.environ, "TEST_OBJECT_HASH": stored.content_hash}
    program = (
        "import os; from pydantic import SecretStr; "
        "from ai_intel.infrastructure.minio_store import MinioContentStore; "
        "s=MinioContentStore(os.environ['TEST_MINIO_ENDPOINT'],os.environ['TEST_MINIO_BUCKET'],"
        "SecretStr(os.environ['TEST_MINIO_ACCESS_KEY']),SecretStr(os.environ['TEST_MINIO_SECRET_KEY']),"
        "secure=False,test_mode=True); "
        "assert s.read_verified(os.environ['TEST_OBJECT_HASH']); print('verified')"
    )
    completed = subprocess.run(
        [sys.executable, "-c", program], env=environment, capture_output=True, text=True, timeout=15
    )
    assert completed.returncode == 0
    assert completed.stdout.strip() == "verified"
    live_store.delete_object(stored.content_hash)
    with pytest.raises(FileNotFoundError):
        live_store.read_verified(stored.content_hash)


def test_minio_a_b_a_revisions_survive_new_pg_session(migrated_engine: Engine, live_store) -> None:
    document_id = str(uuid4())
    payload_a = ("test-A-" + document_id).encode()
    payload_b = ("test-B-" + document_id).encode()
    with Session(migrated_engine) as session, session.begin():
        seed_document(session, document_id)
        saved = [
            save_document_revision(
                session, live_store, document_id, payload, "public", None, datetime.now(UTC)
            )
            for payload in (payload_a, payload_b, payload_a)
        ]
    migrated_engine.dispose()
    with Session(migrated_engine) as session:
        rows = (
            session.execute(
                select(document_revisions)
                .where(document_revisions.c.document_id == document_id)
                .order_by(document_revisions.c.revision_number)
            )
            .mappings()
            .all()
        )
    assert [row["revision_number"] for row in rows] == [1, 2, 3]
    assert [row["is_current"] for row in rows] == [False, False, True]
    assert saved[0].revision_id != saved[2].revision_id
    assert [live_store.read_verified(row["content_hash"]) for row in rows] == [
        payload_a,
        payload_b,
        payload_a,
    ]


def test_rolled_back_revision_does_not_publish_metadata(
    migrated_engine: Engine, live_store
) -> None:
    document_id = str(uuid4())
    with Session(migrated_engine) as session, session.begin():
        seed_document(session, document_id)
    with (
        pytest.raises(RuntimeError, match="publication aborted"),
        Session(migrated_engine) as session,
        session.begin(),
    ):
        save_document_revision(
            session,
            live_store,
            document_id,
            document_id.encode(),
            "public",
            None,
            datetime.now(UTC),
        )
        raise RuntimeError("publication aborted")
    with Session(migrated_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(document_revisions)
                .where(document_revisions.c.document_id == document_id)
            )
            == 0
        )


def test_corrupt_existing_remote_object_is_not_overwritten(live_store, object_settings) -> None:
    payload = ("test-corruption-" + str(uuid4())).encode()
    digest = hashlib.sha256(payload).hexdigest()
    client = Minio(
        object_settings.minio_endpoint,
        access_key=object_settings.minio_access_key.get_secret_value(),
        secret_key=object_settings.minio_secret_key.get_secret_value(),
        secure=False,
    )
    key = f"objects/{digest[:2]}/{digest}"
    client.put_object(object_settings.minio_bucket, key, BytesIO(b"broken"), 6)
    with pytest.raises(ValueError, match="checksum mismatch"):
        live_store.store_bytes(payload)
    response = client.get_object(object_settings.minio_bucket, key)
    try:
        assert response.read() == b"broken"
    finally:
        response.close()
        response.release_conn()
        client.remove_object(object_settings.minio_bucket, key)


def test_real_denied_credentials_do_not_become_missing(object_settings) -> None:
    denied = MinioContentStore(
        object_settings.minio_endpoint,
        object_settings.minio_bucket,
        SecretStr("test-denied-identity"),
        SecretStr("test-denied-secret"),
        secure=False,
        test_mode=True,
        timeout_seconds=2,
    )
    with pytest.raises(ObjectStoreUnavailableError, match="read unavailable"):
        denied.read_verified("a" * 64)


def test_minio_failure_does_not_commit_revision_metadata(migrated_engine: Engine) -> None:
    document_id = str(uuid4())
    unavailable = MinioContentStore(
        "127.0.0.1:29499",
        "test-dianzi-r02-unavailable",
        SecretStr("test-denied-identity"),
        SecretStr("test-denied-secret"),
        secure=False,
        test_mode=True,
        timeout_seconds=1,
    )
    with Session(migrated_engine) as session, session.begin():
        seed_document(session, document_id)
    with (
        pytest.raises(ObjectStoreUnavailableError),
        Session(migrated_engine) as session,
        session.begin(),
    ):
        save_document_revision(
            session,
            unavailable,
            document_id,
            b"test unavailable",
            "public",
            None,
            datetime.now(UTC),
        )
    with Session(migrated_engine) as session:
        assert (
            session.scalar(
                select(func.count())
                .select_from(document_revisions)
                .where(document_revisions.c.document_id == document_id)
            )
            == 0
        )


def test_two_publishers_share_one_revision(migrated_engine: Engine, live_store) -> None:
    document_id = str(uuid4())
    with Session(migrated_engine) as session, session.begin():
        seed_document(session, document_id)
    barrier = Barrier(2)

    def publish():
        barrier.wait(timeout=10)
        with Session(migrated_engine) as session, session.begin():
            return save_document_revision(
                session,
                live_store,
                document_id,
                document_id.encode(),
                "public",
                None,
                datetime.now(UTC),
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: publish(), range(2)))
    assert results[0].revision_id == results[1].revision_id
    assert sorted(result.reused for result in results) == [False, True]
