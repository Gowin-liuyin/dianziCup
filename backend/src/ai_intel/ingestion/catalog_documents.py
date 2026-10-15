"""非漏洞资料复用原文、修订和证据账本，不凭文档类型创建漏洞事件。"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from urllib.parse import urlsplit
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_intel.domain.access import MANAGE_PUBLIC_SOURCES, READ_PUBLIC, AccessScope, Role
from ai_intel.domain.enums import DocumentKind
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.ingestion.parsing.text_blocks import ParseOutcome
from ai_intel.ingestion.source_catalog import CATALOG_SOURCES, SourceCatalogError, SourceKind
from ai_intel.knowledge.models import document_revisions, documents, scope_epochs, text_blocks
from ai_intel.knowledge.persistence_models import claims
from ai_intel.knowledge.revisions import (
    add_text_block,
    attach_evidence_span,
    register_response_content,
    save_document_revision,
)


@dataclass(frozen=True)
class NormalizedSourceDocument:
    """来源解析的事实输入；metadata保留原始日期精度、许可与全文能力。"""

    source_record_id: str
    kind: DocumentKind
    title: str
    canonical_uri: str
    payload: bytes
    parsed: ParseOutcome
    published_at: datetime | None
    modified_at: datetime | None
    metadata: dict[str, JsonValue]
    source_locator: str | None = None


@dataclass(frozen=True)
class SavedCatalogDocuments:
    """父事务提交前的内部PG标识；事件/论断发布由各业务判断另行完成。"""

    revision_ids: tuple[str, ...]
    new_revision_count: int


def _utc(value: datetime) -> datetime:
    if value.utcoffset() is None:
        raise SourceCatalogError("source ingestion time must be timezone aware")
    return value.astimezone(UTC)


def _validate_document(source_kind: SourceKind, member: NormalizedSourceDocument) -> None:
    source_document_kinds = {
        "nvd_ollama": DocumentKind.ADVISORY,
        "vllm_vendor": DocumentKind.ADVISORY,
        "osv_ollama": DocumentKind.ADVISORY,
        "avid_community": DocumentKind.ARTICLE,
        "ollama_releases": DocumentKind.REPOSITORY_RECORD,
        "trailofbits_blog": DocumentKind.ARTICLE,
        "arxiv_security": DocumentKind.PAPER,
        "nist_ai_rmf": DocumentKind.STANDARD,
        "cac_generative_ai": DocumentKind.POLICY,
    }
    if member.kind != source_document_kinds[source_kind]:
        raise SourceCatalogError("document kind does not match fixed source category")
    if not 1 <= len(member.source_record_id) <= 512 or any(
        ord(char) < 32 for char in member.source_record_id
    ):
        raise SourceCatalogError("invalid stable source record identifier")
    if not 1 <= len(member.title) <= 500 or not member.title.strip() or "\x00" in member.title:
        raise SourceCatalogError("invalid source document title")
    origin = urlsplit(CATALOG_SOURCES[source_kind].base_origin)
    allowed_hosts = {origin.hostname}
    if source_kind in {"avid_community", "ollama_releases"}:
        allowed_hosts.add("github.com")
    if source_kind == "arxiv_security":
        allowed_hosts.add("arxiv.org")
    try:
        uri = urlsplit(member.canonical_uri)
        valid_uri = (
            uri.scheme == "https"
            and uri.hostname in allowed_hosts
            and uri.port in {None, 443}
            and uri.username is None
            and uri.password is None
            and not uri.fragment
        )
    except ValueError:
        raise SourceCatalogError("invalid source document URI") from None
    if (
        not valid_uri
        or not member.canonical_uri.isascii()
        or len(member.canonical_uri) > 4096
        or any(ord(char) <= 32 or ord(char) == 127 for char in member.canonical_uri)
    ):
        raise SourceCatalogError("source document URI outside fixed publisher")
    if not 1 <= len(member.payload) <= 5 * 1024 * 1024:
        raise SourceCatalogError("source document content exceeds limit")
    if (
        member.parsed.status not in {"parsed", "partial"}
        or not 1 <= len(member.parsed.blocks) <= 2000
    ):
        raise SourceCatalogError("source document lacks bounded parsed content")
    if len(member.parsed.normalized_text) > 4 * 1024 * 1024:
        raise SourceCatalogError("source text exceeds limit")
    offset = 0
    for ordinal, block in enumerate(member.parsed.blocks):
        if (
            block.ordinal != ordinal
            or block.start_offset != offset
            or block.end_offset != offset + len(block.text)
            or not block.text
            or "\x00" in block.text
        ):
            raise SourceCatalogError("source text coordinates are not consistent")
        offset = block.end_offset
    if member.parsed.normalized_text != "".join(block.text for block in member.parsed.blocks):
        raise SourceCatalogError("source normalized text differs from its blocks")
    metadata = json.dumps(_revision_metadata(member), ensure_ascii=False, allow_nan=False).encode(
        "utf-8"
    )
    if len(metadata) > 65536 or b"\\u0000" in metadata:
        raise SourceCatalogError("source metadata exceeds safe limit")
    for timestamp in (member.published_at, member.modified_at):
        if timestamp is not None:
            _utc(timestamp)


def _revision_metadata(member: NormalizedSourceDocument) -> dict[str, JsonValue]:
    return dict(
        member.metadata,
        title=member.title,
        canonical_uri=member.canonical_uri,
        published_at=_utc(member.published_at).isoformat() if member.published_at else None,
        modified_at=_utc(member.modified_at).isoformat() if member.modified_at else None,
        source_locator=member.source_locator,
        parse_status=member.parsed.status,
        parser_version=member.parsed.parser_version,
        normalizer_version=member.parsed.normalizer_version,
    )


def persist_catalog_documents(
    session: Session,
    store: ContentStorage,
    scope: AccessScope,
    source_kind: SourceKind,
    members: tuple[NormalizedSourceDocument, ...],
    *,
    response_hash: str,
    observed_at: datetime,
    ingested_at: datetime,
) -> SavedCatalogDocuments:
    """仅写同一公开源；整页savepoint与cursor/outbox由调用方事务共同提交。"""
    scope.requires(MANAGE_PUBLIC_SOURCES)
    scope.requires(READ_PUBLIC)
    if scope.role != Role.SYSTEM_ADMIN or scope.tenant_id is not None:
        raise SourceCatalogError("public source administrator required")
    observed_at, ingested_at = _utc(observed_at), _utc(ingested_at)
    if observed_at > ingested_at or source_kind not in CATALOG_SOURCES:
        raise SourceCatalogError("invalid source observation")
    if len(members) > 100 or len({member.source_record_id for member in members}) != len(members):
        raise SourceCatalogError("source page contains duplicate or too many documents")
    for member in members:
        _validate_document(source_kind, member)
    source_id = CATALOG_SOURCES[source_kind].source_id
    revisions: list[str] = []
    new_count = 0
    for member in members:
        document_id = str(
            uuid5(NAMESPACE_URL, f"dianzi:document:{source_id}:{member.source_record_id}")
        )
        session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(document_id, 0))))
        content = register_response_content(session, store, member.payload, ingested_at)
        session.execute(
            insert(documents)
            .values(
                document_id=document_id,
                source_id=source_id,
                kind=member.kind.value,
                title=member.title,
                published_at=member.published_at,
                retrieved_at=observed_at,
                content_hash=content.content_hash,
                visibility="public",
                tenant_id=None,
                schema_version=2,
            )
            .on_conflict_do_nothing(index_elements=[documents.c.document_id])
        )
        existing = (
            session.execute(
                select(documents).where(documents.c.document_id == document_id).with_for_update()
            )
            .mappings()
            .one()
        )
        if (
            existing["source_id"],
            existing["kind"],
            existing["visibility"],
            existing["tenant_id"],
        ) != (source_id, member.kind.value, "public", None):
            raise SourceCatalogError("source document identity or scope conflicts")
        saved = save_document_revision(
            session,
            store,
            document_id,
            member.payload,
            "public",
            None,
            ingested_at,
            revision_metadata=_revision_metadata(member),
        )
        revisions.append(saved.revision_id)
        if saved.reused:
            continue
        new_count += 1
        prior_revisions = select(document_revisions.c.revision_id).where(
            document_revisions.c.document_id == document_id,
            document_revisions.c.revision_id != saved.revision_id,
        )
        session.execute(
            update(claims)
            .where(claims.c.source_revision_id.in_(prior_revisions))
            .values(is_current=False)
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == saved.revision_id)
            .values(
                canonical_uri=member.canonical_uri,
                source_published_at=member.published_at,
                source_modified_at=member.modified_at,
                first_observed_at=observed_at,
                ingested_at=ingested_at,
                parser_version=member.parsed.parser_version,
                normalizer_version=member.parsed.normalizer_version,
                parse_status=member.parsed.status,
                source_response_hash=response_hash,
                source_json_pointer=member.source_locator,
                source_metadata=_revision_metadata(member),
            )
        )
        for block in member.parsed.blocks:
            block_id = add_text_block(
                session,
                saved.revision_id,
                block.ordinal,
                block.start_offset,
                block.end_offset,
                block.text,
            )
            pointer = (
                block.block_type.removeprefix("field:")
                if block.block_type.startswith("field:")
                else None
            )
            session.execute(
                update(text_blocks)
                .where(text_blocks.c.block_id == block_id)
                .values(
                    block_type="json_field" if pointer is not None else block.block_type,
                    page_number=block.page_number,
                    json_pointer=pointer,
                )
            )
            attach_evidence_span(
                session,
                saved.revision_id,
                block.start_offset,
                block.end_offset,
                f"page:{block.page_number}"
                if block.page_number is not None
                else (pointer or f"block:{block.ordinal}"),
                block.text,
                False,
                "public",
                None,
                ingested_at,
                block_id=block_id,
                verified_at=ingested_at,
            )
    if new_count:
        session.execute(
            insert(scope_epochs)
            .values(scope_key="public", epoch=1, updated_at=ingested_at)
            .on_conflict_do_update(
                index_elements=[scope_epochs.c.scope_key],
                set_={"epoch": scope_epochs.c.epoch + 1, "updated_at": ingested_at},
            )
        )
    return SavedCatalogDocuments(tuple(revisions), new_count)
