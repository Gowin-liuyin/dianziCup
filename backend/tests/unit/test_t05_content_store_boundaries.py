"""ContentStore 边界单元测试: 路径导出、哈希校验与对象生命周期（无数据库依赖）。"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_intel.infrastructure.content_store import ContentPathValidationError, ContentStore


def make_store(tmp_path: Path) -> ContentStore:
    """隔离的原文存储根目录。"""
    return ContentStore(tmp_path / "objects")


def test_object_path_rejects_traversal_and_non_hash_input(tmp_path: Path) -> None:
    """路径导出只接受 64 位十六进制哈希, 恶意路径成分一律拒绝。"""
    store = make_store(tmp_path)
    for malicious_hash in ("../../etc/passwd", "..\\windows\\system32", "abc", "Z" * 64, ""):
        with pytest.raises(ContentPathValidationError):
            store.object_path_for_hash(malicious_hash)


def test_object_path_is_derived_only_from_hash(tmp_path: Path) -> None:
    """对象路径结构由哈希自身决定: 分片目录+完整哈希文件名。"""
    store = make_store(tmp_path)
    content_hash = "ab" + "0" * 62
    object_path = store.object_path_for_hash(content_hash)
    assert object_path.parent.name == "ab"
    assert object_path.name == content_hash
    assert object_path.parent.parent == tmp_path / "objects"


def test_store_and_read_roundtrip_verifies_hash(tmp_path: Path) -> None:
    """写读往返: 读取时重新校验哈希, 与写入内容一致。"""
    store = make_store(tmp_path)
    payload = b"verified payload content"
    stored = store.store_bytes(payload)
    assert stored.size_bytes == len(payload)
    assert store.read_verified(stored.content_hash) == payload


def test_store_bytes_is_idempotent_for_same_content(tmp_path: Path) -> None:
    """重复写入同内容幂等: 对象不重复落盘, 哈希一致。"""
    store = make_store(tmp_path)
    first = store.store_bytes(b"repeated content")
    second = store.store_bytes(b"repeated content")
    assert first.content_hash == second.content_hash
    assert first.object_path == second.object_path
    assert first.object_path.exists()


def test_read_verified_detects_corrupted_object(tmp_path: Path) -> None:
    """对象被篡改时读取报错, 不返回未验证内容。"""
    store = make_store(tmp_path)
    stored = store.store_bytes(b"original bytes")
    stored.object_path.write_bytes(b"tampered bytes!")
    with pytest.raises(ValueError):
        store.read_verified(stored.content_hash)


def test_delete_object_removes_file_and_is_idempotent(tmp_path: Path) -> None:
    """删除未引用对象: 文件移除且重复删除不报错。"""
    store = make_store(tmp_path)
    stored = store.store_bytes(b"disposable content")
    store.delete_object(stored.content_hash)
    assert not stored.object_path.exists()
    store.delete_object(stored.content_hash)
