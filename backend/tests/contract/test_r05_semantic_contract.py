"""Local provider contract, including real process cleanup on unavailable artifacts."""

import multiprocessing
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from ai_intel.infrastructure.models import semantic
from ai_intel.infrastructure.models.clients import ModelNotConfiguredError
from ai_intel.infrastructure.models.semantic import E5_MODEL, RERANK_MODEL, LocalSemanticModels


def test_model_spaces_pin_source_revision_weights_tokenizer_and_codec() -> None:
    assert E5_MODEL.revision == "614241f622f53c4eeff9890bdc4f31cfecc418b3"
    assert RERANK_MODEL.revision == "1427fd652930e4ba29e8149678df786c240d8825"
    assert E5_MODEL.model_version != RERANK_MODEL.model_version
    changed_tokenizer = replace(E5_MODEL.artifacts[1], sha256="f" * 64)
    other_space = replace(E5_MODEL, artifacts=(E5_MODEL.artifacts[0], changed_tokenizer))
    assert other_space.model_version != E5_MODEL.model_version


def test_embedding_domain_result_is_immutable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    row = [1.0] + [0.0] * 383
    monkeypatch.setattr(semantic, "_run_worker", lambda *args: [row])
    result = LocalSemanticModels(tmp_path).embed_query("question")
    assert isinstance(result.vectors, tuple) and isinstance(result.vectors[0], tuple)
    with pytest.raises(FrozenInstanceError):
        result.dimension = 3
    row[0] = 0.0
    assert result.vectors[0][0] == 1.0


def test_missing_weights_in_real_spawn_fail_closed_and_reap_child(tmp_path: Path) -> None:
    client = LocalSemanticModels(tmp_path)
    before = {child.pid for child in multiprocessing.active_children()}
    with pytest.raises(ModelNotConfiguredError):
        client.embed_query("private input must remain in memory")
    assert {child.pid for child in multiprocessing.active_children()} == before


def test_modified_local_weights_in_real_spawn_are_not_loaded(tmp_path: Path) -> None:
    artifact = tmp_path / "e5" / "onnx" / "model.onnx"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"unverified model content")
    with pytest.raises(ModelNotConfiguredError):
        LocalSemanticModels(tmp_path).embed_query("question")
