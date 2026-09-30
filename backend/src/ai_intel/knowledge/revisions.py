"""不可变文档修订与证据关联: 修订链语义、租户范围、引文一致性与抓取记录。"""

from __future__ import annotations

import hashlib
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ai_intel.infrastructure.content_store import ContentStore
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
    existing = session.execute(
        select(content_objects.c.content_hash).where(content_objects.c.content_hash == content_hash)
    ).scalar_one_or_none()
    if existing is None:
        session.execute(
            content_objects.insert().values(
                content_hash=content_hash, size_bytes=size_bytes, created_at=created_at
            )
        )


def _load_document_row(session: Session, document_id: str) -> dict[str, object]:
    """读取文档父行; 不存在即拒绝, 保证修订不脱离文档。"""
    row = (
        session.execute(select(documents).where(documents.c.document_id == document_id))
        .mappings()
        .first()
    )
    if row is None:
        raise MissingDocumentError(document_id)
    return dict(row)


def save_document_revision(
    session: Session,
    store: ContentStore,
    document_id: str,
    payload: bytes,
    visibility: str,
    tenant_id: str | None,
    created_at: datetime,
) -> SavedRevision:
    """保存文档修订: 末版同内容复用; A→B→A 保留三修订; 归属与租户必须一致。"""
    document_row = _load_document_row(session, document_id)
    if (visibility == "tenant") != (tenant_id is not None):
        raise TenantScopeViolation("tenant revision requires exactly one tenant_id")
    if visibility != document_row["visibility"] or tenant_id != document_row["tenant_id"]:
        raise TenantScopeViolation("revision scope does not match document scope")
    stored = store.store_bytes(payload)
    _insert_content_object(session, stored.content_hash, stored.size_bytes, created_at)
    tip = (
        session.execute(
            select(document_revisions)
            .where(
                document_revisions.c.document_id == document_id,
                document_revisions.c.is_current.is_(True),
            )
            .limit(1)
        )
        .mappings()
        .first()
    )
    if tip is not None and tip["content_hash"] == stored.content_hash:
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
    session.execute(
        document_revisions.insert().values(
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
    )
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
            select(text_blocks.c.revision_id, text_blocks.c.block_text).where(
                text_blocks.c.block_id == block_id
            )
        ).first()
        if block_row is None:
            raise QuoteConsistencyError("text block does not exist")
        if block_row[0] != revision_id:
            raise QuoteConsistencyError("text block belongs to a different revision")
        block_text = str(block_row[1])
        if start_offset < 0 or end_offset > len(block_text) or start_offset > end_offset:
            raise QuoteConsistencyError("evidence span outside text block")
        if block_text[start_offset:end_offset] != quote:
            raise QuoteConsistencyError("quote does not match source text at span")
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
    current = session.execute(
        select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == scope_key)
    ).scalar_one_or_none()
    next_epoch = 1 if current is None else int(current) + 1
    if current is None:
        session.execute(
            scope_epochs.insert().values(
                scope_key=scope_key, epoch=next_epoch, updated_at=updated_at
            )
        )
    else:
        session.execute(
            update(scope_epochs)
            .where(scope_epochs.c.scope_key == scope_key)
            .values(epoch=next_epoch, updated_at=updated_at)
        )
    return next_epoch


def cleanup_unreferenced_object(session: Session, store: ContentStore, content_hash: str) -> bool:
    """清理无引用原文对象: 文件与登记行同删; 任何引用存在即拒删。"""
    revision_refs = session.execute(
        select(func.count())
        .select_from(document_revisions)
        .where(document_revisions.c.content_hash == content_hash)
    ).scalar_one()
    document_refs = session.execute(
        select(func.count()).select_from(documents).where(documents.c.content_hash == content_hash)
    ).scalar_one()
    if int(revision_refs) > 0 or int(document_refs) > 0:
        return False
    store.delete_object(content_hash)
    session.execute(content_objects.delete().where(content_objects.c.content_hash == content_hash))
    return True
