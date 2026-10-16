"""Explicit offline assembly checks; these fixtures do not count as live projections."""

import time
from pathlib import Path

import pytest
from sqlalchemy import create_engine

from ai_intel.infrastructure.models.semantic import LocalSemanticModels, SemanticTimeoutError
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.retrieval.hybrid_contracts import IndexChange
from ai_intel.retrieval.indexing import HybridIndexer
from ai_intel.retrieval.runtime_policy import (
    KNOWLEDGE_CHANGE_JOB_TYPE,
    _DeadlineSemanticModels,
    build_projection_job_handlers,
    make_knowledge_change_handler,
)
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError


def test_unconfigured_projection_has_a_registered_blocking_handler() -> None:
    engine = create_engine("sqlite://")
    try:
        with build_projection_job_handlers(engine, ApplicationSettings()) as handlers:
            assert set(handlers) == {KNOWLEDGE_CHANGE_JOB_TYPE}
            with pytest.raises(
                JobExecutionError, match="corpus_projection_not_configured"
            ) as error:
                handlers[KNOWLEDGE_CHANGE_JOB_TYPE](
                    None, JobExecutionContext("synthetic-job", "fixture-worker", 1, None), b"{}"
                )
            assert error.value.blocked
    finally:
        engine.dispose()


@pytest.mark.parametrize("missing", ("opensearch_url", "semantic_model_cache_directory"))
def test_partial_configuration_does_not_open_external_clients(missing: str) -> None:
    values = {
        "opensearch_url": "http://127.0.0.1:29200",
        "semantic_model_cache_directory": Path("D:/explicit-unit-model-cache"),
        missing: None,
    }
    engine = create_engine("sqlite://")
    try:
        with build_projection_job_handlers(engine, ApplicationSettings(**values)) as handlers:
            assert KNOWLEDGE_CHANGE_JOB_TYPE in handlers
    finally:
        engine.dispose()


@pytest.mark.parametrize("deadline", (float("inf"), float("nan"), True))
def test_invalid_deadline_is_rejected_before_database_or_external_io(deadline: float) -> None:
    with pytest.raises(ValueError, match="finite monotonic"):
        HybridIndexer.refresh_scope(None, IndexChange("not-a-uuid", "public"), deadline=deadline)


def test_expired_deadline_is_rejected_before_database_or_external_io() -> None:
    with pytest.raises(RuntimeError, match="corpus_projection_deadline_exceeded"):
        HybridIndexer.refresh_scope(None, IndexChange("not-a-uuid", "public"), deadline=0.0)


def test_factory_handler_does_not_treat_missing_dependencies_as_an_empty_success() -> None:
    handler = make_knowledge_change_handler(None)
    with pytest.raises(JobExecutionError):
        handler(None, JobExecutionContext("fixture", "fixture", 1, "fixture-tenant"), b"{}")


def test_native_call_timeout_is_clipped_to_remaining_job_duration(tmp_path: Path) -> None:
    original = LocalSemanticModels(tmp_path, timeout_seconds=10.0)
    bounded = _DeadlineSemanticModels(original, deadline=time.monotonic() + 5.0)
    assert 0 < bounded._bounded_client().timeout_seconds <= 5.0
    assert original.timeout_seconds == 10.0


def test_expired_native_budget_never_starts_model_inference(tmp_path: Path) -> None:
    bounded = _DeadlineSemanticModels(LocalSemanticModels(tmp_path), time.monotonic() - 1.0)
    with pytest.raises(SemanticTimeoutError, match="corpus_projection_deadline_exceeded"):
        bounded.embed_passages(("explicit unit fixture",))
