"""不可变文档修订与证据关联: 修订链语义、租户范围、引文一致性与抓取记录。"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass
from datetime import datetime

from pydantic import JsonValue
from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ai_intel.infrastructure.content_store import ContentStorage, StoredContent
from ai_intel.knowledge.models import (
    content_objects,
    document_revisions,
    documents,
    evidence,
    fetch_attempts,
    scope_epochs,
    text_blocks,
)


class TenantScopeViolation(ValueError):
    """跨租户或租户字段矛盾: 拒绝持久化, 不静默改写归属。"""


class MissingRevisionError(LookupError):
    """修订不存在: 调用方不得假设旧读缓存仍然有效。"""


class MissingDocumentError(LookupError):
    """文档不存在: 修订不得脱离文档父行持久化。"""


class QuoteConsistencyError(ValueError):
    """引文与原文块不一致: 引文存在不等于内容支持, 校验失败必须拒绝。"""


@dataclass(frozen=True)
class SavedRevision:
    """保存结果: reused=True 表示重复末版复用, 未新增修订。"""

    revision_id: str
    revision_number: int
    content_hash: str
    reused: bool


def _insert_content_object(
    session: Session, content_hash: str, size_bytes: int, created_at: datetime
) -> None:
    """登记原文对象; 重复登记幂等。"""
    session.execute(
        insert(content_objects)
        .values(content_hash=content_hash, size_bytes=size_bytes, created_at=created_at)
        .on_conflict_do_nothing(index_elements=[content_objects.c.content_hash])
    )


def _lock_content_hash(session: Session, content_hash: str) -> None:
    """发布与回收共享事务锁, 避免回收尚未提交引用的对象。"""
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(content_hash, 0))))


def _load_document_row(session: Session, document_id: str) -> dict[str, object]:
    """读取文档父行; 不存在即拒绝, 保证修订不脱离文档。"""
    row = (
        session.execute(
            select(documents).where(documents.c.document_id == document_id).with_for_update()
        )
        .mappings()
        .first()
    )
    if row is None:
        raise MissingDocumentError(document_id)
    return dict(row)


def register_response_content(
    session: Session, store: ContentStorage, payload: bytes, created_at: datetime
) -> StoredContent:
    """来源响应与GC共享hash锁；调用方保持同事务直到所有PG引用完成。"""
    if type(payload) is not bytes or created_at.tzinfo is None:
        raise ValueError("response requires bytes and an aware timestamp")
    content_hash = hashlib.sha256(payload).hexdigest()
    _lock_content_hash(session, content_hash)
    stored = store.store_bytes(payload)
    if stored.content_hash != content_hash or stored.size_bytes != len(payload):
        raise ValueError("stored response does not match its payload")
    if store.read_verified(content_hash) != payload:
        raise ValueError("stored response bytes failed verification")
    _insert_content_object(session, stored.content_hash, stored.size_bytes, created_at)
    return stored


def save_document_revision(
    session: Session,
    store: ContentStorage,
    document_id: str,
    payload: bytes,
    visibility: str,
    tenant_id: str | None,
    created_at: datetime,
    *,
    revision_metadata: dict[str, JsonValue] | None = None,
) -> SavedRevision:
    """同内容及显式元数据才复用；旧调用不提供metadata时保留原有语义。"""
    if revision_metadata is not None:
        try:
            encoded_metadata = json.dumps(
                revision_metadata, ensure_ascii=False, allow_nan=False
            ).encode("utf-8")
        except (TypeError, ValueError, UnicodeError, RecursionError):
            raise ValueError("invalid document revision metadata") from None
        if (
            not isinstance(revision_metadata, dict)
            or len(encoded_metadata) > 65536
            or b"\\u0000" in encoded_metadata
        ):
            raise ValueError("document revision metadata exceeds bounded object")
    document_row = _load_document_row(session, document_id)
    if (visibility == "tenant") != (tenant_id is not None):
        raise TenantScopeViolation("tenant revision requires exactly one tenant_id")
    if visibility != document_row["visibility"] or tenant_id != document_row["tenant_id"]:
        raise TenantScopeViolation("revision scope does not match document scope")
    content_hash = hashlib.sha256(payload).hexdigest()
    _lock_content_hash(session, content_hash)
    stored = store.store_bytes(payload)
    _insert_content_object(session, stored.content_hash, stored.size_bytes, created_at)
    tip_query = select(
        document_revisions.c.revision_id,
        document_revisions.c.revision_number,
        document_revisions.c.content_hash,
    )
    if revision_metadata is not None:
        tip_query = tip_query.add_columns(document_revisions.c.source_metadata)
    tip = (
        session.execute(
            tip_query.where(
                document_revisions.c.document_id == document_id,
                document_revisions.c.is_current.is_(True),
            ).limit(1)
        )
        .mappings()
        .first()
    )
    if (
        tip is not None
        and tip["content_hash"] == stored.content_hash
        and (revision_metadata is None or tip["source_metadata"] == revision_metadata)
    ):
        return SavedRevision(
            revision_id=str(tip["revision_id"]),
            revision_number=int(tip["revision_number"]),
            content_hash=stored.content_hash,
            reused=True,
        )
    next_number = (
        session.execute(
            select(func.coalesce(func.max(document_revisions.c.revision_number), 0)).where(
                document_revisions.c.document_id == document_id
            )
        ).scalar_one()
        + 1
    )
    revision_id = str(uuid.uuid4())
    if tip is not None:
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == tip["revision_id"])
            .values(is_current=False)
        )
    revision_insert = document_revisions.insert().values(
        revision_id=revision_id,
        document_id=document_id,
        revision_number=next_number,
        content_hash=stored.content_hash,
        created_at=created_at,
        is_current=True,
        previous_revision_id=str(tip["revision_id"]) if tip is not None else None,
        visibility=visibility,
        tenant_id=tenant_id,
    )
    if revision_metadata is not None:
        revision_insert = revision_insert.values(source_metadata=revision_metadata)
    session.execute(revision_insert)
    session.execute(
        update(documents)
        .where(documents.c.document_id == document_id)
        .values(content_hash=stored.content_hash)
    )
    return SavedRevision(
        revision_id=revision_id,
        revision_number=next_number,
        content_hash=stored.content_hash,
        reused=False,
    )


def add_text_block(
    session: Session,
    revision_id: str,
    ordinal: int,
    start_offset: int,
    end_offset: int,
    block_text: str,
) -> str:
    """登记原文文本块: 记录块哈希, 供引文一致性校验。"""
    if start_offset < 0 or end_offset - start_offset != len(block_text):
        raise QuoteConsistencyError("block offsets must cover its Unicode text exactly")
    revision = session.execute(
        select(document_revisions.c.revision_id).where(
            document_revisions.c.revision_id == revision_id
        )
    ).scalar_one_or_none()
    if revision is None:
        raise MissingRevisionError(revision_id)
    block_id = str(uuid.uuid4())
    session.execute(
        text_blocks.insert().values(
            block_id=block_id,
            revision_id=revision_id,
            ordinal=ordinal,
            start_offset=start_offset,
            end_offset=end_offset,
            text_sha256=hashlib.sha256(block_text.encode("utf-8")).hexdigest(),
            block_text=block_text,
        )
    )
    return block_id


def attach_evidence_span(
    session: Session,
    revision_id: str,
    start_offset: int,
    end_offset: int,
    locator: str,
    quote: str,
    supports_claim: bool,
    visibility: str,
    tenant_id: str | None,
    created_at: datetime,
    block_id: str | None = None,
    quote_sha256: str | None = None,
    verified_at: datetime | None = None,
) -> str:
    """挂接证据区间: 租户范围校验 + 引文与原文块一致性校验后持久化。"""
    if (visibility == "tenant") != (tenant_id is not None):
        raise TenantScopeViolation("tenant evidence requires exactly one tenant_id")
    revision = session.execute(
        select(document_revisions.c.visibility, document_revisions.c.tenant_id).where(
            document_revisions.c.revision_id == revision_id
        )
    ).first()
    if revision is None:
        raise MissingRevisionError(revision_id)
    revision_visibility, revision_tenant = revision
    if visibility == "tenant" and revision_visibility == "tenant" and tenant_id != revision_tenant:
        raise TenantScopeViolation("evidence tenant does not match revision tenant")
    if visibility == "public" and revision_visibility == "tenant":
        raise TenantScopeViolation("public evidence cannot derive from tenant revision")
    quote_digest = hashlib.sha256(quote.encode("utf-8")).hexdigest()
    if quote_sha256 is not None and quote_sha256 != quote_digest:
        raise QuoteConsistencyError("quote hash does not match quote text")
    resolved_quote_sha256 = quote_digest
    if block_id is not None:
        block_row = session.execute(
            select(
                text_blocks.c.revision_id,
                text_blocks.c.block_text,
                text_blocks.c.start_offset,
                text_blocks.c.end_offset,
            ).where(text_blocks.c.block_id == block_id)
        ).first()
        if block_row is None:
            raise QuoteConsistencyError("text block does not exist")
        if block_row[0] != revision_id:
            raise QuoteConsistencyError("text block belongs to a different revision")
        block_text = str(block_row[1])
        relative_start = start_offset - int(block_row[2])
        relative_end = end_offset - int(block_row[2])
        if relative_start < 0 or relative_end > len(block_text) or relative_start > relative_end:
            raise QuoteConsistencyError("evidence span outside text block")
        if block_text[relative_start:relative_end] != quote:
            raise QuoteConsistencyError("quote does not match source text at span")
    elif supports_claim or verified_at is not None:
        raise QuoteConsistencyError("verified evidence requires a source text block")
    evidence_id = str(uuid.uuid4())
    session.execute(
        evidence.insert().values(
            evidence_id=evidence_id,
            revision_id=revision_id,
            start_offset=start_offset,
            end_offset=end_offset,
            locator=locator,
            quote=quote,
            supports_claim=supports_claim,
            visibility=visibility,
            tenant_id=tenant_id,
            created_at=created_at,
            block_id=block_id,
            quote_sha256=resolved_quote_sha256,
            verified_at=verified_at,
            coordinate_version="fulltext_unicode_v1"
            if block_id is not None
            else "legacy_unverified",
        )
    )
    return evidence_id


def record_fetch_attempt(
    session: Session,
    source_id: str,
    attempted_at: datetime,
    outcome: str,
    http_status: int | None,
) -> str:
    """保存抓取尝试; new_event_count 恒为 0, 抓取记录不误计新业务事件。"""
    attempt_id = str(uuid.uuid4())
    session.execute(
        fetch_attempts.insert().values(
            attempt_id=attempt_id,
            source_id=source_id,
            attempted_at=attempted_at,
            outcome=outcome,
            http_status=http_status,
            new_event_count=0,
        )
    )
    return attempt_id


def bump_scope_epoch(session: Session, scope_key: str, updated_at: datetime) -> int:
    """递增 scope epoch: 事实变更后旧读缓存据此过期。"""
    statement = insert(scope_epochs).values(scope_key=scope_key, epoch=1, updated_at=updated_at)
    upsert = statement.on_conflict_do_update(
        index_elements=[scope_epochs.c.scope_key],
        set_={"epoch": scope_epochs.c.epoch + 1, "updated_at": updated_at},
    ).returning(scope_epochs.c.epoch)
    return int(session.execute(upsert).scalar_one())


def cleanup_unreferenced_object(session: Session, store: ContentStorage, content_hash: str) -> bool:
    """清理无引用原文对象: 文件与登记行同删; 任何引用存在即拒删。"""
    _lock_content_hash(session, content_hash)
    revision_refs = session.execute(
        select(func.count())
        .select_from(document_revisions)
        .where(document_revisions.c.content_hash == content_hash)
    ).scalar_one()
    document_refs = session.execute(
        select(func.count()).select_from(documents).where(documents.c.content_hash == content_hash)
    ).scalar_one()
    response_revision_refs = session.execute(
        select(func.count())
        .select_from(document_revisions)
        .where(document_revisions.c.source_response_hash == content_hash)
    ).scalar_one()
    response_fetch_refs = session.execute(
        select(func.count())
        .select_from(fetch_attempts)
        .where(fetch_attempts.c.response_content_hash == content_hash)
    ).scalar_one()
    if any(
        int(count) > 0
        for count in (revision_refs, document_refs, response_revision_refs, response_fetch_refs)
    ):
        return False
    try:
        with session.begin_nested():
            session.execute(
                content_objects.delete().where(content_objects.c.content_hash == content_hash)
            )
            store.delete_object(content_hash)
    except IntegrityError as error:
        if getattr(error.orig, "sqlstate", None) == "23503":
            return False
        raise
    return True
