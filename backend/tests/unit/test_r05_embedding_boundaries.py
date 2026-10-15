"""共享向量边界拒绝无法安全进入真实 pgvector 的值。"""

import pytest

from ai_intel.infrastructure.models.clients import ModelContractError, validate_embedding_batch


@pytest.mark.parametrize(
    "vectors",
    [
        [[float("nan"), 1.0]],
        [[float("inf"), 1.0]],
        [[True, 1.0]],
        [[1, 1.0]],
        [[1e39, 1.0]],
        [[0.0, -0.0]],
        [["1.0", 1.0]],
    ],
)
def test_invalid_coordinates_do_not_become_indexable(vectors: list[list[float]]) -> None:
    with pytest.raises(ModelContractError):
        validate_embedding_batch(vectors, 1, 2, "embedding-v1")


@pytest.mark.parametrize(
    "count,dimension", [(0, 2), (257, 2), (True, 2), (1, 0), (1, 4097), (1, True)]
)
def test_invalid_batch_metadata_is_rejected(count: int, dimension: int) -> None:
    with pytest.raises(ModelContractError):
        validate_embedding_batch([[1.0, 0.0]], count, dimension, "embedding-v1")


@pytest.mark.parametrize("version", ["", "has space", "has\nnewline", "中文", "x" * 201])
def test_invalid_space_identifier_is_rejected(version: str) -> None:
    with pytest.raises(ModelContractError):
        validate_embedding_batch([[1.0, 0.0]], 1, 2, version)


def test_vectors_are_frozen_without_normalizing_or_reordering() -> None:
    original = [[0.0, 2.0], [-3.0, 4.0]]
    result = validate_embedding_batch(original, 2, 2, "intfloat/e5@revision;space=fingerprint")
    original[0][1] = 7.0
    assert result.vectors == ((0.0, 2.0), (-3.0, 4.0))


@pytest.mark.parametrize("coordinate", [1e-50, -(1e-50), 2.0 ** -150])
def test_underflow_to_float32_zero_cannot_enter_cosine_index(coordinate: float) -> None:
    with pytest.raises(ModelContractError, match="zero embedding"):
        validate_embedding_batch([[coordinate] * 384], 1, 384, "float32-underflow-v1")


def test_smallest_representable_float32_subnormal_remains_valid() -> None:
    coordinate = 2.0 ** -149
    result = validate_embedding_batch([[coordinate] * 384], 1, 384, "float32-subnormal-v1")
    assert result.vectors == ((coordinate,) * 384,)
