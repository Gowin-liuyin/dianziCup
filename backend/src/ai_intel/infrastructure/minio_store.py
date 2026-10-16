"""用官方SDK保存内容寻址原文，远端失败和损坏不冒充成功。"""

from __future__ import annotations

import hashlib
import json
from io import BytesIO

from minio import Minio
from minio.error import InvalidResponseError, S3Error, ServerError
from pydantic import SecretStr
from urllib3 import PoolManager
from urllib3.exceptions import HTTPError
from urllib3.util import Timeout

from ai_intel.infrastructure.content_store import (
    SHA256_PATTERN,
    ContentPathValidationError,
    StoredContent,
    _read_with_deadline,
    remaining_content_time,
)

MAX_OBJECT_BYTES = 64 * 1024 * 1024


class ObjectStoreUnavailableError(RuntimeError):
    """可重试性由上层任务决定；错误不回显SDK参数、凭据或原文。"""


class MinioContentStore:
    """可信配置的固定bucket，不接受请求方指定endpoint、bucket或对象键。"""

    def __init__(
        self,
        endpoint: str,
        bucket: str,
        access_key: SecretStr,
        secret_key: SecretStr,
        *,
        secure: bool = True,
        ca_file: str | None = None,
        timeout_seconds: float = 5.0,
        max_object_bytes: int = MAX_OBJECT_BYTES,
        test_mode: bool = False,
    ) -> None:
        if not access_key.get_secret_value() or not secret_key.get_secret_value():
            raise ValueError("object storage credentials are required")
        if not 0 < timeout_seconds <= 30 or not 0 < max_object_bytes <= MAX_OBJECT_BYTES:
            raise ValueError("object storage timeout or size bound invalid")
        if not secure and not test_mode:
            raise ValueError("plaintext object storage is allowed only in explicit test mode")
        self._bucket = bucket
        self._limit = max_object_bytes
        self._endpoint = endpoint
        self._access_key = access_key
        self._secret_key = secret_key
        self._secure = secure
        self._ca_file = ca_file
        self._timeout_seconds = timeout_seconds
        self._test_mode = test_mode
        http = PoolManager(
            timeout=Timeout(connect=timeout_seconds, read=timeout_seconds),
            retries=False,
            cert_reqs="CERT_REQUIRED",
            ca_certs=ca_file,
            maxsize=4,
        )
        self._client = Minio(
            endpoint,
            access_key=access_key.get_secret_value(),
            secret_key=secret_key.get_secret_value(),
            secure=secure,
            region="us-east-1",
            http_client=http,
        )

    def _object_key(self, content_hash: str) -> str:
        if not SHA256_PATTERN.fullmatch(content_hash):
            raise ContentPathValidationError("content hash must be 64 lowercase hex characters")
        return f"objects/{content_hash[:2]}/{content_hash}"

    def store_bytes(self, payload: bytes) -> StoredContent:
        """同哈希并发写相同字节；写后校验完成才允许PG登记引用。"""
        if len(payload) > self._limit:
            raise ValueError("object exceeded configured byte limit")
        digest = hashlib.sha256(payload).hexdigest()
        try:
            self.read_verified(digest)
        except FileNotFoundError:
            try:
                self._client.put_object(
                    self._bucket,
                    self._object_key(digest),
                    BytesIO(payload),
                    len(payload),
                    content_type="application/octet-stream",
                )
            except (S3Error, InvalidResponseError, ServerError, HTTPError, OSError):
                raise ObjectStoreUnavailableError("object storage write unavailable") from None
            self.read_verified(digest)
        return StoredContent(digest, len(payload))

    def read_verified(self, content_hash: str, *, deadline_monotonic: float | None = None) -> bytes:
        """有界读取并校验完整字节；missing与access/network失败分开。"""
        key = self._object_key(content_hash)
        if deadline_monotonic is not None:
            remaining = remaining_content_time(deadline_monotonic)
            request = json.dumps(
                {
                    "storage": "minio",
                    "endpoint": self._endpoint,
                    "bucket": self._bucket,
                    "access_key": self._access_key.get_secret_value(),
                    "secret_key": self._secret_key.get_secret_value(),
                    "secure": self._secure,
                    "ca_file": self._ca_file,
                    "timeout_seconds": min(self._timeout_seconds, remaining),
                    "test_mode": self._test_mode,
                    "content_hash": content_hash,
                    "remaining_seconds": remaining,
                    "byte_limit": self._limit,
                }
            ).encode()
            try:
                payload = _read_with_deadline(request, deadline_monotonic, self._limit)
            except (FileNotFoundError, TimeoutError):
                raise
            except OSError:
                raise ObjectStoreUnavailableError("object storage read unavailable") from None
            if hashlib.sha256(payload).hexdigest() != content_hash:
                raise ValueError("content object checksum mismatch")
            remaining_content_time(deadline_monotonic)
            return payload
        try:
            response = self._client.get_object(self._bucket, key)
            try:
                chunks: list[bytes] = []
                total = 0
                while chunk := response.read(min(1024 * 1024, self._limit + 1 - total)):
                    total += len(chunk)
                    if total > self._limit:
                        raise ValueError("object exceeded configured byte limit")
                    chunks.append(chunk)
                payload = b"".join(chunks)
            finally:
                response.close()
                response.release_conn()
        except S3Error as error:
            if error.code == "NoSuchKey":
                raise FileNotFoundError("content object not found") from None
            raise ObjectStoreUnavailableError("object storage read unavailable") from None
        except (InvalidResponseError, ServerError, HTTPError, OSError):
            raise ObjectStoreUnavailableError("object storage read unavailable") from None
        if hashlib.sha256(payload).hexdigest() != content_hash:
            raise ValueError("content object checksum mismatch")
        return payload

    def delete_object(self, content_hash: str) -> None:
        """只供同PG事务hash锁下的未引用对象回收调用；不提供任意删除API。"""
        key = self._object_key(content_hash)
        try:
            self._client.remove_object(self._bucket, key)
        except (S3Error, InvalidResponseError, ServerError, HTTPError, OSError):
            raise ObjectStoreUnavailableError("object storage deletion unavailable") from None
