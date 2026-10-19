"""R05单事件公开证据检索；真实向量在PG派生表，权限和有效性回查事实表。"""

from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.api.knowledge_contracts import CitationProjection
from ai_intel.api.knowledge_read_service import KnowledgeReadService, sources
from ai_intel.domain.access import READ_PUBLIC, AccessScope, CrossTenantAccessError
from ai_intel.infrastructure.models.clients import (
    EmbeddingResult,
    ModelContractError,
    validate_embedding_batch,
)
from ai_intel.infrastructure.models.semantic import E5_MODEL, RERANK_MODEL, RerankResult
from ai_intel.knowledge.models import document_revisions, documents, evidence, scope_epochs
from ai_intel.knowledge.persistence_models import claim_evidence, claims, event_documents, events
from ai_intel.retrieval.persistence_models import retrieval_chunks

MAX_EVIDENCE = 32
MAX_CHUNKS = 64
CHUNK_CHARACTERS = 240


class RetrievalFailure(RuntimeError):
    """固定安全失败码；没有索引或证据时不返回假成功的空答案。"""


class SemanticModels(Protocol):
    def embed_query(self, query: str) -> EmbeddingResult: ...

    def embed_passages(self, passages: tuple[str, ...]) -> EmbeddingResult: ...

    def rerank(self, query: str, passages: tuple[str, ...]) -> RerankResult: ...


@dataclass(frozen=True)
class EvidenceChunk:
    chunk_id: str
    evidence_id: UUID
    revision_id: UUID
    start_offset: int
    end_offset: int
    text: str
    text_sha256: str


@dataclass(frozen=True)
class EvidenceSelection:
    event_id: UUID
    citations: tuple[CitationProjection, ...]
    epoch: int
    embedding_model: str
    reranker_model: str
    candidate_count: int
    partial: bool


def split_evidence_quote(
    evidence_id: UUID, revision_id: UUID, quote: str
) -> tuple[EvidenceChunk, ...]:
    """单行派生片段使用相对永久quote的Unicode坐标，不改写原始换行。"""
    chunks: list[EvidenceChunk] = []
    position = 0
    for line in quote.splitlines(keepends=True):
        content = line.rstrip("\r\n\v\f\x1c\x1d\x1e\x85\u2028\u2029")
        for start in range(0, len(content), CHUNK_CHARACTERS):
            fragment = content[start : start + CHUNK_CHARACTERS]
            if not fragment.strip():
                continue
            offset = position + start
            digest = hashlib.sha256(fragment.encode("utf-8")).hexdigest()
            key = (
                f"{evidence_id}:{offset}:{offset + len(fragment)}:{digest}:{E5_MODEL.model_version}"
            )
            chunks.append(
                EvidenceChunk(
                    str(uuid5(NAMESPACE_URL, key)),
                    evidence_id,
                    revision_id,
                    offset,
                    offset + len(fragment),
                    fragment,
                    digest,
                )
            )
        position += len(line)
    return tuple(chunks)


def _public(relation: FromClause) -> ColumnElement[bool]:
    return and_(relation.c.visibility == "public", relation.c.tenant_id.is_(None))


def _event_evidence_query(event_id: UUID) -> Select[tuple[object, ...]]:
    active_support = exists(
        select(claim_evidence.c.claim_id)
        .select_from(claim_evidence.join(claims))
        .where(
            claim_evidence.c.evidence_id == evidence.c.evidence_id,
            claim_evidence.c.validation_status == "validated",
            claim_evidence.c.support_kind == "supports",
            claims.c.source_revision_id == document_revisions.c.revision_id,
            claims.c.is_current.is_(True),
            claims.c.claim_status == "supported",
            claims.c.freshness == "current",
            _public(claims),
        )
    )
    source_withdrawn = exists(
        select(claims.c.claim_id).where(
            claims.c.source_revision_id == document_revisions.c.revision_id,
            claims.c.is_current.is_(True),
            claims.c.claim_status == "supported",
            _public(claims),
            or_(
                claims.c.predicate == "source_withdrawn_at",
                and_(
                    claims.c.predicate == "source_status",
                    func.lower(claims.c.object_value).in_(("rejected", "withdrawn")),
                ),
            ),
        )
    )
    return (
        select(evidence)
        .select_from(
            evidence.join(document_revisions)
            .join(documents)
            .join(sources, sources.c.source_id == documents.c.source_id)
            .join(
                event_documents, event_documents.c.revision_id == document_revisions.c.revision_id
            )
            .join(events, events.c.event_id == event_documents.c.event_id)
        )
        .where(
            events.c.event_id == str(event_id),
            event_documents.c.active.is_(True),
            document_revisions.c.is_current.is_(True),
            document_revisions.c.parse_status.in_(("parsed", "partial")),
            documents.c.kind != "asset_inventory",
            active_support,
            ~source_withdrawn,
            *(
                _public(table)
                for table in (events, evidence, document_revisions, documents, sources)
            ),
        )
        .order_by(evidence.c.evidence_id)
    )


