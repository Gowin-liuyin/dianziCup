"""Fixed, verified local ONNX models; bounded workers never download or execute model code."""

from __future__ import annotations

import hashlib
import math
import multiprocessing
import os
import threading
import time
from dataclasses import dataclass
from importlib import import_module
from multiprocessing.connection import Connection, _ConnectionBase
from multiprocessing.process import BaseProcess
from pathlib import Path
from typing import Literal

from ai_intel.infrastructure.models.clients import (
    EmbeddingResult,
    ModelContractError,
    ModelNotConfiguredError,
    validate_embedding_batch,
)

MAX_BATCH = 8
MAX_TOKENS = 512
MAX_TEXT_CHARACTERS = 16384
MAX_MEMORY_BYTES = 2 * 1024**3
_WORKER_LOCK = threading.Lock()


class SemanticInputError(ValueError):
    """Empty, oversized or malformed input is rejected without truncation."""


class SemanticRuntimeError(RuntimeError):
    """The local worker failed; this is never an empty successful result."""


class SemanticTimeoutError(TimeoutError):
    """The total worker deadline includes verification, loading and inference."""


@dataclass(frozen=True)
class ModelArtifact:
    relative_path: str
    size: int
    sha256: str


@dataclass(frozen=True)
class LocalModel:
    folder: str
    repository: str
    revision: str
    artifacts: tuple[ModelArtifact, ...]
    output_name: str

    @property
    def space_description(self) -> str:
        semantics = "query:/passage:;masked-mean;l2" if self.folder == "e5" else "pair;raw-logit"
        return (
            f"{self.repository}@{self.revision};onnx-fp32-v1;"
            f"weights={self.artifacts[0].sha256};tokenizer={self.artifacts[1].sha256};"
            f"{semantics};max512;dim={384 if self.folder == 'e5' else 1}"
        )

    @property
    def model_version(self) -> str:
        fingerprint = hashlib.sha256(self.space_description.encode("utf-8")).hexdigest()
        return f"{self.repository}@{self.revision};space={fingerprint}"


E5_MODEL = LocalModel(
    folder="e5",
    repository="intfloat/multilingual-e5-small",
    revision="614241f622f53c4eeff9890bdc4f31cfecc418b3",
    artifacts=(
        ModelArtifact(
            "onnx/model.onnx",
            470268510,
            "ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665",
        ),
        ModelArtifact(
            "tokenizer.json",
            17082730,
            "0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39",
        ),
    ),
    output_name="last_hidden_state",
)
RERANK_MODEL = LocalModel(
    folder="mmarco",
    repository="cross-encoder/mmarco-mMiniLMv2-L12-H384-v1",
    revision="1427fd652930e4ba29e8149678df786c240d8825",
    artifacts=(
        ModelArtifact(
            "onnx/model.onnx",
            470883696,
            "3e9a03ed1e966f7c5288dd4230e3d6a9bf5e3a170a06f1f4241c5bca12c6487c",
        ),
        ModelArtifact(
            "tokenizer.json",
            17082660,
            "62c24cdc13d4c9952d63718d6c9fa4c287974249e16b7ade6d5a85e7bbb75626",
        ),
    ),
    output_name="logits",
)


@dataclass(frozen=True)
class RankedPassage:
    index: int
    score: float


@dataclass(frozen=True)
class RerankResult:
    items: tuple[RankedPassage, ...]
    model_version: str


def _validate_text(text: str) -> None:
    if (
        not isinstance(text, str)
        or not text.strip()
        or len(text) > MAX_TEXT_CHARACTERS
        or "\0" in text
    ):
        raise SemanticInputError("text must be nonempty and within the character limit")
    try:
        text.encode("utf-8")
    except UnicodeError:
        raise SemanticInputError("text must be valid UTF-8") from None


def _validate_passages(passages: tuple[str, ...]) -> None:
    if not isinstance(passages, tuple) or not 1 <= len(passages) <= MAX_BATCH:
        raise SemanticInputError("passages must be a tuple containing one to eight texts")
    for passage in passages:
        _validate_text(passage)


def _float_rows(payload: object, count: int, dimension: int) -> list[list[float]]:
    if not isinstance(payload, list) or len(payload) != count:
        raise ModelContractError("local model output count mismatch")
    rows: list[list[float]] = []
    for row in payload:
        if not isinstance(row, list) or len(row) != dimension:
            raise ModelContractError("local model output dimension mismatch")
        values: list[float] = []
        for value in row:
            if type(value) is not float or not math.isfinite(value):
                raise ModelContractError("local model output must contain finite floats")
            values.append(value)
        rows.append(values)
    return rows


