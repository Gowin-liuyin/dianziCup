"""Outbox-triggered full-scope projections; the PG receipt follows successful OS refresh."""

from __future__ import annotations

import hashlib
import json
import math
import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.knowledge.models import outbox_events
from ai_intel.knowledge.persistence_models import change_events
from ai_intel.retrieval.hybrid import (
    candidate_values,
    candidates_from_rows,
    facts_query,
    read_scope_epochs,
    require_generation,
)
from ai_intel.retrieval.hybrid_contracts import (
    HybridQuery,
    HybridRetrievalError,
    IndexChange,
    IndexGeneration,
    IndexReceipt,
)
from ai_intel.retrieval.hybrid_schema import (
    hybrid_chunks,
    hybrid_index_generations,
    hybrid_index_receipts,
    hybrid_index_watermarks,
)
from ai_intel.retrieval.opensearch_client import OpenSearchCorpusClient
from ai_intel.retrieval.service import EventEvidenceRetriever, SemanticModels

MAX_SCOPE_CHUNKS = 10000


class HybridIndexer:
    def __init__(
        self,
        engine: Engine,
        models: SemanticModels,
        search: OpenSearchCorpusClient,
        generation: IndexGeneration,
    ) -> None:
        generation.require_fixed_space()
        self.engine, self.models, self.search, self.generation = engine, models, search, generation

    def prepare_generation(self) -> None:
        """Root must first apply the proposed migration; this method never creates PG tables."""
        with Session(self.engine) as session, session.begin():
            existing = (
                session.execute(
                    select(hybrid_index_generations).where(
                        hybrid_index_generations.c.generation_id == self.generation.generation_id
                    )
                )
                .mappings()
                .one_or_none()
            )
            if existing is not None:
                require_generation(session, self.generation)
                self.search.verify_index(self.generation)
                return
            self.search.create_index(self.generation)
            session.execute(
                insert(hybrid_index_generations).values(
                    generation_id=self.generation.generation_id,
                    index_name=self.generation.index_name,
                    model_version=self.generation.model_version,
                    dimension=self.generation.dimension,
                    state="ready",
                    created_at=datetime.now(UTC),
                )
            )

    def refresh_scope(self, change: IndexChange, *, deadline: float | None = None) -> IndexReceipt:
        """An optional worker deadline bounds IO and prevents a late PG receipt commit."""
        if deadline is not None and (
            type(deadline) not in (int, float) or not math.isfinite(deadline)
        ):
            raise ValueError("index deadline must be a finite monotonic timestamp")

        def require_deadline() -> None:
            if deadline is not None and time.monotonic() >= deadline:
                raise HybridRetrievalError("corpus_projection_deadline_exceeded")

        require_deadline()
        UUID(change.outbox_id)
        if change.scope_key == "public":
            tenant = None
        elif change.scope_key.startswith("tenant:") and change.scope_key[7:]:
            tenant = change.scope_key[7:]
        else:
            raise ValueError("invalid index scope")
        worker_scope = AccessScope.for_authenticated_user("internal-indexer", tenant, Role.ANALYST)
        with Session(self.engine) as session, session.begin():
            session.execute(
                select(
                    func.pg_advisory_xact_lock(
                        func.hashtextextended(
                            "hybrid-index:"
                            + self.generation.generation_id
                            + ":"
                            + change.scope_key,
                            0,
                        )
                    )
                )
            )
            require_generation(session, self.generation)
            outbox = (
                session.execute(
                    select(outbox_events).where(
                        outbox_events.c.event_id == change.outbox_id,
                        outbox_events.c.topic == "job.knowledge_change",
                    )
                )
                .mappings()
                .one_or_none()
            )
            if outbox is None or not outbox["payload_ref"].startswith("pg:change:"):
                raise HybridRetrievalError("index_change_not_authoritative")
            event = (
                session.execute(
                    select(change_events).where(
                        change_events.c.change_id == outbox["payload_ref"][10:],
                        change_events.c.scope_key == change.scope_key,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if event is None:
                raise HybridRetrievalError("index_change_not_authoritative")
            prior = (
                session.execute(
                    select(hybrid_index_receipts).where(
                        hybrid_index_receipts.c.generation_id == self.generation.generation_id,
                        hybrid_index_receipts.c.outbox_id == change.outbox_id,
                    )
                )
                .mappings()
                .one_or_none()
            )
            if prior is not None:
                if prior["scope_key"] != change.scope_key:
                    raise HybridRetrievalError("index_receipt_scope_conflict")
                return IndexReceipt(
                    self.generation.generation_id,
                    change.outbox_id,
                    change.scope_key,
                    prior["indexed_epoch"],
                    prior["chunk_count"],
                    True,
                )
            epochs = read_scope_epochs(session, worker_scope)
            epoch = epochs[change.scope_key]
            if event["epoch"] > epoch:
                raise HybridRetrievalError("index_change_epoch_invalid")
            rows = list(
                session.execute(
                    facts_query(
                        worker_scope,
                        HybridQuery(
                            "internal indexing",
                            available_before=datetime.max.replace(tzinfo=UTC),
                            include_graph=False,
                        ),
                    ).limit(MAX_SCOPE_CHUNKS + 1)
                ).mappings()
            )
            if len(rows) > MAX_SCOPE_CHUNKS:
                raise HybridRetrievalError("index_scope_capacity_exceeded")
            candidates = tuple(
                item
                for item in candidates_from_rows(session, worker_scope, rows)
                if item.scope_key == change.scope_key
            )
            if len(candidates) > MAX_SCOPE_CHUNKS:
                raise HybridRetrievalError("index_scope_capacity_exceeded")
            vectors: list[tuple[float, ...]] = []
            for start in range(0, len(candidates), 8):
                require_deadline()
                batch = candidates[start : start + 8]
                embedded = self.models.embed_passages(tuple(item.text for item in batch))
                EventEvidenceRetriever._embedding(embedded, len(batch))
                vectors.extend(embedded.vectors)
            require_deadline()
            self.search.upsert(self.generation, candidates, epoch)
            require_deadline()
            self.search.refresh(self.generation)
            require_deadline()
            self.search.remove_older_scope(self.generation, change.scope_key, epoch)
            require_deadline()
            self.search.refresh(self.generation)
            require_deadline()
            if read_scope_epochs(session, worker_scope, lock=True) != epochs:
                raise HybridRetrievalError("index_scope_changed_retry_required")
            session.execute(
                delete(hybrid_chunks).where(
                    hybrid_chunks.c.generation_id == self.generation.generation_id,
                    hybrid_chunks.c.scope_key == change.scope_key,
                )
            )
            now = datetime.now(UTC)
            for candidate, vector in zip(candidates, vectors, strict=True):
                require_deadline()
                session.execute(
                    insert(hybrid_chunks).values(
                        **candidate_values(candidate),
                        generation_id=self.generation.generation_id,
                        model_version=self.generation.model_version,
                        embedding=list(vector),
                        indexed_epoch=epoch,
                        indexed_at=now,
                    )
                )
            digest = hashlib.sha256(
                json.dumps(
                    [[item.chunk_id, item.text_sha256] for item in candidates],
                    separators=(",", ":"),
                ).encode()
            ).hexdigest()
            session.execute(
                insert(hybrid_index_watermarks)
                .values(
                    generation_id=self.generation.generation_id,
                    scope_key=change.scope_key,
                    indexed_epoch=epoch,
                    outbox_id=change.outbox_id,
                    refreshed_at=now,
                )
                .on_conflict_do_update(
                    index_elements=["generation_id", "scope_key"],
                    set_={
                        "indexed_epoch": epoch,
                        "outbox_id": change.outbox_id,
                        "refreshed_at": now,
                    },
                )
            )
            session.execute(
                insert(hybrid_index_receipts).values(
                    generation_id=self.generation.generation_id,
                    outbox_id=change.outbox_id,
                    scope_key=change.scope_key,
                    indexed_epoch=epoch,
                    chunk_count=len(candidates),
                    payload_sha256=digest,
                    completed_at=now,
                )
            )
            require_deadline()
            return IndexReceipt(
                self.generation.generation_id,
                change.outbox_id,
                change.scope_key,
                epoch,
                len(candidates),
                False,
            )
