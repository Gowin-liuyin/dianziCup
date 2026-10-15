"""官方SDK边界的显式unit替身；不计MinIO live或PG集成证明。"""

import hashlib
from io import BytesIO

import pytest
from minio.error import S3Error
from pydantic import SecretStr
from urllib3.response import HTTPResponse

from ai_intel.infrastructure import minio_store
from ai_intel.infrastructure.content_store import ContentPathValidationError
from ai_intel.infrastructure.minio_store import MinioContentStore, ObjectStoreUnavailableError


class FixtureResponse(BytesIO):
    def release_conn(self) -> None:
        pass


class FixtureMinio:
    """只模拟SDK IO，校验与内容寻址仍由真实被测类完成。"""

    def __init__(self, *args: object, **kwargs: object) -> None:
        self.objects: dict[str, bytes] = {}
        self.denied = False
        self.put_count = 0

    def get_object(self, bucket: str, object_name: str) -> FixtureResponse:
        if self.denied:
            raise S3Error(
                HTTPResponse(status=403), "AccessDenied", "fixture denial", None, None, None
            )
        if object_name not in self.objects:
            raise S3Error(
                HTTPResponse(status=404), "NoSuchKey", "fixture missing", None, None, None
            )
        return FixtureResponse(self.objects[object_name])

    def put_object(
        self, bucket: str, object_name: str, data: BytesIO, length: int, content_type: str
    ) -> None:
        if self.denied:
            raise S3Error(
                HTTPResponse(status=403), "AccessDenied", "fixture denial", None, None, None
            )
        self.put_count += 1
        self.objects[object_name] = data.read(length)

    def remove_object(self, bucket: str, object_name: str) -> None:
        if self.denied:
            raise S3Error(
                HTTPResponse(status=403), "AccessDenied", "fixture denial", None, None, None
            )
        self.objects.pop(object_name, None)


@pytest.fixture()
def unit_store(monkeypatch: pytest.MonkeyPatch) -> MinioContentStore:
    monkeypatch.setattr(minio_store, "Minio", FixtureMinio)
    return MinioContentStore(
        "127.0.0.1:29400",
        "test-fixture",
        SecretStr("fixture-access"),
        SecretStr("fixture-secret"),
        secure=False,
        test_mode=True,
        max_object_bytes=20,
    )


def test_unit_fixture_roundtrip_idempotency_and_delete(unit_store: MinioContentStore) -> None:
    first = unit_store.store_bytes(b"evidence")
    second = unit_store.store_bytes(b"evidence")
    assert first == second
    assert unit_store.read_verified(first.content_hash) == b"evidence"
    assert unit_store._client.put_count == 1
    unit_store.delete_object(first.content_hash)
    with pytest.raises(FileNotFoundError):
        unit_store.read_verified(first.content_hash)


def test_existing_corruption_is_not_silently_replaced(unit_store: MinioContentStore) -> None:
    digest = hashlib.sha256(b"evidence").hexdigest()
    unit_store._client.objects[unit_store._object_key(digest)] = b"corrupted"
    with pytest.raises(ValueError, match="checksum"):
        unit_store.store_bytes(b"evidence")
    assert unit_store._client.put_count == 0


def test_denied_is_distinct_from_missing(unit_store: MinioContentStore) -> None:
    unit_store._client.denied = True
    with pytest.raises(ObjectStoreUnavailableError, match="read unavailable"):
        unit_store.store_bytes(b"evidence")
    with pytest.raises(ObjectStoreUnavailableError, match="deletion unavailable"):
        unit_store.delete_object("a" * 64)


def test_remote_read_and_input_size_are_bounded(unit_store: MinioContentStore) -> None:
    with pytest.raises(ValueError, match="byte limit"):
        unit_store.store_bytes(b"x" * 21)
    digest = hashlib.sha256(b"x" * 21).hexdigest()
    unit_store._client.objects[unit_store._object_key(digest)] = b"x" * 21
    with pytest.raises(ValueError, match="byte limit"):
        unit_store.read_verified(digest)
    with pytest.raises(ContentPathValidationError):
        unit_store.read_verified("../../etc/passwd")


@pytest.mark.parametrize(
    "options", [{"secure": False}, {"timeout_seconds": 0}, {"max_object_bytes": 0}]
)
def test_plaintext_or_unbounded_settings_are_rejected(options: dict[str, object]) -> None:
    with pytest.raises(ValueError):
        MinioContentStore(
            "127.0.0.1:29400",
            "test-fixture",
            SecretStr("fixture-access"),
            SecretStr("fixture-secret"),
            **options,
        )