def current_public_epoch(session: Session, *, lock: bool = False) -> int:
    query = select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == "public")
    if lock:
        query = query.with_for_update(read=True)
    value = session.scalar(query)
    return 0 if value is None else int(value)


class EventEvidenceRetriever:
    """R05只为显式单事件建立/查询索引；R12的全库混合检索另有验收。"""

    def __init__(self, engine: Engine, models: SemanticModels) -> None:
        self.engine = engine
        self.models = models

    def retrieve(self, scope: AccessScope, event_id: UUID, question: str) -> EvidenceSelection:
        scope.requires(READ_PUBLIC)
        with Session(self.engine) as session:
            visible = session.scalar(
                select(events.c.event_id).where(events.c.event_id == str(event_id), _public(events))
            )
            if visible is None:
                raise CrossTenantAccessError("resource not found")
            epoch = current_public_epoch(session)
            rows = list(
                session.execute(_event_evidence_query(event_id).limit(MAX_EVIDENCE + 1)).mappings()
            )
            partial = len(rows) > MAX_EVIDENCE
            rows = rows[:MAX_EVIDENCE]
            read_service = KnowledgeReadService(session, scope, "live")
            available: dict[UUID, CitationProjection] = {}
            chunks: list[EvidenceChunk] = []
            for row in rows:
                projection = read_service.read_evidence(UUID(row["evidence_id"]))
                if projection.verified_at is None or projection.source_uri is None:
                    partial = True
                    continue
                available[projection.span_id] = CitationProjection(
                    evidence_id=projection.span_id,
                    revision_id=projection.revision_id,
                    quote=projection.quote_text,
                    locator=row["locator"],
                    source_uri=projection.source_uri,
                )
                chunks.extend(
                    split_evidence_quote(
                        projection.span_id, projection.revision_id, projection.quote_text
                    )
                )
            partial = partial or len(chunks) > MAX_CHUNKS
            chunks = chunks[:MAX_CHUNKS]
            existing: set[str] = set(
                session.scalars(
                    select(retrieval_chunks.c.chunk_id).where(
                        retrieval_chunks.c.chunk_id.in_([chunk.chunk_id for chunk in chunks])
                    )
                )
            )
        if not chunks:
            raise RetrievalFailure("answer_evidence_unavailable")
        missing = [chunk for chunk in chunks if chunk.chunk_id not in existing]
        pending: list[tuple[EvidenceChunk, tuple[float, ...]]] = []
        for offset in range(0, len(missing), 8):
            batch = missing[offset : offset + 8]
            embedded = self.models.embed_passages(tuple(chunk.text for chunk in batch))
            self._embedding(embedded, len(batch))
            pending.extend(zip(batch, embedded.vectors, strict=True))
        with Session(self.engine) as session, session.begin():
            self.require_current(session, scope, event_id, epoch, tuple(available.values()))
            for chunk, vector in pending:
                session.execute(
                    insert(retrieval_chunks)
                    .values(
                        chunk_id=chunk.chunk_id,
                        evidence_id=str(chunk.evidence_id),
                        revision_id=str(chunk.revision_id),
                        start_offset=chunk.start_offset,
                        end_offset=chunk.end_offset,
                        chunk_text=chunk.text,
                        text_sha256=chunk.text_sha256,
                        model_version=E5_MODEL.model_version,
                        embedding=list(vector),
                        indexed_at=datetime.now(UTC),
                    )
                    .on_conflict_do_nothing()
                )
        query = self.models.embed_query(question)
        self._embedding(query, 1)
        with Session(self.engine) as session:
            self.require_current(session, scope, event_id, epoch, tuple(available.values()))
            distance = retrieval_chunks.c.embedding.cosine_distance(list(query.vectors[0]))
            selected = list(
                session.execute(
                    select(retrieval_chunks)
                    .where(
                        retrieval_chunks.c.chunk_id.in_([chunk.chunk_id for chunk in chunks]),
                        retrieval_chunks.c.model_version == E5_MODEL.model_version,
                    )
                    .order_by(distance, retrieval_chunks.c.chunk_id)
                    .limit(8)
                ).mappings()
            )
        originals = {chunk.chunk_id: chunk for chunk in chunks}
        for row in selected:
            self._require_derived_integrity(row, originals[row["chunk_id"]])
        reranked = self.models.rerank(question, tuple(row["chunk_text"] for row in selected))
        if (
            reranked.model_version != RERANK_MODEL.model_version
            or sorted(item.index for item in reranked.items) != list(range(len(selected)))
            or any(
                type(item.index) is not int or not math.isfinite(item.score)
                for item in reranked.items
            )
        ):
            raise ModelContractError("reranker space or indices do not match candidates")
        citations: list[CitationProjection] = []
        seen: set[UUID] = set()
        for item in reranked.items:
            row = selected[item.index]
            source = available[UUID(row["evidence_id"])]
            if source.evidence_id in seen:
                continue
            seen.add(source.evidence_id)
            citations.append(
                source.model_copy(
                    update={
                        "quote": row["chunk_text"],
                        "locator": (
                            f"{source.locator}; quote_unicode["
                            f"{row['start_offset']}:{row['end_offset']}]"
                        ),
                    }
                )
            )
        return EvidenceSelection(
            event_id,
            tuple(citations),
            epoch,
            E5_MODEL.model_version,
            reranked.model_version,
            len(chunks),
            partial,
        )

    @staticmethod
    def _embedding(result: EmbeddingResult, count: int) -> None:
        if result.model_version != E5_MODEL.model_version or result.dimension != 384:
            raise ModelContractError("embedding model space mismatch")
        validate_embedding_batch(
            [list(row) for row in result.vectors], count, 384, result.model_version
        )

    @staticmethod
    def _require_derived_integrity(row: RowMapping, chunk: EvidenceChunk) -> None:
        if (
            row["chunk_text"] != chunk.text
            or row["text_sha256"] != chunk.text_sha256
            or row["evidence_id"] != str(chunk.evidence_id)
            or row["revision_id"] != str(chunk.revision_id)
            or row["start_offset"] != chunk.start_offset
            or row["end_offset"] != chunk.end_offset
        ):
            raise RetrievalFailure("answer_index_integrity_unavailable")

    @staticmethod
    def require_current(
        session: Session,
        scope: AccessScope,
        event_id: UUID,
        epoch: int,
        citations: tuple[CitationProjection, ...],
        *,
        lock_epoch: bool = False,
    ) -> None:
        scope.requires(READ_PUBLIC)
        if current_public_epoch(session, lock=lock_epoch) != epoch:
            raise RetrievalFailure("answer_evidence_changed")
        rows = {
            row["evidence_id"]: row
            for row in session.execute(
                _event_evidence_query(event_id).where(
                    evidence.c.evidence_id.in_(
                        [str(citation.evidence_id) for citation in citations]
                    )
                )
            ).mappings()
        }
        for citation in citations:
            row = rows.get(str(citation.evidence_id))
            if (
                row is None
                or row["revision_id"] != str(citation.revision_id)
                or citation.quote not in row["quote"]
            ):
                raise RetrievalFailure("answer_evidence_changed")
            current = KnowledgeReadService(session, scope, "live").read_evidence(
                citation.evidence_id
            )
            if (
                current.verified_at is None
                or current.source_uri != citation.source_uri
                or citation.quote not in current.quote_text
            ):
                raise RetrievalFailure("answer_evidence_changed")
