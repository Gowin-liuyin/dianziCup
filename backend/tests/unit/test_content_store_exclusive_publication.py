"""用真实文件、排他竞争与合成异常验证不可变原文发布，不访问外部服务。"""

from __future__ import annotations

import errno
import hashlib
import os
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from ai_intel.infrastructure.content_store import ContentStore, StoredObject


def test_parallel_publish_and_replay_preserve_object_with_open_reader(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    payload = b"synthetic concurrent object" * 128
    digest = hashlib.sha256(payload).hexdigest()
    store = ContentStore(tmp_path)
    target = store.object_path_for_hash(digest)
    first_checks = threading.Barrier(4, timeout=3)
    published = threading.Event()
    losers_done = threading.Event()
    mutex = threading.Lock()
    checked_threads: set[int] = set()
    descriptors: dict[str, tuple[int, tuple[int, int]]] = {}
    publication_positions: dict[str, int] = {}
    completed_losers = 0
    collision_count = 0
    reader_verified = False
    original_exists = Path.exists
    original_link = os.link
    original_create = tempfile.mkstemp

    def checked_exists(path: Path) -> bool:
        if path == target:
            with mutex:
                thread_id = threading.get_ident()
                first_check = thread_id not in checked_threads
                checked_threads.add(thread_id)
            if first_check:
                absent = not original_exists(path)
                first_checks.wait()
                assert absent
                return False
        return original_exists(path)

    def create(*, dir: Path, prefix: str) -> tuple[int, str]:
        descriptor, name = original_create(dir=dir, prefix=prefix)
        stat = os.fstat(descriptor)
        with mutex:
            descriptors[name] = (descriptor, (stat.st_dev, stat.st_ino))
        return descriptor, name

    def exclusive_publish(source: str, destination: Path) -> None:
        nonlocal collision_count, reader_verified
        with mutex:
            position = len(publication_positions)
            publication_positions[source] = position
            descriptor, identity = descriptors[source]
        try:
            stat = os.fstat(descriptor)
        except OSError:
            pass
        else:
            assert (stat.st_dev, stat.st_ino) != identity
        if position == 0:
            original_link(source, destination)
            with destination.open("rb") as reader:
                published.set()
                assert losers_done.wait(3)
                assert reader.read() == payload
                reader_verified = True
        else:
            assert published.wait(3)
            try:
                original_link(source, destination)
            except FileExistsError:
                with mutex:
                    collision_count += 1
                raise
            else:
                raise AssertionError("exclusive publication unexpectedly replaced target")

    def first_writer() -> StoredObject:
        nonlocal completed_losers
        result = store.store_bytes(payload)
        with mutex:
            if published.is_set() and not reader_verified:
                completed_losers += 1
                if completed_losers == 3:
                    losers_done.set()
        return result

    with monkeypatch.context() as publication_patch:
        publication_patch.setattr(Path, "exists", checked_exists)
        publication_patch.setattr(tempfile, "mkstemp", create)
        publication_patch.setattr(os, "link", exclusive_publish)
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(first_writer) for _ in range(4)]
            results = [future.result(timeout=5) for future in futures]
    identity = (target.stat().st_dev, target.stat().st_ino)
    with target.open("rb") as reader:
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(store.store_bytes, payload) for _ in range(8)]
            results.extend(future.result(timeout=5) for future in futures)
        assert reader.read() == payload
    assert len(results) == 12
    assert {result.content_hash for result in results} == {digest}
    assert {result.object_path for result in results} == {target}
    assert all(result.size_bytes == len(payload) for result in results)
    assert store.read_verified(digest) == payload
    assert (target.stat().st_dev, target.stat().st_ino) == identity
    assert len(publication_positions) == len(descriptors) == 4
    assert collision_count == 3
    assert reader_verified
    assert not list(tmp_path.glob("*/.tmp-*"))


@pytest.mark.parametrize(
    "publication_error",
    [
        PermissionError("synthetic non-collision permission failure"),
        OSError(errno.EOPNOTSUPP, "synthetic unsupported hardlink filesystem"),
        NotImplementedError("synthetic hardlink unavailable"),
    ],
)
def test_non_collision_error_is_preserved_even_when_target_is_identical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, publication_error: BaseException
) -> None:
    store = ContentStore(tmp_path)
    payload = b"synthetic non-collision existing content"
    digest = hashlib.sha256(payload).hexdigest()
    target = store.object_path_for_hash(digest)

    def fail_publish(source: str, destination: Path) -> None:
        destination.write_bytes(payload)
        raise publication_error

    def unexpected_verification(content_hash: str) -> bytes:
        raise AssertionError("non-collision errors must not reuse an existing object")

    monkeypatch.setattr(os, "link", fail_publish)
    monkeypatch.setattr(store, "read_verified", unexpected_verification)
    with pytest.raises(type(publication_error)) as caught:
        store.store_bytes(payload)
    assert caught.value is publication_error
    assert target.read_bytes() == payload
    assert not list(tmp_path.glob("*/.tmp-*"))


@pytest.mark.parametrize("competitor_matches", [True, False])
def test_real_exclusive_collision_never_replaces_competitor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, competitor_matches: bool
) -> None:
    store = ContentStore(tmp_path)
    payload = b"synthetic competing complete content"
    competitor_payload = payload if competitor_matches else b"synthetic corrupt competitor"
    digest = hashlib.sha256(payload).hexdigest()
    target = store.object_path_for_hash(digest)
    original_link = os.link
    publication_errors: list[FileExistsError] = []
    competitor_identities: list[tuple[int, int]] = []

    def competing_publish(source: str, destination: Path) -> None:
        destination.write_bytes(competitor_payload)
        stat = destination.stat()
        competitor_identities.append((stat.st_dev, stat.st_ino))
        try:
            original_link(source, destination)
        except FileExistsError as error:
            publication_errors.append(error)
            raise
        else:
            raise AssertionError("exclusive publication unexpectedly replaced competitor")

    monkeypatch.setattr(os, "link", competing_publish)
    if competitor_matches:
        result = store.store_bytes(payload)
        assert result.content_hash == digest
        assert result.size_bytes == len(payload)
    else:
        with pytest.raises(FileExistsError) as caught:
            store.store_bytes(payload)
        assert caught.value is publication_errors[0]
    assert len(publication_errors) == 1
    assert target.read_bytes() == competitor_payload
    assert (target.stat().st_dev, target.stat().st_ino) == competitor_identities[0]
    assert not list(tmp_path.glob("*/.tmp-*"))
