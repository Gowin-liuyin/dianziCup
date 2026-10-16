"""真实关闭自有 FD 后的合成关闭错误不得覆盖本次主错误。"""

from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import pytest

from ai_intel.infrastructure.content_store import ContentStore


@pytest.mark.parametrize("failure_stage", ["fstat", "fdopen", "none"])
def test_descriptor_close_preserves_primary_failure_or_reports_close_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure_stage: str
) -> None:
    original_create = tempfile.mkstemp
    original_close = os.close
    original_stat = os.fstat
    captured: list[tuple[int, str]] = []
    closed: list[int] = []
    main_failure = OSError("synthetic original storage failure")
    close_failure = OSError("synthetic descriptor close failure")

    def create(*, dir: Path, prefix: str) -> tuple[int, str]:
        descriptor, name = original_create(dir=dir, prefix=prefix)
        captured.append((descriptor, name))
        return descriptor, name

    def fail_stat(descriptor: int) -> os.stat_result:
        if captured and descriptor == captured[0][0] and failure_stage == "fstat":
            raise main_failure
        return original_stat(descriptor)

    def fail_open(*args: object, **kwargs: object) -> None:
        raise main_failure

    def close_then_fail(descriptor: int) -> None:
        original_close(descriptor)
        if captured and descriptor == captured[0][0]:
            closed.append(descriptor)
            raise close_failure

    monkeypatch.setattr(tempfile, "mkstemp", create)
    monkeypatch.setattr(os, "fstat", fail_stat)
    monkeypatch.setattr(os, "close", close_then_fail)
    if failure_stage == "fdopen":
        monkeypatch.setattr(os, "fdopen", fail_open)
    store = ContentStore(tmp_path)
    payload = b"synthetic descriptor close bytes"
    with pytest.raises(OSError) as caught:
        store.store_bytes(payload)
    descriptor, name = captured[0]
    with pytest.raises(OSError):
        original_stat(descriptor)
    assert closed == [descriptor]
    assert not store.object_path_for_hash(hashlib.sha256(payload).hexdigest()).exists()
    if failure_stage == "none":
        assert caught.value is close_failure
        assert not Path(name).exists()
    else:
        assert caught.value is main_failure
        assert caught.value.__notes__ == ["temporary content descriptor close failed: OSError"]
        if failure_stage == "fstat":
            assert Path(name).read_bytes() == b""
        else:
            assert not Path(name).exists()
