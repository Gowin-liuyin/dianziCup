"""Explicit synthetic boundaries; no fixture claims to be a live semantic model."""

from pathlib import Path

import pytest

from ai_intel.infrastructure.models import semantic
from ai_intel.infrastructure.models.clients import ModelContractError, ModelNotConfiguredError
from ai_intel.infrastructure.models.semantic import (
    E5_MODEL,
    RERANK_MODEL,
    LocalSemanticModels,
    ModelArtifact,
    SemanticInputError,
)


@pytest.fixture
def client(tmp_path: Path) -> LocalSemanticModels:
    return LocalSemanticModels(tmp_path)


def vector(axis: int) -> list[float]:
    return [1.0 if index == axis else 0.0 for index in range(384)]


@pytest.mark.parametrize("timeout", [True, False, 0, -1, 31, float("nan"), float("inf")])
def test_configuration_rejects_invalid_deadline(tmp_path: Path, timeout: float) -> None:
    with pytest.raises(ValueError, match="timeout"):
        LocalSemanticModels(tmp_path, timeout)


def test_configuration_rejects_relative_cache() -> None:
    with pytest.raises(ValueError, match="absolute"):
        LocalSemanticModels(Path("models"))


@pytest.mark.parametrize("text", ["", "  ", "a\0b", "x" * 16385, "\ud800"])
def test_invalid_query_fails_before_worker(client: LocalSemanticModels, text: str) -> None:
    with pytest.raises(SemanticInputError):
        client.embed_query(text)
    with pytest.raises(SemanticInputError):
        client.rerank(text, ("paragraph",))


@pytest.mark.parametrize("passages", [(), ("",), ("x",) * 9])
def test_invalid_batch_is_not_empty_success(
    client: LocalSemanticModels, passages: tuple[str, ...]
) -> None:
    with pytest.raises(SemanticInputError):
        client.embed_passages(passages)
    with pytest.raises(SemanticInputError):
        client.rerank("question", passages)


