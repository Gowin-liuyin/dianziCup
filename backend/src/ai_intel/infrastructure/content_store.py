"""原文内容寻址存储: 临时写入原子替换、hash 校验、路径不取自用户输入。"""

from __future__ import annotations

import hashlib
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ContentPathValidationError(ValueError):
    """内容哈希非法: 路径仅由合法哈希导出, 拒绝任何用户可控路径成分。"""


@dataclass(frozen=True)
class StoredObject:
    """已落盘原文对象的登记信息。"""

    content_hash: str
    size_bytes: int
    object_path: Path


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
        """写入原文: 先临时文件落盘再原子替换, 避免半写对象; 重复写入幂等。"""
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
        try:
            with os.fdopen(file_descriptor, "wb") as temporary_file:
                temporary_file.write(payload)
                temporary_file.flush()
                os.fsync(temporary_file.fileno())
            os.replace(temporary_name, object_path)
        except Exception:
            if os.path.exists(temporary_name):
                os.unlink(temporary_name)
            raise
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