def _verified_model_directory(cache_root: Path, model: LocalModel) -> Path:
    directory = cache_root / model.folder
    for artifact in model.artifacts:
        path = directory / artifact.relative_path
        if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(cache_root):
            raise ModelNotConfiguredError("fixed local model artifact missing or outside cache")
        if path.stat().st_size != artifact.size:
            raise ModelNotConfiguredError("fixed local model artifact size mismatch")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
        if digest != artifact.sha256:
            raise ModelNotConfiguredError("fixed local model artifact checksum mismatch")
    return directory


@dataclass(frozen=True)
class LocalSemanticModels:
    """Construct once from trusted server configuration, never a request-supplied cache path."""

    model_cache_directory: Path
    timeout_seconds: float = 30.0

    def __post_init__(self) -> None:
        root = self.model_cache_directory
        if not isinstance(root, Path) or not root.is_absolute() or root.is_symlink():
            raise ValueError("model cache must be an absolute trusted directory")
        if (
            type(self.timeout_seconds) not in (int, float)
            or not math.isfinite(self.timeout_seconds)
            or not 0 < self.timeout_seconds <= 30
        ):
            raise ValueError("timeout must be finite and between zero and thirty seconds")
        object.__setattr__(self, "model_cache_directory", root.resolve())

    def embed_query(self, query: str) -> EmbeddingResult:
        _validate_text(query)
        return self._embed((query,), "query")

    def embed_passages(self, passages: tuple[str, ...]) -> EmbeddingResult:
        _validate_passages(passages)
        return self._embed(passages, "passage")

    def _embed(
        self, texts: tuple[str, ...], prefix: Literal["query", "passage"]
    ) -> EmbeddingResult:
        payload = _run_worker(self, E5_MODEL, prefix, texts, None)
        rows = _float_rows(payload, len(texts), 384)
        for row in rows:
            norm = math.sqrt(math.fsum(value * value for value in row))
            if not math.isclose(norm, 1.0, rel_tol=1e-5, abs_tol=1e-5):
                raise ModelContractError("local embedding must be nonzero and L2 normalized")
        return validate_embedding_batch(rows, len(texts), 384, E5_MODEL.model_version)

    def rerank(self, query: str, passages: tuple[str, ...]) -> RerankResult:
        _validate_text(query)
        _validate_passages(passages)
        payload = _run_worker(self, RERANK_MODEL, "rerank", passages, query)
        rows = _float_rows(payload, len(passages), 1)
        items = tuple(RankedPassage(index, row[0]) for index, row in enumerate(rows))
        return RerankResult(
            items=tuple(sorted(items, key=lambda item: (-item.score, item.index))),
            model_version=RERANK_MODEL.model_version,
        )


def _run_worker(
    client: LocalSemanticModels,
    model: LocalModel,
    operation: Literal["query", "passage", "rerank"],
    texts: tuple[str, ...],
    query: str | None,
) -> object:
    if not _WORKER_LOCK.acquire(blocking=False):
        raise SemanticRuntimeError("local semantic inference is already busy")
    receiving: _ConnectionBase | None = None
    sending: _ConnectionBase | None = None
    process: BaseProcess | None = None
    primary_error: BaseException | None = None
    try:
        try:
            deadline = time.monotonic() + client.timeout_seconds
            context = multiprocessing.get_context("spawn")
            receiving, sending = context.Pipe(duplex=False)
            process = context.Process(
                target=_semantic_worker,
                args=(sending, client.model_cache_directory, model, operation, texts, query),
                daemon=True,
            )
            process.start()
            sending.close()
        except Exception:
            raise SemanticRuntimeError("local semantic worker could not initialize") from None
        if not receiving.poll(max(0.0, deadline - time.monotonic())):
            raise SemanticTimeoutError("local semantic worker exceeded total deadline")
        try:
            response: object = receiving.recv()
        except EOFError:
            raise SemanticRuntimeError("local semantic worker exited without a result") from None
        if not isinstance(response, tuple) or len(response) != 2:
            raise ModelContractError("local worker returned an invalid envelope")
        status, payload = response
        if status == "input":
            raise SemanticInputError("input exceeds the 512 token limit; no truncation applied")
        if status == "unavailable":
            raise ModelNotConfiguredError("verified local model or runtime unavailable")
        if status != "ok":
            raise SemanticRuntimeError("local semantic worker failed")
        if time.monotonic() > deadline:
            raise SemanticTimeoutError("local semantic worker exceeded total deadline")
        return payload
    except BaseException as error:
        primary_error = error
        raise
    finally:
        cleanup_failed = False
        try:
            for connection in (sending, receiving):
                if connection is not None:
                    try:
                        connection.close()
                    except Exception:
                        cleanup_failed = True
            if process is not None:
                if process.pid is not None:
                    for stop in (process.terminate, process.kill):
                        try:
                            if process.is_alive():
                                stop()
                            process.join(timeout=1.0)
                        except Exception:
                            cleanup_failed = True
                try:
                    if process.pid is not None and process.is_alive():
                        cleanup_failed = True
                    else:
                        process.close()
                except Exception:
                    cleanup_failed = True
        finally:
            _WORKER_LOCK.release()
        if cleanup_failed:
            if primary_error is not None:
                primary_error.add_note("local semantic worker cleanup was incomplete")
            else:
                raise SemanticRuntimeError("local semantic worker cleanup failed") from None


