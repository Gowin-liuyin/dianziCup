"""Synthetic public facts and explicit fixture models; nothing here is a live source claim."""

import hashlib
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine

from ai_intel.infrastructure.models.clients import EmbeddingResult
from ai_intel.infrastructure.models.semantic import (
    E5_MODEL,
    RERANK_MODEL,
    RankedPassage,
    RerankResult,
)
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    evidence,
    job_runs,
    outbox_events,
    scope_epochs,
    text_blocks,
)
from ai_intel.knowledge.persistence_models import (
    change_events,
    claim_evidence,
    claims,
    event_documents,
    event_external_ids,
    events,
)
from ai_intel.retrieval.hybrid_contracts import IndexChange

NOW = datetime(2026, 10, 15, 5, 0, tzinfo=UTC)


class FixtureSemanticModels:
    """One explicit synthetic vector space exercises SQL, never semantic recall quality."""

    def embed_query(self, query: str) -> EmbeddingResult:
        return self.embed_passages((query,))

    def embed_passages(self, passages: tuple[str, ...]) -> EmbeddingResult:
        return EmbeddingResult(
            tuple((1.0,) + (0.0,) * 383 for _ in passages), E5_MODEL.model_version, 384
        )

    def rerank(self, query: str, passages: tuple[str, ...]) -> RerankResult:
        return RerankResult(
            tuple(RankedPassage(index, float(index)) for index in reversed(range(len(passages)))),
            RERANK_MODEL.model_version,
        )


def seed_fact(
    engine: Engine,
    body: str,
    *,
    tenant: str | None = None,
    cve: str | None = None,
    available_at: datetime = NOW,
) -> dict[str, str]:
    identifiers = {
        name: str(uuid4())
        for name in (
            "source_id",
            "document_id",
            "revision_id",
            "block_id",
            "evidence_id",
            "event_id",
            "claim_id",
        )
    }
    visibility = "public" if tenant is None else "tenant"
    scope = "public" if tenant is None else "tenant:" + tenant
    digest = hashlib.sha256(body.encode()).hexdigest()
    archive = os.environ.get("R12_EVIDENCE_DIR")
    if archive is not None:
        root = Path(archive)
        root.mkdir(parents=True, exist_ok=True)
        (root / f"{digest}.txt").write_bytes(body.encode())
        with (root / "raw_manifest.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(
                json.dumps(
                    {
                        "sha256": digest,
                        "size_bytes": len(body.encode()),
                        "data_mode": "synthetic",
                        "source_uri": "https://example.invalid/r12",
                    }
                )
                + "\n"
            )
    with engine.begin() as connection:
        connection.execute(
            insert(content_objects)
            .values(content_hash=digest, size_bytes=len(body.encode()), created_at=available_at)
            .on_conflict_do_nothing()
        )
        connection.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,visibility,tenant_id,"
                "created_at) "
                "VALUES(:id,:id,'vendor_advisory','https://example.invalid',:v,:t,:now)"
            ),
            {"id": identifiers["source_id"], "v": visibility, "t": tenant, "now": available_at},
        )
        connection.execute(
            documents.insert().values(
                document_id=identifiers["document_id"],
                source_id=identifiers["source_id"],
                kind="advisory",
                title="R12 synthetic document",
                published_at=None,
                retrieved_at=available_at,
                content_hash=digest,
                visibility=visibility,
                tenant_id=tenant,
                schema_version=2,
            )
        )
        connection.execute(
            document_revisions.insert().values(
                revision_id=identifiers["revision_id"],
                document_id=identifiers["document_id"],
                revision_number=1,
                content_hash=digest,
                created_at=available_at,
                is_current=True,
                visibility=visibility,
                tenant_id=tenant,
                canonical_uri="https://example.invalid/r12",
                first_observed_at=available_at,
                ingested_at=available_at,
                parse_status="parsed",
            )
        )
        connection.execute(
            text_blocks.insert().values(
                block_id=identifiers["block_id"],
                revision_id=identifiers["revision_id"],
                ordinal=1,
                start_offset=0,
                end_offset=len(body),
                block_text=body,
                text_sha256=digest,
                block_type="paragraph",
            )
        )
        connection.execute(
            evidence.insert().values(
                evidence_id=identifiers["evidence_id"],
                revision_id=identifiers["revision_id"],
                start_offset=0,
                end_offset=len(body),
                locator="synthetic paragraph 1",
                quote=body,
                supports_claim=True,
                visibility=visibility,
                tenant_id=tenant,
                created_at=available_at,
                block_id=identifiers["block_id"],
                quote_sha256=digest,
                verified_at=available_at,
                coordinate_version="fulltext_unicode_v1",
            )
        )
        connection.execute(
            events.insert().values(
                event_id=identifiers["event_id"],
                event_type="vulnerability",
                title="R12 synthetic event",
                scope_key=scope,
                visibility=visibility,
                tenant_id=tenant,
                status="active",
                first_seen_at=available_at,
                business_version=1,
            )
        )
        connection.execute(
            event_documents.insert().values(
                event_id=identifiers["event_id"],
                revision_id=identifiers["revision_id"],
                active=True,
                associated_at=available_at,
            )
        )
        if cve is not None:
            connection.execute(
                event_external_ids.insert().values(
                    event_id=identifiers["event_id"],
                    id_type="cve",
                    id_value=cve,
                    scope_key=scope,
                )
            )
        connection.execute(
            claims.insert().values(
                claim_id=identifiers["claim_id"],
                subject="synthetic component",
                predicate="affected_product",
                object_value="synthetic",
                claim_status="supported",
                claim_origin="source_explicit",
                condition_value="true",
                freshness="current",
                asserted_at=available_at,
                visibility=visibility,
                tenant_id=tenant,
                created_at=available_at,
                schema_version=2,
                provenance_status="source_verified",
                is_current=True,
                source_revision_id=identifiers["revision_id"],
            )
        )
        connection.execute(
            claim_evidence.insert().values(
                claim_id=identifiers["claim_id"],
                evidence_id=identifiers["evidence_id"],
                support_kind="supports",
                validation_status="validated",
            )
        )
    return identifiers


def record_change(engine: Engine, scope: str = "public") -> IndexChange:
    change_id, job_id, outbox_id = (str(uuid4()) for _ in range(3))
    now = datetime.now(UTC)
    with engine.begin() as connection:
        epoch = connection.scalar(
            insert(scope_epochs)
            .values(
                scope_key=scope,
                epoch=1,
                updated_at=now,
            )
            .on_conflict_do_update(
                index_elements=["scope_key"],
                set_={
                    "epoch": scope_epochs.c.epoch + 1,
                    "updated_at": now,
                },
            )
            .returning(scope_epochs.c.epoch)
        )
        connection.execute(
            change_events.insert().values(
                change_id=change_id,
                scope_key=scope,
                epoch=epoch,
                change_type="r12_synthetic_change",
                entity_ids=[],
                payload={"data_mode": "synthetic"},
                created_at=now,
            )
        )
        connection.execute(
            job_runs.insert().values(
                job_id=job_id,
                tenant_id=None if scope == "public" else scope[7:],
                job_type="knowledge_change",
                status="queued",
                payload_ref="pg:change:" + change_id,
                created_at=now,
                updated_at=now,
                attempt_count=0,
                max_attempts=5,
            )
        )
        connection.execute(
            outbox_events.insert().values(
                event_id=outbox_id,
                job_id=job_id,
                topic="job.knowledge_change",
                payload_ref="pg:change:" + change_id,
                created_at=now,
            )
        )
    return IndexChange(outbox_id, scope)
