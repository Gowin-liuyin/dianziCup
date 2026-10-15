"""Load visible current PG revisions and verified immutable objects for bounded enrichment."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from ai_intel.api.document_read_service import DocumentReadService, sources
from ai_intel.domain.access import AccessScope
from ai_intel.domain.enums import SourceCategory
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.contracts import EnrichmentBlock, EnrichmentContext, EnrichmentDocument
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES
from ai_intel.knowledge.event_linking import EventRepository
from ai_intel.knowledge.models import content_objects, document_revisions, documents, text_blocks
from ai_intel.knowledge.persistence_models import event_external_ids, events

MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_DOCUMENT_BYTES = 2 * 1024 * 1024
CVE_FIELD_BY_SOURCE_ID = {
    UUID(CATALOG_SOURCES["nvd_ollama"].source_id): "/cve/id",
    UUID(CATALOG_SOURCES["vllm_vendor"].source_id): "/cve_id",
}


class EnrichmentInputError(ValueError):
    """Missing, stale or corrupt inputs block enrichment rather than imply no risk."""


@dataclass(frozen=True)
class LoadedEnrichmentInputs:
    context: EnrichmentContext
    documents: tuple[EnrichmentDocument, ...]
    scope: VisibilityScope


def _require_input_scopes(
    session: Session,
    access_scope: AccessScope,
    scope: VisibilityScope,
    revision_ids: tuple[str, ...],
) -> None:
    """Validate every parent before IO; historical revisions retain the same ACL boundary."""
    query = (
        select(
            document_revisions.c.revision_id,
            document_revisions.c.visibility,
            document_revisions.c.tenant_id,
            documents.c.visibility.label("document_visibility"),
            documents.c.tenant_id.label("document_tenant_id"),
            sources.c.visibility.label("source_visibility"),
            sources.c.tenant_id.label("source_tenant_id"),
        )
        .join(documents, documents.c.document_id == document_revisions.c.document_id)
        .join(sources, sources.c.source_id == documents.c.source_id)
        .where(document_revisions.c.revision_id.in_(revision_ids))
    )
    if scope.visibility == "public":
        query = query.where(DocumentReadService._visible())
    rows = tuple(session.execute(query).mappings())
    if {row["revision_id"] for row in rows} != set(revision_ids):
        raise EnrichmentInputError("source_scope_exceeds_event")
    for row in rows:
        for prefix in ("", "document_", "source_"):
            source_scope = VisibilityScope(
                visibility=row[prefix + "visibility"], tenant_id=row[prefix + "tenant_id"]
            )
            access_scope.enforce_visible(source_scope.visibility, source_scope.tenant_id)
            if source_scope.visibility == "tenant" and source_scope != scope:
                raise EnrichmentInputError("source_scope_exceeds_event")


def _revision_blocks(
    session: Session, revision_id: str
) -> tuple[tuple[EnrichmentBlock, ...], bool]:
    rows = session.execute(
        select(text_blocks)
        .where(text_blocks.c.revision_id == revision_id)
        .order_by(text_blocks.c.ordinal)
        .limit(201)
    ).mappings()
    selected: list[EnrichmentBlock] = []
    complete = True
    characters = 0
    for row in rows:
        block_text = row["block_text"]
        if len(selected) == 200 or len(block_text) > 20000 or characters + len(block_text) > 200000:
            complete = False
            continue
        if row["end_offset"] - row["start_offset"] != len(block_text):
            raise EnrichmentInputError("saved_block_coordinates_invalid")
        selected.append(
            EnrichmentBlock(
                block_id=row["block_id"],
                start_offset=row["start_offset"],
                text=block_text,
                text_sha256=row["text_sha256"],
                json_pointer=row["json_pointer"],
                page_number=row["page_number"],
            )
        )
        characters += len(block_text)
    if not selected:
        raise EnrichmentInputError("source_blocks_unavailable")
    return tuple(selected), complete


def _load_document(
    session: Session, store: ContentStorage, scope: VisibilityScope, row: RowMapping
) -> EnrichmentDocument:
    if row["visibility"] == "tenant" and (
        scope.visibility != "tenant" or scope.tenant_id != row["tenant_id"]
    ):
        raise EnrichmentInputError("source_scope_exceeds_event")
    if not row["is_current"] or row["parse_status"] not in {"parsed", "partial"}:
        raise EnrichmentInputError("source_revision_not_current_parsed")
    if not row["canonical_uri"]:
        raise EnrichmentInputError("source_uri_unavailable")
    category = session.scalar(
        text("SELECT category FROM sources WHERE source_id=:id"), {"id": row["source_id"]}
    )
    blocks, complete = _revision_blocks(session, row["revision_id"])
    payload = store.read_verified(row["content_hash"])
    if (
        len(payload) != row["size_bytes"]
        or hashlib.sha256(payload).hexdigest() != row["content_hash"]
    ):
        raise EnrichmentInputError("source_object_integrity_invalid")
    metadata = row["source_metadata"]
    legacy_json_source = UUID(row["source_id"]) in CVE_FIELD_BY_SOURCE_ID
    coverage = metadata.get("content_coverage", "full_text" if legacy_json_source else "unknown")
    version = metadata.get("taxonomy_version") or metadata.get("version_label")
    if version is None:
        version = row["normalizer_version"]
    return EnrichmentDocument(
        revision_id=row["revision_id"],
        document_id=row["document_id"],
        source_id=row["source_id"],
        document_kind=row["kind"],
        source_category=SourceCategory(category),
        canonical_uri=row["canonical_uri"],
        source_record_id=str(row["canonical_uri"]).rsplit("/", 1)[-1],
        content_sha256=row["content_hash"],
        blocks=blocks,
        blocks_complete=complete and row["parse_status"] == "parsed",
        content_coverage=coverage,
        source_version=version,
        observed_at=row["first_observed_at"],
        json_payload=payload if any(block.json_pointer is not None for block in blocks) else None,
    )


def _explicit_cve_ids(
    session: Session, event_id: UUID, loaded: tuple[EnrichmentDocument, ...]
) -> tuple[str, ...]:
    identifiers: tuple[str, ...] = tuple(
        session.scalars(
            select(event_external_ids.c.id_value)
            .where(
                event_external_ids.c.event_id == str(event_id),
                event_external_ids.c.id_type == "cve",
            )
            .order_by(event_external_ids.c.id_value)
        )
    )
    for identifier in identifiers:
        supported = any(
            any(
                block.json_pointer == pointer and block.text == pointer + ": " + identifier
                for block in document.blocks
            )
            for document in loaded
            if (pointer := CVE_FIELD_BY_SOURCE_ID.get(document.source_id)) is not None
        )
        if not supported:
            raise EnrichmentInputError("event_identifier_unverified")
    return identifiers


def load_event_enrichment_inputs(
    session: Session,
    store: ContentStorage,
    access_scope: AccessScope,
    event_id: UUID,
    rule_version: str,
) -> LoadedEnrichmentInputs:
    """No model-supplied scope, URL or revision is accepted; IO follows PG visibility checks."""
    revision_ids = EventRepository(session, access_scope).get_source_revisions(str(event_id))
    event = (
        session.execute(select(events).where(events.c.event_id == str(event_id))).mappings().one()
    )
    if event["status"] != "active" or not 1 <= len(revision_ids) <= 20:
        raise EnrichmentInputError("active_bounded_event_revisions_required")
    scope = VisibilityScope(visibility=event["visibility"], tenant_id=event["tenant_id"])
    _require_input_scopes(session, access_scope, scope, revision_ids)
    rows = tuple(
        session.execute(
            select(
                document_revisions,
                documents.c.kind,
                documents.c.source_id,
                content_objects.c.size_bytes,
            )
            .join(documents, documents.c.document_id == document_revisions.c.document_id)
            .join(
                content_objects, content_objects.c.content_hash == document_revisions.c.content_hash
            )
            .where(document_revisions.c.revision_id.in_(revision_ids))
            .order_by(document_revisions.c.revision_id)
        ).mappings()
    )
    if (
        len(rows) != len(revision_ids)
        or any(row["size_bytes"] > MAX_DOCUMENT_BYTES for row in rows)
        or sum(row["size_bytes"] for row in rows) > MAX_INPUT_BYTES
    ):
        raise EnrichmentInputError("enrichment_input_byte_budget_exceeded")
    try:
        loaded = tuple(_load_document(session, store, scope, row) for row in rows)
        context = EnrichmentContext(
            event_id=event_id,
            expected_event_version=event["business_version"],
            revision_ids=tuple(UUID(revision_id) for revision_id in revision_ids),
            external_cve_ids=_explicit_cve_ids(session, event_id, loaded),
            rule_version=rule_version,
        )
    except (OSError, ValidationError, ValueError):
        raise EnrichmentInputError("enrichment_source_input_invalid") from None
    return LoadedEnrichmentInputs(context, loaded, scope)