def test_embedding_keeps_order_duplicates_and_prefix(
    client: LocalSemanticModels, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[tuple[str, tuple[str, ...]]] = []

    def run(
        configured: LocalSemanticModels,
        model: semantic.LocalModel,
        operation: str,
        texts: tuple[str, ...],
        query: str | None,
    ) -> object:
        assert configured is client
        assert model == E5_MODEL
        assert query is None
        calls.append((operation, texts))
        return [vector(0)] if operation == "query" else [vector(1), vector(0), vector(1)]

    monkeypatch.setattr(semantic, "_run_worker", run)
    result = client.embed_passages(("重复", "English", "重复"))
    assert result.dimension == 384
    assert result.vectors == (tuple(vector(1)), tuple(vector(0)), tuple(vector(1)))
    assert result.model_version == E5_MODEL.model_version
    assert client.embed_query("问题").vectors == (tuple(vector(0)),)
    assert calls == [("passage", ("重复", "English", "重复")), ("query", ("问题",))]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        [[1.0]],
        [[0.0] * 384],
        [[True] * 384],
        [[1] * 384],
        [[float("nan")] * 384],
        [[float("inf")] * 384],
        [[-float("inf")] * 384],
        [[0.5] * 384],
        [vector(0), vector(1)],
    ],
)
def test_embedding_rejects_malformed_backend_output(
    client: LocalSemanticModels, monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    monkeypatch.setattr(semantic, "_run_worker", lambda *args: payload)
    with pytest.raises(ModelContractError):
        client.embed_query("test")


def test_rerank_keeps_all_original_indexes_and_stable_ties(
    client: LocalSemanticModels, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(semantic, "_run_worker", lambda *args: [[-2.0], [3.0], [3.0], [-2.0]])
    result = client.rerank("query", ("repeat", "best", "best", "repeat"))
    assert [(item.index, item.score) for item in result.items] == [
        (1, 3.0),
        (2, 3.0),
        (0, -2.0),
        (3, -2.0),
    ]
    assert result.model_version == RERANK_MODEL.model_version


@pytest.mark.parametrize("payload", [[], [[float("nan")]], [[True]], [[1]], [[1.0, 2.0]]])
def test_rerank_rejects_invalid_scores(
    client: LocalSemanticModels, monkeypatch: pytest.MonkeyPatch, payload: object
) -> None:
    monkeypatch.setattr(semantic, "_run_worker", lambda *args: payload)
    with pytest.raises(ModelContractError):
        client.rerank("query", ("passage",))


def test_unavailable_cache_has_no_fallback(client: LocalSemanticModels) -> None:
    with pytest.raises(ModelNotConfiguredError):
        semantic._verified_model_directory(client.model_cache_directory, E5_MODEL)


def test_artifact_size_and_hash_are_both_checked(tmp_path: Path) -> None:
    import hashlib

    directory = tmp_path / "synthetic"
    directory.mkdir()
    artifact_path = directory / "weights"
    artifact_path.write_bytes(b"approved")
    model = semantic.LocalModel(
        "synthetic",
        "synthetic-only",
        "0" * 40,
        (ModelArtifact("weights", 8, hashlib.sha256(b"approved").hexdigest()),),
        "test",
    )
    assert semantic._verified_model_directory(tmp_path, model) == directory
    artifact_path.write_bytes(b"modified")
    with pytest.raises(ModelNotConfiguredError, match="checksum"):
        semantic._verified_model_directory(tmp_path, model)
    artifact_path.write_bytes(b"bigger content")
    with pytest.raises(ModelNotConfiguredError, match="size"):
        semantic._verified_model_directory(tmp_path, model)


def test_model_space_changes_for_other_artifact() -> None:
    from dataclasses import replace

    alternative = replace(
        E5_MODEL,
        artifacts=(replace(E5_MODEL.artifacts[0], sha256="0" * 64), E5_MODEL.artifacts[1]),
    )
    assert alternative.model_version != E5_MODEL.model_version


def test_busy_worker_fails_without_spawning(client: LocalSemanticModels) -> None:
    semantic._WORKER_LOCK.acquire()
    try:
        with pytest.raises(semantic.SemanticRuntimeError, match="busy"):
            client.embed_query("query")
    finally:
        semantic._WORKER_LOCK.release()


class WorkerPipe:
    def __init__(self, response: object, ready: bool = True) -> None:
        self.response = response
        self.ready = ready
        self.closed = False

    def poll(self, timeout: float) -> bool:
        assert 0 <= timeout <= 30
        return self.ready

    def recv(self) -> object:
        if self.response is None:
            raise EOFError
        return self.response

    def close(self) -> None:
        self.closed = True


class WorkerProcess:
    pid: int | None = None

    def __init__(self) -> None:
        self.alive = False
        self.terminated = False
        self.joined = False
        self.closed = False

    def start(self) -> None:
        self.pid = 1
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def terminate(self) -> None:
        self.terminated = True
        self.alive = False

    def kill(self) -> None:
        self.alive = False

    def join(self, timeout: float) -> None:
        self.joined = True

    def close(self) -> None:
        self.closed = True


class WorkerContext:
    def __init__(self, response: object, ready: bool = True) -> None:
        self.receiver = WorkerPipe(response, ready)
        self.sender = WorkerPipe(None)
        self.process = WorkerProcess()

    def Pipe(self, duplex: bool) -> tuple[WorkerPipe, WorkerPipe]:
        assert duplex is False
        return self.receiver, self.sender

    def Process(self, **kwargs: object) -> WorkerProcess:
        assert kwargs["daemon"] is True
        return self.process


@pytest.mark.parametrize(
    ("response", "ready", "error"),
    [
        (("input", None), True, SemanticInputError),
        (("unavailable", None), True, ModelNotConfiguredError),
        (("failed", "untrusted detail"), True, semantic.SemanticRuntimeError),
        (("not-status", None), True, semantic.SemanticRuntimeError),
        (["ok", []], True, ModelContractError),
        (("ok", []), False, semantic.SemanticTimeoutError),
        (None, True, semantic.SemanticRuntimeError),
    ],
)
def test_worker_errors_cleanup_without_fallback(
    client: LocalSemanticModels,
    monkeypatch: pytest.MonkeyPatch,
    response: object,
    ready: bool,
    error: type[Exception],
) -> None:
    context = WorkerContext(response, ready)
    monkeypatch.setattr(semantic.multiprocessing, "get_context", lambda *args: context)
    with pytest.raises(error) as captured:
        client.embed_query("private text must not enter error output")
    assert "private text" not in str(captured.value)
    assert "untrusted detail" not in str(captured.value)
    assert context.receiver.closed and context.sender.closed
    assert context.process.terminated and context.process.joined and context.process.closed
    assert not semantic._WORKER_LOCK.locked()


@pytest.mark.parametrize("stage", ["get_context", "pipe", "process", "start"])
@pytest.mark.parametrize("failure", [OSError, RuntimeError])
def test_initialization_failure_releases_capacity_and_allows_next_call(
    client: LocalSemanticModels,
    monkeypatch: pytest.MonkeyPatch,
    stage: str,
    failure: type[Exception],
) -> None:
    context = WorkerContext(("ok", [vector(0)]))

    def unavailable(*args: object, **kwargs: object) -> None:
        raise failure("sensitive initialization details")

    if stage == "get_context":
        monkeypatch.setattr(semantic.multiprocessing, "get_context", unavailable)
    else:
        monkeypatch.setattr(semantic.multiprocessing, "get_context", lambda *args: context)
        target = context.process if stage == "start" else context
        name = {"pipe": "Pipe", "process": "Process", "start": "start"}[stage]
        monkeypatch.setattr(target, name, unavailable)
    try:
        with pytest.raises(semantic.SemanticRuntimeError) as captured:
            client.embed_query("private question")
        assert "sensitive" not in str(captured.value)
        assert "private" not in str(captured.value)
        assert not semantic._WORKER_LOCK.locked()
        if stage in ("process", "start"):
            assert context.receiver.closed and context.sender.closed
        if stage == "start":
            assert context.process.closed
        healthy = WorkerContext(("ok", [vector(0)]))
        monkeypatch.setattr(semantic.multiprocessing, "get_context", lambda *args: healthy)
        assert client.embed_query("next question").vectors == (tuple(vector(0)),)
        assert healthy.receiver.closed and healthy.sender.closed
        assert healthy.process.closed and not semantic._WORKER_LOCK.locked()
    finally:
        if semantic._WORKER_LOCK.locked():
            semantic._WORKER_LOCK.release()


def test_cleanup_failure_preserves_primary_error_and_releases_capacity(
    client: LocalSemanticModels, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = WorkerContext(("input", None))

    def close_unavailable() -> None:
        raise OSError("sensitive cleanup details")

    monkeypatch.setattr(context.receiver, "close", close_unavailable)
    monkeypatch.setattr(semantic.multiprocessing, "get_context", lambda *args: context)
    try:
        with pytest.raises(SemanticInputError) as captured:
            client.embed_query("private question")
        assert "sensitive" not in str(captured.value)
        assert context.sender.closed and context.process.closed
        assert not semantic._WORKER_LOCK.locked()
        assert captured.value.__notes__ == ["local semantic worker cleanup was incomplete"]
    finally:
        if semantic._WORKER_LOCK.locked():
            semantic._WORKER_LOCK.release()


def test_cleanup_failure_on_success_is_visible_and_releases_capacity(
    client: LocalSemanticModels, monkeypatch: pytest.MonkeyPatch
) -> None:
    context = WorkerContext(("ok", [vector(0)]))

    def close_unavailable() -> None:
        raise OSError("sensitive cleanup details")

    monkeypatch.setattr(context.receiver, "close", close_unavailable)
    monkeypatch.setattr(semantic.multiprocessing, "get_context", lambda *args: context)
    try:
        with pytest.raises(semantic.SemanticRuntimeError, match="cleanup"):
            client.embed_query("question")
        assert context.process.closed
        assert not semantic._WORKER_LOCK.locked()
    finally:
        if semantic._WORKER_LOCK.locked():
            semantic._WORKER_LOCK.release()


def test_symlink_artifact_is_rejected_before_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifact_path = tmp_path / "e5" / "onnx" / "model.onnx"
    monkeypatch.setattr(Path, "is_symlink", lambda path: path == artifact_path)
    with pytest.raises(ModelNotConfiguredError, match="outside cache"):
        semantic._verified_model_directory(tmp_path, E5_MODEL)


def test_over_token_limit_fails_before_onnx_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    from types import SimpleNamespace

    class Tokenizer:
        truncated = True
        padded = True

        def no_truncation(self) -> None:
            self.truncated = False

        def no_padding(self) -> None:
            self.padded = False

        def encode_batch(self, inputs: object) -> list[SimpleNamespace]:
            assert not self.truncated and not self.padded
            return [SimpleNamespace(ids=[0] * 513)]

    tokenizer = Tokenizer()
    modules = {
        "tokenizers": SimpleNamespace(Tokenizer=SimpleNamespace(from_file=lambda path: tokenizer)),
        "onnxruntime": SimpleNamespace(disable_telemetry_events=lambda: None),
        "numpy": SimpleNamespace(),
    }
    monkeypatch.setattr(semantic, "import_module", lambda name: modules[name])
    with pytest.raises(SemanticInputError, match="token limit"):
        semantic._infer_local(tmp_path, E5_MODEL, "query", ("long tokenized input",), None)


def test_worker_applies_resource_limit_before_any_artifact_or_library_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    events: list[str] = []
    responses: list[object] = []

    class Sender:
        def send(self, payload: object) -> None:
            responses.append(payload)

        def close(self) -> None:
            events.append("closed")

    def bounded() -> None:
        events.append("resource-limit")
        raise OSError("limit unavailable")

    monkeypatch.setattr(semantic, "_bound_worker_memory", bounded)
    monkeypatch.setattr(semantic, "_verified_model_directory", lambda *args: pytest.fail("loaded"))
    semantic._semantic_worker(Sender(), tmp_path, E5_MODEL, "query", ("sensitive",), None)
    assert events == ["resource-limit", "closed"]
    assert responses == [("failed", None)]
