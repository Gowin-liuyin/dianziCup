"""ACL-filtered corpus BM25/vector/RRF retrieval, with PG checks before and after rerank."""

from __future__ import annotations

import hashlib
import math
import re
import time
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import Select, and_, exists, func, or_, select, tuple_
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.sql.selectable import FromClause

from ai_intel.api.knowledge_read_service import KnowledgeReadService, sources
from ai_intel.domain.access import READ_ASSET, READ_PUBLIC, AccessScope
from ai_intel.infrastructure.models.clients import ModelContractError
from ai_intel.infrastructure.models.semantic import E5_MODEL, RERANK_MODEL
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    scope_epochs,
    text_blocks,
)
from ai_intel.knowledge.persistence_models import (
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.retrieval.hybrid_contracts import (
    CorpusCandidate,
    GraphCandidates,
    HybridQuery,
    HybridRetrievalError,
    HybridSelection,
    IndexGeneration,
    RetrievalHit,
    RetrievalTrace,
)
from ai_intel.retrieval.hybrid_schema import (
    hybrid_chunks,
    hybrid_index_generations,
    hybrid_index_watermarks,
)
from ai_intel.retrieval.service import EventEvidenceRetriever, SemanticModels, split_evidence_quote

RRF_K = 60
BRANCH_LIMIT = 32
RERANK_LIMIT = 8
EXACT_ID = re.compile(r"(?<![A-Za-z0-9-])CVE-\d{4}-\d{4,}(?![A-Za-z0-9-])", re.IGNORECASE)


class CorpusBM25(Protocol):
    def search(
        self, generation: IndexGeneration, scope: AccessScope, query: HybridQuery
    ) -> tuple[str, ...]: ...


def authorized_scope_keys(scope: AccessScope) -> tuple[str, ...]:
    scope.requires(READ_PUBLIC)
    if scope.tenant_id is not None and READ_ASSET in scope.permissions:
        return ("public", "tenant:" + scope.tenant_id)
    return ("public",)


def visible_clause(scope: AccessScope, relation: FromClause) -> ColumnElement[bool]:
    public = and_(relation.c.visibility == "public", relation.c.tenant_id.is_(None))
    if scope.tenant_id is None or READ_ASSET not in scope.permissions:
        return public
    return or_(
        public, and_(relation.c.visibility == "tenant", relation.c.tenant_id == scope.tenant_id)
    )


def read_scope_epochs(
    session: Session, scope: AccessScope, *, lock: bool = False
) -> dict[str, int]:
    keys = authorized_scope_keys(scope)
    query = (
        select(scope_epochs)
        .where(scope_epochs.c.scope_key.in_(keys))
        .order_by(scope_epochs.c.scope_key)
    )
    if lock:
        query = query.with_for_update(read=True)
    rows = {row.scope_key: row.epoch for row in session.execute(query)}
    return {key: int(rows.get(key, 0)) for key in keys}


def reciprocal_rank_fusion(branches: tuple[tuple[str, ...], ...]) -> tuple[tuple[str, float], ...]:
    scores: dict[str, float] = {}
    for branch in branches:
        for position, chunk_id in enumerate(dict.fromkeys(branch), start=1):
            scores[chunk_id] = scores.get(chunk_id, 0.0) + 1.0 / (RRF_K + position)
    return tuple(sorted(scores.items(), key=lambda item: (-item[1], item[0])))


def facts_query(scope: AccessScope, query: HybridQuery) -> Select[tuple[object, ...]]:
    """Every joined authority has its own ACL check; this is current truth with time bounds."""
    withdrawal = claims.alias("source_withdrawal")
    withdrawn = exists(
        select(withdrawal.c.claim_id).where(
            withdrawal.c.source_revision_id == document_revisions.c.revision_id,
            withdrawal.c.is_current.is_(True),
            withdrawal.c.claim_status == "supported",
            visible_clause(scope, withdrawal),
            or_(
                withdrawal.c.predicate == "source_withdrawn_at",
                and_(
                    withdrawal.c.predicate == "source_status",
                    func.lower(withdrawal.c.object_value).in_(("withdrawn", "rejected")),
                ),
            ),
        )
    )
    available = func.greatest(
        evidence.c.created_at,
        document_revisions.c.created_at,
        documents.c.retrieved_at,
        claims.c.created_at,
        claims.c.asserted_at,
        events.c.first_seen_at,
        event_documents.c.associated_at,
    )
    relations = (events, evidence, document_revisions, documents, sources, claims)
    fields = [
        evidence.c.evidence_id,
        document_revisions.c.revision_id,
        documents.c.document_id,
        documents.c.source_id,
        events.c.event_id,
        claims.c.claim_id,
        evidence.c.quote,
        evidence.c.locator,
        available.label("available_at"),
    ]
    for relation in relations:
        fields.extend(
            (
                relation.c.visibility.label(relation.name + "_visibility"),
                relation.c.tenant_id.label(relation.name + "_tenant"),
            )
        )
    result = (
        select(*fields)
        .select_from(
            evidence.join(document_revisions)
            .join(documents)
            .join(sources, sources.c.source_id == documents.c.source_id)
            .join(
                event_documents, event_documents.c.revision_id == document_revisions.c.revision_id
            )
            .join(events, events.c.event_id == event_documents.c.event_id)
            .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
            .join(claims, claims.c.claim_id == claim_evidence.c.claim_id)
        )
        .where(
            *(visible_clause(scope, relation) for relation in relations),
            events.c.status == "active",
            event_documents.c.active.is_(True),
            document_revisions.c.is_current.is_(True),
            document_revisions.c.parse_status.in_(("parsed", "partial")),
            documents.c.kind != "asset_inventory",
            claims.c.source_revision_id == document_revisions.c.revision_id,
            claims.c.is_current.is_(True),
            claims.c.claim_status == "supported",
            claims.c.freshness == "current",
            claim_evidence.c.validation_status == "validated",
            claim_evidence.c.support_kind == "supports",
            evidence.c.supports_claim.is_(True),
            ~withdrawn,
            available <= query.available_before,
        )
        .order_by(evidence.c.evidence_id, events.c.event_id, claims.c.claim_id)
    )
    if query.available_after is not None:
        result = result.where(available >= query.available_after)
    return result


def candidates_from_rows(
    session: Session, scope: AccessScope, rows: list[RowMapping]
) -> tuple[CorpusCandidate, ...]:
    candidates: list[CorpusCandidate] = []
    reader = KnowledgeReadService(session, scope, "live")
    for row in rows:
        projection = reader.read_evidence(UUID(row["evidence_id"]))
        if projection.verified_at is None or projection.source_uri is None:
            raise HybridRetrievalError("corpus_evidence_integrity_unavailable")
        private = any(
            row[relation.name + "_visibility"] == "tenant"
            for relation in (events, evidence, document_revisions, documents, sources, claims)
        )
        tenant_id = scope.tenant_id if private else None
        scope_key = "tenant:" + str(tenant_id) if private else "public"
        for chunk in split_evidence_quote(
            projection.span_id, projection.revision_id, projection.quote_text
        ):
            chunk_id = str(
                uuid5(NAMESPACE_URL, f"{row['event_id']}:{row['claim_id']}:{chunk.chunk_id}")
            )
            candidates.append(
                CorpusCandidate(
                    chunk_id,
                    str(projection.span_id),
                    str(projection.revision_id),
                    row["document_id"],
                    row["source_id"],
                    row["event_id"],
                    row["claim_id"],
                    scope_key,
                    "tenant" if private else "public",
                    tenant_id,
                    row["available_at"],
                    chunk.start_offset,
                    chunk.end_offset,
                    chunk.text,
                    chunk.text_sha256,
                    str(projection.source_uri),
                    row["locator"],
                )
            )
    return tuple(candidates)


def require_generation(session: Session, generation: IndexGeneration) -> None:
    generation.require_fixed_space()
    row = (
        session.execute(
            select(hybrid_index_generations).where(
                hybrid_index_generations.c.generation_id == generation.generation_id
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["state"] != "ready":
        raise HybridRetrievalError("corpus_index_not_ready")
    if (row["index_name"], row["model_version"], row["dimension"]) != (
        generation.index_name,
        generation.model_version,
        generation.dimension,
    ):
        raise HybridRetrievalError("index_space_rebuild_required")


def candidate_values(candidate: CorpusCandidate) -> dict[str, object]:
    return {
        "chunk_id": candidate.chunk_id,
        "evidence_id": candidate.evidence_id,
        "revision_id": candidate.revision_id,
        "document_id": candidate.document_id,
        "source_id": candidate.source_id,
        "event_id": candidate.event_id,
        "claim_id": candidate.claim_id,
        "scope_key": candidate.scope_key,
        "visibility": candidate.visibility,
        "tenant_id": candidate.tenant_id,
        "available_at": candidate.available_at,
        "start_offset": candidate.start_offset,
        "end_offset": candidate.end_offset,
        "chunk_text": candidate.text,
        "text_sha256": candidate.text_sha256,
        "source_uri": candidate.source_uri,
        "locator": candidate.locator,
    }


def lock_candidate_authorities(
    session: Session, scope: AccessScope, candidates: tuple[CorpusCandidate, ...]
) -> None:
    """Lock only previously visible input identities; a complete fresh fact read must follow."""
    for relation, identifier, values in (
        (sources, sources.c.source_id, {item.source_id for item in candidates}),
        (documents, documents.c.document_id, {item.document_id for item in candidates}),
        (
            document_revisions,
            document_revisions.c.revision_id,
            {item.revision_id for item in candidates},
        ),
        (events, events.c.event_id, {item.event_id for item in candidates}),
        (claims, claims.c.claim_id, {item.claim_id for item in candidates}),
        (evidence, evidence.c.evidence_id, {item.evidence_id for item in candidates}),
    ):
        session.execute(
            select(identifier)
            .where(identifier.in_(values), visible_clause(scope, relation))
            .order_by(identifier)
            .with_for_update(read=True)
        ).all()
    session.execute(
        select(text_blocks.c.block_id)
        .where(
            text_blocks.c.block_id.in_(
                select(evidence.c.block_id).where(
                    evidence.c.evidence_id.in_({item.evidence_id for item in candidates}),
                    visible_clause(scope, evidence),
                )
            )
        )
        .order_by(text_blocks.c.block_id)
        .with_for_update(read=True)
    ).all()
    session.execute(
        select(event_documents.c.event_id, event_documents.c.revision_id)
        .where(
            tuple_(event_documents.c.event_id, event_documents.c.revision_id).in_(
                {(item.event_id, item.revision_id) for item in candidates}
            )
        )
        .order_by(event_documents.c.event_id, event_documents.c.revision_id)
        .with_for_update(read=True)
    ).all()
    session.execute(
        select(claim_evidence.c.claim_id, claim_evidence.c.evidence_id)
        .where(
            tuple_(claim_evidence.c.claim_id, claim_evidence.c.evidence_id).in_(
                {(item.claim_id, item.evidence_id) for item in candidates}
            )
        )
        .order_by(claim_evidence.c.claim_id, claim_evidence.c.evidence_id)
        .with_for_update(read=True)
    ).all()


def current_hit_candidates(
    session: Session, scope: AccessScope, query: HybridQuery, hits: tuple[RetrievalHit, ...]
) -> dict[str, CorpusCandidate]:
    rows = list(
        session.execute(
            facts_query(scope, query).where(
                evidence.c.evidence_id.in_({hit.candidate.evidence_id for hit in hits})
            )
        ).mappings()
    )
    return {item.chunk_id: item for item in candidates_from_rows(session, scope, rows)}


class HybridRetriever:
    def __init__(
        self,
        engine: Engine,
        models: SemanticModels,
        bm25: CorpusBM25,
        generation: IndexGeneration,
        graph: GraphCandidates | None = None,
    ) -> None:
        generation.require_fixed_space()
        self.engine, self.models, self.bm25 = engine, models, bm25
        self.generation, self.graph = generation, graph

    def retrieve(self, scope: AccessScope, query: HybridQuery) -> HybridSelection:
        authorized_scope_keys(scope)
        start = time.perf_counter()
        reasons: list[str] = []
        with Session(self.engine) as session:
            require_generation(session, self.generation)
            epochs = read_scope_epochs(session, scope)
            watermarks: dict[str, int] = dict(
                session.execute(
                    select(
                        hybrid_index_watermarks.c.scope_key, hybrid_index_watermarks.c.indexed_epoch
                    ).where(
                        hybrid_index_watermarks.c.generation_id == self.generation.generation_id,
                        hybrid_index_watermarks.c.scope_key.in_(epochs),
                    )
                ).all()
            )
            if any(watermarks.get(key) != value for key, value in epochs.items()):
                reasons.append("index_lag")
            exact_start = time.perf_counter()
            identifiers = tuple(
                dict.fromkeys(item.upper() for item in EXACT_ID.findall(query.text))
            )
            exact_events = (
                select(event_external_ids.c.event_id)
                .where(
                    event_external_ids.c.id_type == "cve",
                    event_external_ids.c.event_id == events.c.event_id,
                    event_external_ids.c.id_value.in_(identifiers),
                    event_external_ids.c.scope_key == events.c.scope_key,
                )
                .correlate(events)
            )
            exact_rows = (
                list(
                    session.execute(
                        facts_query(scope, query)
                        .where(exists(exact_events))
                        .limit(BRANCH_LIMIT + 1)
                    ).mappings()
                )
                if identifiers
                else []
            )
            if len(exact_rows) > BRANCH_LIMIT:
                reasons.append("exact_candidates_truncated")
            exact = candidates_from_rows(session, scope, exact_rows[:BRANCH_LIMIT])
            if len(exact) > BRANCH_LIMIT:
                reasons.append("exact_candidates_truncated")
            exact = exact[:BRANCH_LIMIT]
            exact_seconds = time.perf_counter() - exact_start
        bm25_start = time.perf_counter()
        try:
            bm25_ids = self.bm25.search(self.generation, scope, query)
        except HybridRetrievalError as failure:
            bm25_ids = ()
            reasons.append(
                {
                    "opensearch_permission_denied": "bm25_permission_denied",
                    "opensearch_timeout": "bm25_timeout",
                }.get(str(failure), "bm25_unavailable")
            )
        bm25_seconds = time.perf_counter() - bm25_start
        vector_start = time.perf_counter()
        embedded = self.models.embed_query(query.text)
        EventEvidenceRetriever._embedding(embedded, 1)
        with Session(self.engine) as session:
            distance = hybrid_chunks.c.embedding.cosine_distance(list(embedded.vectors[0]))
            condition = [
                hybrid_chunks.c.generation_id == self.generation.generation_id,
                hybrid_chunks.c.model_version == E5_MODEL.model_version,
                hybrid_chunks.c.scope_key.in_(epochs),
                visible_clause(scope, hybrid_chunks),
                hybrid_chunks.c.available_at <= query.available_before,
            ]
            if query.available_after is not None:
                condition.append(hybrid_chunks.c.available_at >= query.available_after)
            vector_ids: tuple[str, ...] = tuple(
                session.scalars(
                    select(hybrid_chunks.c.chunk_id)
                    .where(*condition)
                    .order_by(distance, hybrid_chunks.c.chunk_id)
                    .limit(BRANCH_LIMIT)
                )
            )
        vector_seconds = time.perf_counter() - vector_start
        graph_ids: tuple[str, ...] = ()
        graph_status: Literal["not_configured", "available", "not_requested"] = "not_requested"
        if query.include_graph:
            graph_status = "not_configured" if self.graph is None else "available"
            if self.graph is None:
                reasons.append("graph_not_configured")
            else:
                graph_ids = self.graph.retrieve(scope, query)[:BRANCH_LIMIT]
        fusion = reciprocal_rank_fusion((bm25_ids, vector_ids, graph_ids))
        scores = dict(fusion)
        exact_ids = {item.chunk_id for item in exact}
        ordered = tuple(
            dict.fromkeys((*(item.chunk_id for item in exact), *(key for key, _ in fusion)))
        )
        validation_start = time.perf_counter()
        with Session(self.engine) as session:
            projections = list(
                session.execute(
                    select(hybrid_chunks).where(
                        hybrid_chunks.c.generation_id == self.generation.generation_id,
                        hybrid_chunks.c.chunk_id.in_(ordered),
                        visible_clause(scope, hybrid_chunks),
                        hybrid_chunks.c.scope_key.in_(epochs),
                    )
                ).mappings()
            )
            evidence_ids = {row["evidence_id"] for row in projections} | {
                item.evidence_id for item in exact
            }
            current = {
                item.chunk_id: item
                for item in candidates_from_rows(
                    session,
                    scope,
                    list(
                        session.execute(
                            facts_query(scope, query).where(
                                evidence.c.evidence_id.in_(evidence_ids)
                            )
                        ).mappings()
                    ),
                )
            }
            projected = {row["chunk_id"]: row for row in projections}
            validated: list[CorpusCandidate] = []
            for chunk_id in ordered:
                candidate = current.get(chunk_id)
                row = projected.get(chunk_id)
                if candidate is None:
                    reasons.append("stale_candidates_filtered")
                    continue
                if chunk_id not in exact_ids and (
                    row is None
                    or any(row[key] != value for key, value in candidate_values(candidate).items())
                ):
                    reasons.append("index_projection_changed")
                    continue
                if hashlib.sha256(candidate.text.encode()).hexdigest() != candidate.text_sha256:
                    raise HybridRetrievalError("corpus_index_integrity_unavailable")
                validated.append(candidate)
        validation_seconds = time.perf_counter() - validation_start
        selected = validated[:RERANK_LIMIT]
        rerank_start = time.perf_counter()
        hits: tuple[RetrievalHit, ...] = ()
        if selected:
            reranked = self.models.rerank(query.text, tuple(item.text for item in selected))
            if (
                reranked.model_version != RERANK_MODEL.model_version
                or any(
                    type(item.index) is not int or not math.isfinite(item.score)
                    for item in reranked.items
                )
                or sorted(item.index for item in reranked.items) != list(range(len(selected)))
            ):
                raise ModelContractError("reranker space or indices do not match corpus candidates")
            hits = tuple(
                sorted(
                    (
                        RetrievalHit(
                            selected[item.index],
                            item.score,
                            scores.get(selected[item.index].chunk_id, 0.0),
                            selected[item.index].chunk_id in exact_ids,
                        )
                        for item in reranked.items
                    ),
                    key=lambda hit: (
                        not hit.exact_identifier,
                        -hit.rerank_score,
                        -hit.rrf_score,
                        hit.candidate.chunk_id,
                    ),
                )
            )
        rerank_seconds = time.perf_counter() - rerank_start
        with Session(self.engine) as session, session.begin():
            session.connection(execution_options={"isolation_level": "READ COMMITTED"})
            observed_epochs = read_scope_epochs(session, scope)
            observed_candidates = current_hit_candidates(session, scope, query, hits)
            lock_candidate_authorities(session, scope, tuple(hit.candidate for hit in hits))
            final = current_hit_candidates(session, scope, query, hits)
            final_epochs = read_scope_epochs(session, scope, lock=True)
            checked = tuple(
                hit for hit in hits if final.get(hit.candidate.chunk_id) == hit.candidate
            )
            if len(checked) != len(hits) or final != observed_candidates:
                reasons.append("facts_changed_during_rerank")
            hits = checked
            if final_epochs != epochs or final_epochs != observed_epochs:
                reasons.append("scope_changed_during_retrieval")
                hits = ()
            if not hits:
                reasons.append("no_supported_evidence")
            return HybridSelection(
                hits,
                bool(reasons),
                tuple(dict.fromkeys(reasons)),
                tuple(sorted(final_epochs.items())),
                tuple((key, watermarks.get(key)) for key in epochs),
                E5_MODEL.model_version,
                RERANK_MODEL.model_version,
                graph_status,
                RetrievalTrace(
                    len(exact),
                    len(bm25_ids),
                    len(vector_ids),
                    len(graph_ids),
                    len(validated),
                    len(selected),
                    exact_seconds,
                    bm25_seconds,
                    vector_seconds,
                    validation_seconds,
                    rerank_seconds,
                    time.perf_counter() - start,
                ),
            )
