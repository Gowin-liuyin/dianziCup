"""不可变文档修订与证据关联: 修订链语义、租户范围与抓取记录。"""

from __future__ import annotations

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
)


class TenantScopeViolation(ValueError):
    """跨租户证据引用: 拒绝持久化, 不静默改写归属。"""


class MissingRevisionError(LookupError):
    """修订不存在: 调用方不得假设旧读缓存仍然有效。"""


@dataclass(frozen=True)
class SavedRevision:
    """保存结果: reused=True 表示重复末版复用, 未新增修订。"""

    revision_id: str
    revision_index: int
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


def save_document_revision(
    session: Session,
    store: ContentStore,
    document_id: str,
    payload: bytes,
    visibility: str,
    tenant_id: str | None,
    created_at: datetime,
) -> SavedRevision:
    """保存文档修订: 与末版同内容则复用; A→B→A 保留三条按时间排列的修订。"""
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
            revision_index=int(tip["revision_index"]),
            content_hash=stored.content_hash,
            reused=True,
        )
    next_index = (
        session.execute(
            select(func.coalesce(func.max(document_revisions.c.revision_index), 0)).where(
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
            revision_index=next_index,
            content_hash=stored.content_hash,
            created_at=created_at,
            is_current=True,
            supersedes_id=str(tip["revision_id"]) if tip is not None else None,
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
        revision_index=next_index,
        content_hash=stored.content_hash,
        reused=False,
    )


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
) -> str:
    """把证据区间挂到修订; 跨租户引用拒绝持久化。"""
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
    """保存抓取尝试; new_event_count 恒为 0, 抓取记录不误计为新业务事件。"""
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
    """清理无引用原文对象; 写库失败后调用, 不产生指向缺失原文的有效记录。"""
    referencing_rows = session.execute(
        select(func.count())
        .select_from(document_revisions)
        .where(document_revisions.c.content_hash == content_hash)
    ).scalar_one()
    if int(referencing_rows) > 0:
        return False
    store.delete_object(content_hash)
    return True
