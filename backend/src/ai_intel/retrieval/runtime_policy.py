"""Wire the existing PG-authoritative corpus indexer into the durable worker."""

from __future__ import annotations

import ssl
import time
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, replace

import httpx
from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.infrastructure.models.clients import (
    EmbeddingResult,
    ModelContractError,
    ModelNotConfiguredError,
)
from ai_intel.infrastructure.models.semantic import (
    LocalSemanticModels,
    RerankResult,
    SemanticRuntimeError,
    SemanticTimeoutError,
)
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import job_runs, outbox_events
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.retrieval.hybrid_contracts import HybridRetrievalError, IndexChange, IndexGeneration
from ai_intel.retrieval.indexing import HybridIndexer
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient
from ai_intel.workers.executor import (
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
    JobHandler,
)

KNOWLEDGE_CHANGE_JOB_TYPE = "knowledge_change"
PROJECTION_TIMEOUT_SECONDS = 20.0


@dataclass(frozen=True)
class _DeadlineSemanticModels:
    """Each native inference receives the remaining duration of this single worker job."""

    models: LocalSemanticModels
    deadline: float

    def _bounded_client(self) -> LocalSemanticModels:
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise SemanticTimeoutError("corpus_projection_deadline_exceeded")
        return replace(self.models, timeout_seconds=min(self.models.timeout_seconds, remaining))

    def embed_query(self, query: str) -> EmbeddingResult:
        return self._bounded_client().embed_query(query)

    def embed_passages(self, passages: tuple[str, ...]) -> EmbeddingResult:
        return self._bounded_client().embed_passages(passages)

    def rerank(self, query: str, passages: tuple[str, ...]) -> RerankResult:
        return self._bounded_client().rerank(query, passages)


def find_projection_change(session: Session, context: JobExecutionContext) -> IndexChange:
    """Choose a persisted outbox receipt for this exact leased job and tenant."""
    scope_key = "public" if context.tenant_id is None else "tenant:" + context.tenant_id
    rows = session.execute(
        select(outbox_events.c.event_id, change_events.c.scope_key)
        .select_from(
            outbox_events.join(job_runs, job_runs.c.job_id == outbox_events.c.job_id).join(
                change_events,
                job_runs.c.payload_ref == "pg:change:" + change_events.c.change_id,
            )
        )
        .where(
            job_runs.c.job_id == context.job_id,
            job_runs.c.job_type == KNOWLEDGE_CHANGE_JOB_TYPE,
            job_runs.c.tenant_id.is_(None)
            if context.tenant_id is None
            else job_runs.c.tenant_id == context.tenant_id,
            outbox_events.c.topic == "job.knowledge_change",
            outbox_events.c.payload_ref == job_runs.c.payload_ref,
            change_events.c.scope_key == scope_key,
        )
        .order_by(outbox_events.c.created_at, outbox_events.c.event_id)
        .limit(1)
    ).one_or_none()
    if rows is None:
        raise JobExecutionError("index_change_not_authoritative", blocked=True)
    return IndexChange(str(rows.event_id), str(rows.scope_key))


def make_knowledge_change_handler(
    indexer: HybridIndexer | None, *, projection_deadline: float | None = None
) -> JobHandler:
    """Projection retries reuse the PG receipt; missing dependencies remain explicit."""

    def project_change(
        session: Session, context: JobExecutionContext, payload: bytes
    ) -> JobExecutionResult:
        if indexer is None:
            raise JobExecutionError("corpus_projection_not_configured", blocked=True)
        change = find_projection_change(session, context)
        deadline = (
            time.monotonic() + PROJECTION_TIMEOUT_SECONDS
            if projection_deadline is None
            else projection_deadline
        )
        try:
            indexer.prepare_generation()
            receipt = indexer.refresh_scope(change, deadline=deadline)
        except HybridRetrievalError as error:
            raise JobExecutionError(str(error)) from None
        except ModelNotConfiguredError:
            raise JobExecutionError("corpus_models_not_configured", blocked=True) from None
        except SemanticTimeoutError:
            raise JobExecutionError("corpus_projection_deadline_exceeded") from None
        except (SemanticRuntimeError, ModelContractError):
            raise JobExecutionError("corpus_semantic_runtime_unavailable") from None
        if time.monotonic() >= deadline:
            raise JobExecutionError("corpus_projection_deadline_exceeded")
        return JobExecutionResult(
            outcome="partial",
            result_ref="pg:hybrid_receipt:" + receipt.outbox_id,
            error_code="knowledge_change_other_consumers_pending",
        )

    return project_change


@contextmanager
def build_projection_job_handlers(
    engine: Engine, settings: ApplicationSettings
) -> Iterator[dict[str, JobHandler]]:
    """Open only the configured internal search client, and close it after each job."""
    if settings.opensearch_url is None or settings.semantic_model_cache_directory is None:
        yield {KNOWLEDGE_CHANGE_JOB_TYPE: make_knowledge_change_handler(None)}
        return
    generation = IndexGeneration(settings.hybrid_generation_id, settings.hybrid_index_name)
    generation.require_fixed_space()
    authentication = None
    if settings.opensearch_username is not None and settings.opensearch_password is not None:
        authentication = httpx.BasicAuth(
            settings.opensearch_username, settings.opensearch_password.get_secret_value()
        )
    with httpx.Client(
        base_url=settings.opensearch_url,
        timeout=settings.dependency_timeout_seconds,
        auth=authentication,
        verify=ssl.create_default_context(cafile=settings.opensearch_ca_file),
        trust_env=False,
    ) as client:
        deadline = time.monotonic() + PROJECTION_TIMEOUT_SECONDS
        models = _DeadlineSemanticModels(
            LocalSemanticModels(settings.semantic_model_cache_directory, timeout_seconds=10.0),
            deadline,
        )

        def async_search_client() -> httpx.AsyncClient:
            return httpx.AsyncClient(
                base_url=client.base_url,
                timeout=settings.dependency_timeout_seconds,
                auth=authentication,
                verify=ssl.create_default_context(cafile=settings.opensearch_ca_file),
                trust_env=False,
            )

        search = OpenSearchCorpusClient(
            client, deadline=deadline, async_client_factory=async_search_client
        )
        indexer = HybridIndexer(engine, models, search, generation)
        yield {
            KNOWLEDGE_CHANGE_JOB_TYPE: make_knowledge_change_handler(
                indexer, projection_deadline=deadline
            )
        }
