"""Verify same-process admission while one real local worker is running."""

import multiprocessing
import os
import threading
import time
from pathlib import Path

import pytest

from ai_intel.infrastructure.models import semantic


def test_real_concurrent_call_fails_busy_then_capacity_recovers():
    models = semantic.LocalSemanticModels(Path(os.environ["R05_SEMANTIC_CACHE"]))
    before = {child.pid for child in multiprocessing.active_children()}
    results = []
    errors = []

    def run():
        try:
            results.append(models.embed_query("如何限制未授权的证据访问？"))
        except Exception as error:
            errors.append(type(error).__name__)

    thread = threading.Thread(target=run)
    thread.start()
    deadline = time.monotonic() + 2
    while not semantic._WORKER_LOCK.locked() and time.monotonic() < deadline:
        time.sleep(0.001)
    assert semantic._WORKER_LOCK.locked()
    with pytest.raises(semantic.SemanticRuntimeError, match="busy"):
        models.embed_query("a second synthetic caller")
    thread.join(timeout=30)
    assert not thread.is_alive()
    assert errors == [] and len(results) == 1
    assert results[0].dimension == 384
    assert not semantic._WORKER_LOCK.locked()
    assert {child.pid for child in multiprocessing.active_children()} == before
