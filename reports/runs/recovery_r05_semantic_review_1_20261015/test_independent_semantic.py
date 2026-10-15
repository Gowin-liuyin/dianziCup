"""Independent synthetic boundaries and real local model smoke checks."""

import hashlib
import math
import multiprocessing
import os
import time
from dataclasses import replace
from pathlib import Path

import pytest

from ai_intel.infrastructure.models import semantic
from ai_intel.infrastructure.models.clients import ModelContractError, ModelNotConfiguredError


def test_pipe_creation_failure_releases_capacity(tmp_path, monkeypatch):
    class FailingContext:
        def Pipe(self, *, duplex):
            raise OSError("synthetic pipe resource exhaustion")

    monkeypatch.setattr(semantic.multiprocessing, "get_context", lambda _: FailingContext())
    try:
        with pytest.raises((OSError, semantic.SemanticRuntimeError)):
            semantic.LocalSemanticModels(tmp_path).embed_query("synthetic private question")
        assert not semantic._WORKER_LOCK.locked(), "one Pipe failure permanently consumes capacity"
    finally:
        if semantic._WORKER_LOCK.locked():
            semantic._WORKER_LOCK.release()


@pytest.mark.parametrize("text", [None, True, 3, b"text", [], "\udc00"])
def test_additional_malformed_public_inputs(tmp_path, text):
    with pytest.raises(semantic.SemanticInputError):
        semantic.LocalSemanticModels(tmp_path).embed_query(text)


@pytest.mark.parametrize("bad", [True, 1, float("nan"), float("inf"), -float("inf")])
def test_public_boundary_rejects_bad_backend_scalars(tmp_path, monkeypatch, bad):
    row = [1.0] + [0.0] * 383
    row[1] = bad
    monkeypatch.setattr(semantic, "_run_worker", lambda *args: [row])
    with pytest.raises(ModelContractError):
        semantic.LocalSemanticModels(tmp_path).embed_query("synthetic query")


def test_real_missing_cache_error_is_safe_and_child_is_reaped(tmp_path):
    before = {child.pid for child in multiprocessing.active_children()}
    with pytest.raises(ModelNotConfiguredError) as caught:
        semantic.LocalSemanticModels(tmp_path).rerank("SYNTHETIC_PRIVATE_MARKER", ("body",))
    assert "SYNTHETIC_PRIVATE_MARKER" not in str(caught.value)
    assert {child.pid for child in multiprocessing.active_children()} == before


def test_real_short_deadline_reaps_worker_and_releases_lock():
    cache = Path(os.environ["R05_SEMANTIC_CACHE"])
    before = {child.pid for child in multiprocessing.active_children()}
    started = time.monotonic()
    with pytest.raises(semantic.SemanticTimeoutError):
        semantic.LocalSemanticModels(cache, 0.001).embed_query("SYNTHETIC_PRIVATE_DEADLINE")
    assert time.monotonic() - started < 3
    assert {child.pid for child in multiprocessing.active_children()} == before
    assert not semantic._WORKER_LOCK.locked()


def test_real_same_size_corruption_is_rejected_before_inference(tmp_path):
    directory = tmp_path / "synthetic"
    directory.mkdir()
    (directory / "weights").write_bytes(b"changed!")
    model = replace(semantic.E5_MODEL, folder="synthetic", artifacts=(
        semantic.ModelArtifact("weights", 8, hashlib.sha256(b"approved").hexdigest()),))
    with pytest.raises(ModelNotConfiguredError, match="checksum"):
        semantic._verified_model_directory(tmp_path, model)


def test_real_directory_junction_outside_cache_is_rejected(tmp_path):
    import subprocess

    outside = tmp_path.parent / f"outside-{tmp_path.name}"
    outside.mkdir()
    (outside / "weights").write_bytes(b"approved")
    link = tmp_path / "synthetic"
    result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)],
                            capture_output=True, timeout=5, check=False)
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    model = replace(semantic.E5_MODEL, folder="synthetic", artifacts=(
        semantic.ModelArtifact("weights", 8, hashlib.sha256(b"approved").hexdigest()),))
    with pytest.raises(ModelNotConfiguredError, match="outside cache"):
        semantic._verified_model_directory(tmp_path, model)


def test_real_padding_batch_order_duplicate_and_rerank():
    models = semantic.LocalSemanticModels(Path(os.environ["R05_SEMANTIC_CACHE"]))
    paragraphs = (
        "访问控制可以阻止未授权用户读取其他租户的证据。",
        "Authorization prevents an unauthorised user from reading another tenant's evidence.",
        "The garden flowers are watered each morning.",
        "访问控制可以阻止未授权用户读取其他租户的证据。",
    )
    single = models.embed_passages((paragraphs[0],)).vectors[0]
    batch = models.embed_passages(paragraphs).vectors
    query = models.embed_query("如何保护其他租户的证据？")
    assert len(batch) == 4 and query.dimension == 384
    assert max(abs(a - b) for a, b in zip(single, batch[0], strict=True)) < 1e-5
    assert batch[0] == batch[3] and batch[0] != batch[1]
    for row in (*batch, *query.vectors):
        assert len(row) == 384 and all(type(value) is float and math.isfinite(value) for value in row)
        assert math.isclose(sum(value * value for value in row), 1, abs_tol=1e-5)
    ranked = models.rerank("如何保护其他租户的证据？", paragraphs)
    assert sorted(item.index for item in ranked.items) == [0, 1, 2, 3]
    scores = {item.index: item.score for item in ranked.items}
    assert scores[0] == scores[3]
    assert [item.index for item in ranked.items].index(0) < [item.index for item in ranked.items].index(3)
    print({"kind": "independent_real_smoke", "ranked": [(item.index, item.score) for item in ranked.items],
           "quality_threshold": None})


def test_real_maximum_batch_at_512_tokens_and_513_rejection():
    from tokenizers import Tokenizer

    cache = Path(os.environ["R05_SEMANTIC_CACHE"])
    tokenizer = Tokenizer.from_file(str(cache / "e5/tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    words = 1
    while len(tokenizer.encode("passage: " + "word " * words).ids) < 512:
        words += 1
    paragraph = "word " * words
    assert len(tokenizer.encode("passage: " + paragraph).ids) == 512
    models = semantic.LocalSemanticModels(cache)
    start = time.monotonic()
    batch = models.embed_passages((paragraph,) * 8)
    assert len(batch.vectors) == 8 and all(row == batch.vectors[0] for row in batch.vectors)
    print({"kind": "independent_max_batch", "batch": 8, "tokens": 512,
           "seconds": time.monotonic() - start})
    with pytest.raises(semantic.SemanticInputError, match="512 token"):
        models.embed_passages((paragraph + "word ",))
