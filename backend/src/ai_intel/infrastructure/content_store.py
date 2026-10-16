"""原文内容寻址存储: 临时写入排他发布、hash 校验、路径不取自用户输入。"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ContentPathValidationError(ValueError):
    """内容哈希非法: 路径仅由合法哈希导出, 拒绝任何用户可控路径成分。"""


@dataclass(frozen=True)
class StoredContent:
    """本地和对象存储共享的校验后登记值，不包含公开可用存储路径。"""

    content_hash: str
    size_bytes: int


@dataclass(frozen=True)
class StoredObject(StoredContent):
    """本地文件实现额外保留内部Path；不把S3键伪造成文件路径。"""

    object_path: Path


class ContentStorage(Protocol):
    """原文发布/回收共用的三个IO操作；事实与ACL仍由PG负责。"""

    def store_bytes(self, payload: bytes) -> StoredContent: ...

    def read_verified(self, content_hash: str) -> bytes: ...

    def delete_object(self, content_hash: str) -> None: ...


class ContentStore:
    """按内容哈希寻址的原文库: 写入原子, 路径与用户输入无关。"""

    def __init__(self, root_directory: Path) -> None:
        self._root = root_directory
        self._root.mkdir(parents=True, exist_ok=True)

    def object_path_for_hash(self, content_hash: str) -> Path:
        """仅接受 64 位十六进制哈希; 目录分片来自哈希本身, 不受用户路径影响。"""
        if not SHA256_PATTERN.fullmatch(content_hash):
            raise ContentPathValidationError("content hash must be 64 lowercase hex characters")
        return self._root / content_hash[:2] / content_hash

    def store_bytes(self, payload: bytes) -> StoredObject:
        """同目录临时落盘后排他发布；已有完整相同对象才复用，不覆盖旧对象。"""
        content_hash = hashlib.sha256(payload).hexdigest()
        object_path = self.object_path_for_hash(content_hash)
        object_path.parent.mkdir(parents=True, exist_ok=True)
        if object_path.exists():
            existing_size = object_path.stat().st_size
            if hashlib.sha256(object_path.read_bytes()).hexdigest() != content_hash:
                raise ValueError(f"existing object corrupted for {content_hash}")
            return StoredObject(
                content_hash=content_hash,
                size_bytes=existing_size,
                object_path=object_path,
            )
        file_descriptor, temporary_name = tempfile.mkstemp(dir=object_path.parent, prefix=".tmp-")
        temporary_identity: tuple[int, int] | None = None
        operation_error: BaseException | None = None
        try:
            try:
                temporary_stat = os.fstat(file_descriptor)
                temporary_identity = (temporary_stat.st_dev, temporary_stat.st_ino)
                with os.fdopen(file_descriptor, "wb", closefd=False) as temporary_file:
                    temporary_file.write(payload)
                    temporary_file.flush()
                    os.fsync(temporary_file.fileno())
            except BaseException as error:
                operation_error = error
                raise
            finally:
                try:
                    os.close(file_descriptor)
                except OSError as close_error:
                    if operation_error is None:
                        raise
                    operation_error.add_note(
                        "temporary content descriptor close failed: " + type(close_error).__name__
                    )
            try:
                os.link(temporary_name, object_path)
            except FileExistsError as publication_error:
                try:
                    existing_payload = self.read_verified(content_hash)
                except (OSError, ValueError):
                    raise publication_error from None
                if existing_payload != payload:
                    raise
        except BaseException as error:
            operation_error = error
            raise
        finally:
            try:
                if temporary_identity is not None:
                    try:
                        remaining_stat = os.lstat(temporary_name)
                    except FileNotFoundError:
                        pass
                    else:
                        if (remaining_stat.st_dev, remaining_stat.st_ino) == temporary_identity:
                            os.unlink(temporary_name)
            except OSError as cleanup_error:
                if operation_error is None:
                    raise
                operation_error.add_note(
                    "temporary content cleanup failed: " + type(cleanup_error).__name__
                )
        return StoredObject(
            content_hash=content_hash, size_bytes=len(payload), object_path=object_path
        )

    def read_verified(self, content_hash: str) -> bytes:
        """读取原文并校验哈希; 损坏对象抛错, 不返回未验证内容。"""
        object_path = self.object_path_for_hash(content_hash)
        payload = object_path.read_bytes()
        actual_hash = hashlib.sha256(payload).hexdigest()
        if actual_hash != content_hash:
            raise ValueError(f"content hash mismatch for {content_hash}")
        return payload

    def delete_object(self, content_hash: str) -> None:
        """删除未引用对象; 供写库失败后的清理路径调用。"""
        object_path = self.object_path_for_hash(content_hash)
        if object_path.exists():
            object_path.unlink()
