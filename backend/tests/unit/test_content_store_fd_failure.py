"""真实合成文件验证本地原文写入的 FD 所有权与失败清理边界。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from types import TracebackType
from typing import IO

import pytest

from ai_intel.infrastructure.content_store import ContentStore


def capture_temporary_file(
    monkeypatch: pytest.MonkeyPatch,
) -> list[tuple[int, str]]:
    original_create = tempfile.mkstemp
    captured: list[tuple[int, str]] = []

    def create(*, dir: Path, prefix: str) -> tuple[int, str]:
        descriptor, name = original_create(dir=dir, prefix=prefix)
        captured.append((descriptor, name))
        return descriptor, name

    monkeypatch.setattr(tempfile, "mkstemp", create)
    return captured


def close_if_open(descriptor: int) -> None:
    try:
        os.fstat(descriptor)
    except OSError:
        return
    os.close(descriptor)


def test_fdopen_constructor_failure_closes_owned_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = capture_temporary_file(monkeypatch)
    failure = OSError("synthetic fdopen construction failure")

    def fail_open(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(os, "fdopen", fail_open)
    with pytest.raises(OSError) as caught:
        ContentStore(tmp_path).store_bytes(b"synthetic fdopen bytes")
    descriptor, name = captured[0]
    try:
        with pytest.raises(OSError):
            os.fstat(descriptor)
    finally:
        close_if_open(descriptor)
    assert caught.value is failure
    assert not Path(name).exists()
    assert not list(tmp_path.glob("*/*"))


def test_publish_failure_does_not_delete_replacement_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = capture_temporary_file(monkeypatch)
    foreign_marker = b"synthetic file owned by another operation"
    failure = OSError("synthetic publication failure")
    displaced = tmp_path / "original-owned-temporary"

    def fail_publish(source: str, target: Path) -> None:
        os.rename(source, displaced)
        Path(source).write_bytes(foreign_marker)
        raise failure

    monkeypatch.setattr(os, "link", fail_publish)
    store = ContentStore(tmp_path)
    payload = b"synthetic publish bytes"
    with pytest.raises(OSError) as caught:
        store.store_bytes(payload)
    assert caught.value is failure
    descriptor, name = captured[0]
    with pytest.raises(OSError):
        os.fstat(descriptor)
    assert Path(name).exists()
    assert Path(name).read_bytes() == foreign_marker
    assert displaced.read_bytes() == payload
    assert not store.object_path_for_hash(hashlib.sha256(payload).hexdigest()).exists()


@pytest.mark.parametrize("payload", [b"", "中文 synthetic\n".encode(), bytes(range(256))])
def test_success_preserves_exact_content_and_closes_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, payload: bytes
) -> None:
    captured = capture_temporary_file(monkeypatch)
    store = ContentStore(tmp_path)
    result = store.store_bytes(payload)
    assert result.content_hash == hashlib.sha256(payload).hexdigest()
    assert result.size_bytes == len(payload)
    assert result.object_path.read_bytes() == payload
    assert store.read_verified(result.content_hash) == payload
    assert not list(tmp_path.glob("*/.tmp-*"))
    with pytest.raises(OSError):
        os.fstat(captured[0][0])


def test_failed_initial_metadata_closes_fd_without_unproven_unlink(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = capture_temporary_file(monkeypatch)
    original_stat = os.fstat
    failure = OSError("synthetic initial fstat failure")

    def fail_stat(descriptor: int) -> os.stat_result:
        if captured and descriptor == captured[0][0]:
            raise failure
        return original_stat(descriptor)

    monkeypatch.setattr(os, "fstat", fail_stat)
    payload = b"synthetic metadata bytes"
    store = ContentStore(tmp_path)
    with pytest.raises(OSError) as caught:
        store.store_bytes(payload)
    assert caught.value is failure
    descriptor, name = captured[0]
    with pytest.raises(OSError):
        original_stat(descriptor)
    assert Path(name).read_bytes() == b""
    assert not store.object_path_for_hash(hashlib.sha256(payload).hexdigest()).exists()


@pytest.mark.parametrize("operation", ["write", "flush", "fsync", "replace"])
def test_io_failure_closes_descriptor_and_removes_only_owned_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, operation: str
) -> None:
    captured = capture_temporary_file(monkeypatch)
    original_open = os.fdopen
    failure = OSError(f"synthetic {operation} failure")

    class FailingFile:
        def __init__(self, stream: IO[bytes]) -> None:
            self.stream = stream

        def __enter__(self) -> FailingFile:
            return self

        def __exit__(
            self,
            exception_type: type[BaseException] | None,
            exception: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            self.stream.close()

        def write(self, payload: bytes) -> int:
            if operation == "write":
                self.stream.write(payload[:3])
                raise failure
            return self.stream.write(payload)

        def flush(self) -> None:
            if operation == "flush":
                raise failure
            self.stream.flush()

        def fileno(self) -> int:
            return self.stream.fileno()

    def open_failing(descriptor: int, mode: str, *, closefd: bool) -> FailingFile:
        assert closefd is False
        return FailingFile(original_open(descriptor, mode, closefd=closefd))

    def fail_fsync(descriptor: int) -> None:
        raise failure

    def fail_replace(source: str, target: Path) -> None:
        raise failure

    if operation in {"write", "flush"}:
        monkeypatch.setattr(os, "fdopen", open_failing)
    elif operation == "fsync":
        monkeypatch.setattr(os, "fsync", fail_fsync)
    else:
        monkeypatch.setattr(os, "link", fail_replace)
    store = ContentStore(tmp_path)
    payload = b"synthetic bounded IO payload"
    with pytest.raises(OSError) as caught:
        store.store_bytes(payload)
    assert caught.value is failure
    with pytest.raises(OSError):
        os.fstat(captured[0][0])
    assert not Path(captured[0][1]).exists()
    assert not store.object_path_for_hash(hashlib.sha256(payload).hexdigest()).exists()


def test_non_exception_base_failure_still_closes_descriptor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = capture_temporary_file(monkeypatch)

    class SyntheticAbort(BaseException):
        """本地故障对象不发送信号或中断其他进程。"""

    failure = SyntheticAbort()

    def fail_open(*args: object, **kwargs: object) -> None:
        raise failure

    monkeypatch.setattr(os, "fdopen", fail_open)
    with pytest.raises(SyntheticAbort) as caught:
        ContentStore(tmp_path).store_bytes(b"synthetic abort bytes")
    assert caught.value is failure
    with pytest.raises(OSError):
        os.fstat(captured[0][0])
    assert not Path(captured[0][1]).exists()


def test_cleanup_metadata_failure_has_no_success_and_preserves_unknown_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured = capture_temporary_file(monkeypatch)
    original_lstat = os.lstat

    def fail_publish(source: str, target: Path) -> None:
        raise OSError("synthetic publish failure")

    def fail_cleanup(path: str | os.PathLike[str], *, dir_fd: int | None = None) -> os.stat_result:
        if captured and str(path) == captured[0][1]:
            raise PermissionError("synthetic cleanup metadata failure")
        return original_lstat(path, dir_fd=dir_fd)

    monkeypatch.setattr(os, "link", fail_publish)
    monkeypatch.setattr(os, "lstat", fail_cleanup)
    with pytest.raises(OSError, match="synthetic publish failure"):
        ContentStore(tmp_path).store_bytes(b"synthetic inaccessible metadata")
    with pytest.raises(OSError):
        os.fstat(captured[0][0])
    assert Path(captured[0][1]).exists()


def test_existing_corrupted_object_is_never_overwritten(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    payload = b"synthetic immutable content"
    result = store.store_bytes(payload)
    foreign_marker = b"synthetic corrupted original"
    result.object_path.write_bytes(foreign_marker)
    with pytest.raises(ValueError, match="existing object corrupted"):
        store.store_bytes(payload)
    assert result.object_path.read_bytes() == foreign_marker
    assert not list(tmp_path.glob("*/.tmp-*"))


def test_parallel_same_hash_remains_idempotent_without_temporary_leftovers(tmp_path: Path) -> None:
    store = ContentStore(tmp_path)
    payload = b"synthetic concurrent object" * 128
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(store.store_bytes, payload) for _ in range(12)]
        results = [future.result(timeout=5) for future in futures]
    assert {result.content_hash for result in results} == {hashlib.sha256(payload).hexdigest()}
    assert len({result.object_path for result in results}) == 1
    assert store.read_verified(results[0].content_hash) == payload
    assert not list(tmp_path.glob("*/.tmp-*"))


@pytest.mark.parametrize(
    "existing_state", ["correct", "corrupted", "unreadable", "missing", "mismatched"]
)
def test_failed_publication_only_reuses_verified_identical_object(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, existing_state: str
) -> None:
    captured = capture_temporary_file(monkeypatch)
    store = ContentStore(tmp_path)
    payload = b"synthetic concurrent published content"
    content_hash = hashlib.sha256(payload).hexdigest()
    failure = FileExistsError("synthetic exclusive publication collision")
    verifier = store.read_verified
    verified_hashes: list[str] = []

    def fail_publish(source: str, target: Path) -> None:
        if existing_state in {"correct", "unreadable", "mismatched"}:
            target.write_bytes(payload)
        elif existing_state == "corrupted":
            target.write_bytes(b"synthetic incorrect content")
        raise failure

    def verify_existing(digest: str) -> bytes:
        verified_hashes.append(digest)
        if existing_state == "unreadable":
            raise PermissionError("synthetic verification permission failure")
        if existing_state == "mismatched":
            return b"synthetic incorrect verifier output"
        return verifier(digest)

    monkeypatch.setattr(os, "link", fail_publish)
    monkeypatch.setattr(store, "read_verified", verify_existing)
    if existing_state == "correct":
        result = store.store_bytes(payload)
        assert result.content_hash == content_hash
        assert result.size_bytes == len(payload)
        assert result.object_path.read_bytes() == payload
    else:
        with pytest.raises(FileExistsError) as caught:
            store.store_bytes(payload)
        assert caught.value is failure
        if existing_state == "corrupted":
            assert (
                store.object_path_for_hash(content_hash).read_bytes()
                == b"synthetic incorrect content"
            )
        if existing_state == "missing":
            assert not store.object_path_for_hash(content_hash).exists()
    assert verified_hashes == [content_hash]
    with pytest.raises(OSError):
        os.fstat(captured[0][0])
    assert not Path(captured[0][1]).exists()
