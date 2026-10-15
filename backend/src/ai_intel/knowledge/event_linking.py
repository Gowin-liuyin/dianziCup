"""事件关联: 去重/别名归并/相似候选三层; 多 CVE 多事件; 合并撤销不删历史。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal
from uuid import NAMESPACE_URL, uuid4, uuid5

from pydantic import Field, model_validator
from sqlalchemy import and_, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    READ_ASSET,
    READ_PUBLIC,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
)
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.knowledge.models import document_revisions
from ai_intel.knowledge.persistence import (
    PublicationReceipt,
    find_prior_publication,
    knowledge_scope_key,
    publication_payload_digest,
    save_change_publication,
)
from ai_intel.knowledge.persistence_models import (
    event_documents,
    event_external_ids,
    event_operations,
    events,
)

LINKING_VERSION = "linking-1.0.0"


class EventLinkingError(RuntimeError):
    """错误关联修复: 发布影响事件并保留来源与引用, 不删除历史。"""


@dataclass(frozen=True)
class SecurityEvent:
    """安全事件: 携带 CVE 列表/来源/同源组; 同产品或同 CWE 不自动合并。"""

    event_id: str
    cve_ids: tuple[str, ...] = field(default_factory=tuple)
    product_names: tuple[str, ...] = field(default_factory=tuple)
    cwe_ids: tuple[str, ...] = field(default_factory=tuple)
    source_record_ids: tuple[str, ...] = field(default_factory=tuple)
    source_group_id: str = ""
    body_fingerprint: str = ""


class EventIdentifier(StrictRecord):
    id_type: Literal["cve", "ghsa"]
    id_value: str = Field(min_length=1, max_length=200)


class EventSubmission(StrictRecord):
    """一事件一个稳定UUID, 一篇文档可以明确关联多事件。"""

    event_id: Identifier
    event_type: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=500)
    scope: VisibilityScope
    external_ids: tuple[EventIdentifier, ...] = ()
    source_revision_ids: tuple[Identifier, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def one_cve_per_event(self) -> EventSubmission:
        cves = {item.id_value.upper() for item in self.external_ids if item.id_type == "cve"}
        if len(cves) > 1:
            raise ValueError("one article with multiple CVEs requires distinct events")
        return self


class EventRepository:
    """持久化事件与关联操作, 操作前后来源快照保留, 不物理删除历史。"""

    def __init__(self, session: Session, access_scope: AccessScope) -> None:
        self.session = session
        self.access_scope = access_scope

    def _require_scope(self, scope: VisibilityScope) -> None:
        if scope.visibility == "public":
            self.access_scope.requires(MANAGE_PUBLIC_SOURCES)
        else:
            self.access_scope.enforce_visible(scope.visibility, scope.tenant_id)
            self.access_scope.requires(WRITE_ASSET)

    def _visible_event(self, event_id: str) -> RowMapping:
        self.access_scope.requires(READ_PUBLIC)
        visible = and_(events.c.visibility == "public", events.c.tenant_id.is_(None))
        if self.access_scope.tenant_id is not None and READ_ASSET in self.access_scope.permissions:
            visible = or_(
                visible,
                and_(
                    events.c.visibility == "tenant",
                    events.c.tenant_id == self.access_scope.tenant_id,
                ),
            )
        row = (
            self.session.execute(select(events).where(events.c.event_id == event_id, visible))
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        return row

    def publish_events(
        self,
        publication_key: str,
        scope: VisibilityScope,
        submissions: tuple[EventSubmission, ...],
        created_at: datetime,
    ) -> PublicationReceipt:
        self._require_scope(scope)
        submissions = tuple(
            EventSubmission.model_validate(item.model_dump()) for item in submissions
        )
        if (
            not publication_key
            or len(publication_key) > 500
            or not submissions
            or created_at.tzinfo is None
        ):
            raise EventLinkingError("event publication requires key, events and aware timestamp")
        payload = {
            "schema_version": 1,
            "operation": "publish_events",
            "scope": scope.model_dump(mode="json"),
            "events": [submission.model_dump(mode="json") for submission in submissions],
        }
        digest = publication_payload_digest(payload)
        with self.session.begin_nested():
            prior = find_prior_publication(
                self.session, knowledge_scope_key(scope), publication_key, digest
            )
            if prior is not None:
                return prior
            published_ids = []
            for submission in submissions:
                if submission.scope != scope:
                    raise EventLinkingError("event scope differs from publication")
                for revision_id in submission.source_revision_ids:
                    revision = (
                        self.session.execute(
                            select(document_revisions).where(
                                document_revisions.c.revision_id == revision_id.value
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if revision is None:
                        raise EventLinkingError("event source revision not found")
                    self.access_scope.enforce_visible(
                        str(revision["visibility"]), revision["tenant_id"]
                    )
                    if revision["visibility"] == "tenant" and (
                        scope.visibility != "tenant" or scope.tenant_id != revision["tenant_id"]
                    ):
                        raise EventLinkingError("event visibility exceeds source scope")
                matched_ids: set[str] = (
                    set(
                        self.session.execute(
                            select(event_external_ids.c.event_id).where(
                                event_external_ids.c.scope_key == knowledge_scope_key(scope),
                                or_(
                                    *(
                                        and_(
                                            event_external_ids.c.id_type == external.id_type,
                                            event_external_ids.c.id_value
                                            == external.id_value.upper(),
                                        )
                                        for external in submission.external_ids
                                    )
                                ),
                            )
                        ).scalars()
                    )
                    if submission.external_ids
                    else set()
                )
                if len(matched_ids) > 1:
                    raise EventLinkingError("external identifiers refer to conflicting events")
                event_id = (
                    str(next(iter(matched_ids))) if matched_ids else submission.event_id.value
                )
                existing = (
                    self.session.execute(select(events).where(events.c.event_id == event_id))
                    .mappings()
                    .first()
                )
                if existing is None:
                    self.session.execute(
                        events.insert().values(
                            event_id=event_id,
                            event_type=submission.event_type,
                            title=submission.title,
                            scope_key=knowledge_scope_key(scope),
                            visibility=scope.visibility,
                            tenant_id=scope.tenant_id,
                            status="active",
                            first_seen_at=created_at,
                            business_version=1,
                        )
                    )
                elif (
                    existing["scope_key"] != knowledge_scope_key(scope)
                    or existing["event_type"] != submission.event_type
                ):
                    raise EventLinkingError("event identity conflicts with its scope or type")
                elif existing["status"] != "active":
                    raise EventLinkingError("merged event requires explicit association repair")
                else:
                    self.session.execute(
                        update(events)
                        .where(events.c.event_id == event_id)
                        .values(
                            business_version=events.c.business_version + 1,
                        )
                    )
                for external in submission.external_ids:
                    self.session.execute(
                        insert(event_external_ids)
                        .values(
                            event_id=event_id,
                            id_type=external.id_type,
                            id_value=external.id_value.upper(),
                            scope_key=knowledge_scope_key(scope),
                        )
                        .on_conflict_do_nothing(
                            index_elements=[
                                event_external_ids.c.scope_key,
                                event_external_ids.c.id_type,
                                event_external_ids.c.id_value,
                            ]
                        )
                    )
                for revision_id in submission.source_revision_ids:
                    self.session.execute(
                        insert(event_documents)
                        .values(
                            event_id=event_id,
                            revision_id=revision_id.value,
                            active=True,
                            associated_at=created_at,
                        )
                        .on_conflict_do_nothing(
                            index_elements=[
                                event_documents.c.event_id,
                                event_documents.c.revision_id,
                            ]
                        )
                    )
                published_ids.append(event_id)
            return save_change_publication(
                self.session,
                scope,
                publication_key,
                payload,
                digest,
                (),
                tuple(dict.fromkeys(published_ids)),
                created_at,
                "events_published",
            )

    def merge_events(
        self,
        publication_key: str,
        source_event_id: str,
        target_event_id: str,
        reason: str,
        recorded_at: datetime,
    ) -> PublicationReceipt:
        """保存显式授权的关联操作; 不把同文指纹或不同CVE自动视为等价。"""
        source, target = self._visible_event(source_event_id), self._visible_event(target_event_id)
        if source_event_id == target_event_id or source["scope_key"] != target["scope_key"]:
            raise EventLinkingError("merge requires distinct events in one scope")
        scope = VisibilityScope(visibility=str(source["visibility"]), tenant_id=source["tenant_id"])
        self._require_scope(scope)
        if not publication_key or not reason or recorded_at.tzinfo is None:
            raise EventLinkingError("merge requires key, reason and aware timestamp")
        payload = {
            "schema_version": 1,
            "operation": "merge_events",
            "operation_id": str(
                uuid5(NAMESPACE_URL, knowledge_scope_key(scope) + ":" + publication_key)
            ),
            "source_event_id": source_event_id,
            "target_event_id": target_event_id,
            "reason": reason,
            "scope": scope.model_dump(mode="json"),
        }
        digest = publication_payload_digest(payload)
        with self.session.begin_nested():
            prior = find_prior_publication(
                self.session, knowledge_scope_key(scope), publication_key, digest
            )
            if prior is not None:
                return prior
            source, target = (
                self._visible_event(source_event_id),
                self._visible_event(target_event_id),
            )
            if (
                source["status"] != "active"
                or target["status"] != "active"
                or source["event_type"] != target["event_type"]
            ):
                raise EventLinkingError("merge requires active events of matching type")
            cves: dict[str, set[str]] = {}
            for event_id in (source_event_id, target_event_id):
                cves[event_id] = set(
                    self.session.execute(
                        select(event_external_ids.c.id_value).where(
                            event_external_ids.c.event_id == event_id,
                            event_external_ids.c.id_type == "cve",
                        )
                    ).scalars()
                )
            if (
                cves[source_event_id]
                and cves[target_event_id]
                and cves[source_event_id] != cves[target_event_id]
            ):
                raise EventLinkingError("different CVEs must not merge")
            source_refs = self.get_source_revisions(source_event_id)
            target_refs = self.get_source_revisions(target_event_id)
            self.session.execute(
                event_operations.insert().values(
                    operation_id=payload["operation_id"],
                    operation_type="merge",
                    source_event_id=source_event_id,
                    target_event_id=target_event_id,
                    source_business_version=source["business_version"],
                    target_business_version=target["business_version"],
                    source_revision_ids=list(source_refs),
                    target_revision_ids=list(target_refs),
                    reason=reason,
                    recorded_at=recorded_at,
                )
            )
            for revision_id in source_refs:
                self.session.execute(
                    insert(event_documents)
                    .values(
                        event_id=target_event_id,
                        revision_id=revision_id,
                        active=True,
                        associated_at=recorded_at,
                    )
                    .on_conflict_do_nothing(
                        index_elements=[event_documents.c.event_id, event_documents.c.revision_id]
                    )
                )
            self.session.execute(
                update(events)
                .where(events.c.event_id == source_event_id)
                .values(status="merged", business_version=events.c.business_version + 1)
            )
            self.session.execute(
                update(events)
                .where(events.c.event_id == target_event_id)
                .values(business_version=events.c.business_version + 1)
            )
            return save_change_publication(
                self.session,
                scope,
                publication_key,
                payload,
                digest,
                (),
                (source_event_id, target_event_id),
                recorded_at,
                "events_merged",
            )

    def undo_merge(
        self, publication_key: str, operation_id: str, reason: str, recorded_at: datetime
    ) -> PublicationReceipt:
        original = (
            self.session.execute(
                select(event_operations).where(
                    event_operations.c.operation_id == operation_id,
                    event_operations.c.operation_type == "merge",
                )
            )
            .mappings()
            .first()
        )
        if original is None:
            raise CrossTenantAccessError("resource not found")
        source = self._visible_event(str(original["source_event_id"]))
        self._visible_event(str(original["target_event_id"]))
        scope = VisibilityScope(visibility=str(source["visibility"]), tenant_id=source["tenant_id"])
        self._require_scope(scope)
        if not publication_key or not reason or recorded_at.tzinfo is None:
            raise EventLinkingError("undo requires key, reason and aware timestamp")
        payload = {
            "schema_version": 1,
            "operation": "undo_event_merge",
            "operation_id": operation_id,
            "reason": reason,
            "scope": scope.model_dump(mode="json"),
        }
        digest = publication_payload_digest(payload)
        with self.session.begin_nested():
            prior = find_prior_publication(
                self.session, knowledge_scope_key(scope), publication_key, digest
            )
            if prior is not None:
                return prior
            current_source = self._visible_event(str(original["source_event_id"]))
            current_target = self._visible_event(str(original["target_event_id"]))
            if (
                original["source_business_version"] is None
                or original["target_business_version"] is None
                or current_source["business_version"] != original["source_business_version"] + 1
                or current_target["business_version"] != original["target_business_version"] + 1
                or current_source["status"] != "merged"
                or current_target["status"] != "active"
            ):
                raise EventLinkingError(
                    "events changed after merge; manual association rebase required"
                )
            if (
                self.session.execute(
                    select(event_operations.c.operation_id).where(
                        event_operations.c.inverse_operation_id == operation_id
                    )
                ).first()
                is not None
            ):
                raise EventLinkingError("merge has already been undone")
            source_id, target_id = (
                str(original["source_event_id"]),
                str(original["target_event_id"]),
            )
            added_refs = set(original["source_revision_ids"]) - set(original["target_revision_ids"])
            self.session.execute(
                update(event_documents)
                .where(
                    event_documents.c.event_id == target_id,
                    event_documents.c.revision_id.in_(added_refs),
                )
                .values(active=False, superseded_at=recorded_at)
            )
            self.session.execute(
                event_operations.insert().values(
                    operation_id=str(uuid4()),
                    operation_type="undo",
                    source_event_id=source_id,
                    target_event_id=target_id,
                    inverse_operation_id=operation_id,
                    source_revision_ids=original["source_revision_ids"],
                    target_revision_ids=original["target_revision_ids"],
                    reason=reason,
                    recorded_at=recorded_at,
                )
            )
            self.session.execute(
                update(events)
                .where(events.c.event_id.in_((source_id, target_id)))
                .values(status="active", business_version=events.c.business_version + 1)
            )
            return save_change_publication(
                self.session,
                scope,
                publication_key,
                payload,
                digest,
                (),
                (source_id, target_id),
                recorded_at,
                "event_merge_undone",
            )

    def get_source_revisions(self, event_id: str) -> tuple[str, ...]:
        self._visible_event(event_id)
        statement = (
            select(event_documents.c.revision_id)
            .where(
                event_documents.c.event_id == event_id,
                event_documents.c.active.is_(True),
            )
            .order_by(event_documents.c.revision_id)
        )
        return tuple(self.session.execute(statement).scalars().all())


@dataclass
class EventLinkingLedger:
    """显式旧fixture台账; 产品事件历史须由PostgreSQL保存。"""

    events: dict[str, SecurityEvent] = field(default_factory=dict)
    merged_history: list[tuple[str, str]] = field(default_factory=list)
    withdrawn_merges: list[tuple[str, str]] = field(default_factory=list)
    impact_events: list[str] = field(default_factory=list)
    fixture_mode: bool = False

    def __post_init__(self) -> None:
        if not self.fixture_mode:
            raise EventLinkingError("memory event linking requires explicit fixture_mode")

    def link_article_events(
        self, article_cve_ids: list[str], source_record_id: str, body_fingerprint: str
    ) -> list[str]:
        """一文多 CVE → 多事件关联, 不并成同一事件。"""
        created: list[str] = []
        for index, cve_id in enumerate(article_cve_ids):
            event_id = f"ev-{cve_id}-{source_record_id}-{index}"
            self.events[event_id] = SecurityEvent(
                event_id=event_id,
                cve_ids=(cve_id,),
                source_record_ids=(source_record_id,),
                body_fingerprint=body_fingerprint,
            )
            created.append(event_id)
        return created

    def should_merge(
        self, left: SecurityEvent, right: SecurityEvent, trusted_aliases: tuple[str, ...]
    ) -> bool:
        """可靠别名才归并; 同产品/同 CWE 不是合并依据。"""
        shared_cves = set(left.cve_ids) & set(right.cve_ids)
        return bool(shared_cves) and any(cve_id in trusted_aliases for cve_id in shared_cves)

    def merge_events(self, keep_id: str, merge_id: str) -> None:
        """合并记录入台账, 原两条记录保留于历史, 不物理删除。"""
        if keep_id not in self.events or merge_id not in self.events:
            raise EventLinkingError("both events must exist before merge")
        self.merged_history.append((keep_id, merge_id))

    def undo_merge(self, keep_id: str, merge_id: str) -> None:
        """撤销错误合并: 恢复来源与引用, 发布影响事件, 不删除历史。"""
        if (keep_id, merge_id) not in self.merged_history:
            raise EventLinkingError("merge record not found; nothing to undo")
        self.withdrawn_merges.append((keep_id, merge_id))
        self.impact_events.append(f"merge_withdrawn:{keep_id}:{merge_id}")

    def describe_history(self) -> dict[str, object]:
        """历史完整可追溯: 合并/撤销/影响事件全保留。"""
        return {
            "merged": list(self.merged_history),
            "withdrawn": list(self.withdrawn_merges),
            "impact_events": list(self.impact_events),
            "current_event_count": len(self.events),
        }