def _semantic_worker(
    connection: Connection,
    cache_root: Path,
    model: LocalModel,
    operation: str,
    texts: tuple[str, ...],
    query: str | None,
) -> None:
    try:
        _bound_worker_memory()
        for name in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
            "RAYON_NUM_THREADS",
        ):
            os.environ[name] = "2"
        os.environ["TOKENIZERS_PARALLELISM"] = "false"
        directory = _verified_model_directory(cache_root, model)
        result = _infer_local(directory, model, operation, texts, query)
        connection.send(("ok", result))
    except SemanticInputError:
        connection.send(("input", None))
    except (ImportError, ModelNotConfiguredError):
        connection.send(("unavailable", None))
    except Exception:
        connection.send(("failed", None))
    finally:
        connection.close()


def _infer_local(
    directory: Path, model: LocalModel, operation: str, texts: tuple[str, ...], query: str | None
) -> object:
    """Third-party values stay inside this boundary; the caller validates plain float rows."""
    tokenizers = import_module("tokenizers")
    ort = import_module("onnxruntime")
    np = import_module("numpy")
    ort.disable_telemetry_events()
    tokenizer = tokenizers.Tokenizer.from_file(str(directory / "tokenizer.json"))
    tokenizer.no_truncation()
    tokenizer.no_padding()
    inputs = (
        [(query, text) for text in texts]
        if query is not None
        else [f"{operation}: {text}" for text in texts]
    )
    encoded = tokenizer.encode_batch(inputs)
    if any(len(item.ids) > MAX_TOKENS for item in encoded):
        raise SemanticInputError("token limit exceeded")
    tokenizer.enable_padding(pad_id=1, pad_token="<pad>")
    encoded = tokenizer.encode_batch(inputs)
    options = ort.SessionOptions()
    options.intra_op_num_threads = 2
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_DISABLE_ALL
    options.enable_mem_pattern = False
    options.enable_cpu_mem_arena = False
    session = ort.InferenceSession(
        str(directory / "onnx/model.onnx"), options, providers=["CPUExecutionProvider"]
    )
    session.disable_fallback()
    fields = {
        "input_ids": np.asarray([item.ids for item in encoded], dtype=np.int64),
        "attention_mask": np.asarray([item.attention_mask for item in encoded], dtype=np.int64),
        "token_type_ids": np.asarray([item.type_ids for item in encoded], dtype=np.int64),
    }
    names = {item.name for item in session.get_inputs()}
    values = session.run(
        [model.output_name], {name: value for name, value in fields.items() if name in names}
    )[0]
    if model == E5_MODEL:
        mask = fields["attention_mask"][..., None].astype(values.dtype)
        pooled = (values * mask).sum(axis=1) / mask.sum(axis=1)
        norms = np.linalg.norm(pooled, axis=1, keepdims=True)
        values = pooled / norms
    result: object = values.tolist()
    return result


def _bound_worker_memory() -> None:
    """Apply a hard 2GiB bound before importing the inference libraries; fail closed."""
    from ai_intel.infrastructure.process_limits import bound_process_resources

    bound_process_resources(memory_bytes=MAX_MEMORY_BYTES, cpu_seconds=30)
