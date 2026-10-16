"""合成异常验证主错误保留、清理错误显式报告和原文件所有权。"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest

from ai_intel.infrastructure.content_store import ContentStore


@pytest.mark.parametrize("cleanup_operation", ["lstat", "unlink"])
def test_cleanup_error_after_verified_success_is_still_reported(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, cleanup_operation: str
) -> None:
    store = ContentStore(tmp_path)
    payload = b"synthetic published complete object"
    cleanup_failure = PermissionError("synthetic successful-operation cleanup failure")
    cleanup = getattr(os, cleanup_operation)
    temporary_paths: list[Path] = []

    def publish_identical(source: str, target: Path) -> None:
        target.write_bytes(Path(source).read_bytes())
        temporary_paths.append(Path(source))

    def fail_cleanup(path: str | os.PathLike[str], *args: object, **kwargs: object) -> object:
        if Path(path).name.startswith(".tmp-"):
            raise cleanup_failure
        return cleanup(path, *args, **kwargs)

    monkeypatch.setattr(os, "link", publish_identical)
    monkeypatch.setattr(os, cleanup_operation, fail_cleanup)
    with pytest.raises(PermissionError) as caught:
        store.store_bytes(payload)
    assert caught.value is cleanup_failure
    digest = hashlib.sha256(payload).hexdigest()
    assert store.read_verified(digest) == payload
    assert temporary_paths[0].read_bytes() == payload


def test_cleanup_error_preserves_main_exception_and_adds_only_error_type(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    main_failure = OSError("synthetic main publication failure")
    cleanup_failure = PermissionError("synthetic hidden cleanup details")
    original_lstat = os.lstat

    def fail_publish(source: str, target: Path) -> None:
        raise main_failure

    def fail_cleanup(path: str | os.PathLike[str], *, dir_fd: int | None = None) -> os.stat_result:
        if Path(path).name.startswith(".tmp-"):
            raise cleanup_failure
        return original_lstat(path, dir_fd=dir_fd)

    monkeypatch.setattr(os, "link", fail_publish)
    monkeypatch.setattr(os, "lstat", fail_cleanup)
    with pytest.raises(OSError) as caught:
        ContentStore(tmp_path).store_bytes(b"synthetic exception note bytes")
    assert caught.value is main_failure
    assert str(caught.value) == "synthetic main publication failure"
    assert caught.value.__notes__ == ["temporary content cleanup failed: PermissionError"]
    assert "synthetic hidden cleanup details" not in "".join(caught.value.__notes__)
