"""知识发布的明确输入/收据; PostgreSQL是事实与收据唯一权威。"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator
from sqlalchemy import and_, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    READ_ASSET,
    READ_PUBLIC,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
)
from ai_intel.domain.enrichment_values import CvssSignalValue, LiteratureReferenceValue
from ai_intel.domain.enums import ClaimOrigin, ClaimStatus
from ai_intel.domain.records import ClaimRecord, EvidenceRecord, ScoreValue, StrictRecord
from ai_intel.domain.values import Identifier, UtcTimestamp, VisibilityScope
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.entities import canonicalize_entity
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    evidence,
    job_runs,
    outbox_events,
)
from ai_intel.knowledge.persistence_models import (
    change_events,
    claim_assertions,
    claim_evidence,
    claim_relations,
    claim_status_history,
    claims,
    entities,
    entity_aliases,
    publication_receipts,
)
from ai_intel.knowledge.revisions import bump_scope_epoch


class KnowledgePublicationError(ValueError):
    """发布合同不成立; 不降级为成功收据或未核验的当前事实。"""


class EvidenceLink(StrictRecord):
    """引文存在与语义支持分开记录, 未核验引文不能支撑已确认事实。"""

    evidence_id: Identifier
    support_kind: Literal["supports", "refutes", "context"]
    validation_status: Literal["validated", "unverified"]


class SupportingSource(StrictRecord):
    """An additional fixed source revision for an explicitly composed v3 assertion."""

    source_id: Identifier
    revision_id: Identifier
    json_path: str = Field(min_length=1, max_length=2000)
    scoring_authority: str = Field(default="", max_length=500)


class ClaimSubmission(StrictRecord):
    """单字段断言与具体来源修订, 不接受来源未说明的事实写入。"""

    record: ClaimRecord
    source_id: Identifier
    revision_id: Identifier
    json_path: str = Field(min_length=1, max_length=2000)
    scoring_authority: str = Field(default="", max_length=500)
    evidence_links: tuple[EvidenceLink, ...] = Field(min_length=1)
    additional_sources: tuple[SupportingSource, ...] = Field(
        default=(), max_length=19, exclude_if=lambda sources: not sources
    )

    @model_validator(mode="after")
    def validate_composed_sources(self) -> ClaimSubmission:
        if self.additional_sources and self.record.schema_version != 3:
            raise ValueError("additional sources require an explicit v3 claim")
        revisions = [
            self.revision_id.value,
            *(s.revision_id.value for s in self.additional_sources),
        ]
        if len(set(revisions)) != len(revisions):
            raise ValueError("each supporting revision must be declared once")
        return self


class StoredEvidence(StrictRecord):
    """固定修订与坐标版本一同返回; legacy引文保持未核验标识。"""

    record: EvidenceRecord
    revision_id: Identifier
    block_id: Identifier | None
    scope: VisibilityScope
    quote_sha256: str | None
    coordinate_version: Literal["fulltext_unicode_v1", "legacy_unverified"]
    verified_at: UtcTimestamp | None


class ClaimRelation(StrictRecord):
    """已核验同范围事实关系; 历史通过新增关系和状态转换保留。"""

    left_claim_id: Identifier
    right_claim_id: Identifier
    relation_type: Literal["supersedes", "disputed"]
    reason: str = Field(min_length=1, max_length=2000)


class AliasSubmission(StrictRecord):
    """别名绑定来源版本和可验证引文, 默认只作为候选。"""

    alias_value: str = Field(min_length=1, max_length=500)
    source_id: Identifier
    revision_id: Identifier
    evidence_id: Identifier
    status: Literal["validated", "unverified"] = "unverified"
    valid_from: UtcTimestamp | None = None
    valid_to: UtcTimestamp | None = None


class EntitySubmission(StrictRecord):
    """同名不同生态、租户保留独立身份; 只执行规范键归一。"""

    entity_id: Identifier
    entity_type: str = Field(min_length=1, max_length=100)
    ecosystem: str = Field(min_length=1, max_length=100)
    canonical_name: str = Field(min_length=1, max_length=500)
    scope: VisibilityScope
    aliases: tuple[AliasSubmission, ...] = ()


@dataclass(frozen=True)
class PublicationReceipt:
    """调用方事务提交后可跨进程重读的收据; 重放返回同一数据库身份。"""

    receipt_id: str
    scope_key: str
    publication_key: str
    payload_sha256: str
    claim_ids: tuple[str, ...]
    epoch: int
    job_id: str
    outbox_id: str
    change_id: str
    created_at: datetime


def knowledge_scope_key(scope: VisibilityScope) -> str:
    return "public" if scope.visibility == "public" else "tenant:" + str(scope.tenant_id)


def publication_payload_digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _claim_display_value(record: ClaimRecord) -> str:
    """Bound v3 display text while object_json retains the complete structured value."""
    value = record.object_value
    displayed = value if isinstance(value, str) else value.model_dump_json()
    suffix = " …（显示摘要已截断；完整结构已保存，请查看原文证据）"
    if record.schema_version == 3 and len(displayed) > 4000:
        return displayed[: 4000 - len(suffix)] + suffix
    return displayed


def _claim_from_row(row: RowMapping, status: str | None = None) -> ClaimRecord:
    if row["provenance_status"] == "legacy_unverified":
        status = ClaimStatus.UNVERIFIED.value
    return ClaimRecord.model_validate(
        {
            "schema_version": row["schema_version"],
            "claim_id": {"value": row["claim_id"]},
            "subject": row["subject"],
            "predicate": row["predicate"],
            "object_value": row["object_json"]
            if row["object_json"] is not None
            else row["object_value"],
            "claim_status": status or row["claim_status"],
            "claim_origin": row["claim_origin"],
            "condition_value": row["condition_value"],
            "freshness": row["freshness"],
            "asserted_at": row["asserted_at"],
            "observed_at": row["observed_at"],
            "scope": {"visibility": row["visibility"], "tenant_id": row["tenant_id"]},
        }
    )


def _receipt_from_row(row: RowMapping) -> PublicationReceipt:
    return PublicationReceipt(
        receipt_id=str(row["receipt_id"]),
        scope_key=str(row["scope_key"]),
        publication_key=str(row["publication_key"]),
        payload_sha256=str(row["payload_sha256"]),
        claim_ids=tuple(row["claim_ids"]),
        epoch=int(row["epoch"]),
        job_id=str(row["job_id"]),
        outbox_id=str(row["outbox_id"]),
        change_id=str(row["change_id"]),
        created_at=row["created_at"],
    )


def find_prior_publication(
    session: Session,
    scope_key: str,
    publication_key: str,
    payload_sha256: str,
) -> PublicationReceipt | None:
    """同scope串行发布并核对已提交收据; 不同内容重用key显式拒绝。"""
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended("knowledge-publication:" + scope_key, 0),
            )
        )
    )
    prior = (
        session.execute(
            select(publication_receipts).where(
                publication_receipts.c.scope_key == scope_key,
                publication_receipts.c.publication_key == publication_key,
            )
        )
        .mappings()
        .first()
    )
    if prior is None:
        return None
    if prior["payload_sha256"] != payload_sha256:
        raise IdempotencyConflictError("publication key reused with different payload")
    return _receipt_from_row(prior)


def save_change_publication(
    session: Session,
    scope: VisibilityScope,
    publication_key: str,
    payload: dict[str, object],
    payload_sha256: str,
    claim_ids: tuple[str, ...],
    changed_ids: tuple[str, ...],
    created_at: datetime,
    change_type: str,
) -> PublicationReceipt:
    """事实与事件共用真实change/epoch/jobs/outbox收据写入; 调用方持scope锁及事务。"""
    scope_key = knowledge_scope_key(scope)
    epoch = bump_scope_epoch(session, scope_key, created_at)
    change_id, job_id, outbox_id, receipt_id = (str(uuid4()) for _ in range(4))
    payload_ref = "pg:change:" + change_id
    session.execute(
        change_events.insert().values(
            change_id=change_id,
            scope_key=scope_key,
            epoch=epoch,
            change_type=change_type,
            entity_ids=list(changed_ids),
            payload=payload,
            created_at=created_at,
        )
    )
    session.execute(
        job_runs.insert().values(
            job_id=job_id,
            tenant_id=scope.tenant_id,
            job_type="knowledge_change",
            status="queued",
            idempotency_key="knowledge-change:" + receipt_id,
            payload_sha256=payload_sha256,
            payload_ref=payload_ref,
            attempt_count=0,
            max_attempts=5,
            created_at=created_at,
            updated_at=created_at,
        )
    )
    session.execute(
        outbox_events.insert().values(
            event_id=outbox_id,
            job_id=job_id,
            topic="job.knowledge_change",
            payload_ref=payload_ref,
            created_at=created_at,
        )
    )
    session.execute(
        publication_receipts.insert().values(
            receipt_id=receipt_id,
            scope_key=scope_key,
            publication_key=publication_key,
            payload_sha256=payload_sha256,
            claim_ids=list(claim_ids),
            epoch=epoch,
            job_id=job_id,
            outbox_id=outbox_id,
            change_id=change_id,
            created_at=created_at,
        )
    )
    return PublicationReceipt(
        receipt_id,
        scope_key,
        publication_key,
        payload_sha256,
        claim_ids,
        epoch,
        job_id,
        outbox_id,
        change_id,
        created_at,
    )


class KnowledgeRepository:
    """同Session发布、读取与历史转换; 内部不commit, 不回退内存。"""

    def __init__(self, session: Session, access_scope: AccessScope) -> None:
        self.session = session
        self.access_scope = access_scope

    def _visible_claims(self) -> ColumnElement[bool]:
        self.access_scope.requires(READ_PUBLIC)
        public = and_(claims.c.visibility == "public", claims.c.tenant_id.is_(None))
        if self.access_scope.tenant_id is not None and READ_ASSET in self.access_scope.permissions:
            return or_(
                public,
                and_(
                    claims.c.visibility == "tenant",
                    claims.c.tenant_id == self.access_scope.tenant_id,
                ),
            )
        return public

    def _require_write_scope(self, scope: VisibilityScope) -> None:
        if scope.visibility == "public":
            self.access_scope.requires(MANAGE_PUBLIC_SOURCES)
        else:
            self.access_scope.enforce_visible(scope.visibility, scope.tenant_id)
            self.access_scope.requires(WRITE_ASSET)

    def _validate_submission(self, submission: ClaimSubmission, scope: VisibilityScope) -> None:
        record = submission.record
        if record.scope != scope:
            raise KnowledgePublicationError("publication requires a single visibility scope")
        if record.schema_version == 1 and record.claim_status != ClaimStatus.UNVERIFIED:
            raise KnowledgePublicationError("legacy claims must remain unverified")
        if record.claim_status not in (ClaimStatus.SUPPORTED, ClaimStatus.UNVERIFIED):
            raise KnowledgePublicationError("initial status must be supported or unverified")
        if (
            isinstance(record.object_value, (ScoreValue, CvssSignalValue))
            and record.object_value.authority != submission.scoring_authority
        ):
            raise KnowledgePublicationError("score authority differs from source assertion")
        if (
            record.claim_origin == ClaimOrigin.MODEL_HYPOTHESIS
            and record.claim_status != ClaimStatus.UNVERIFIED
        ):
            raise KnowledgePublicationError("model hypothesis must remain unverified")
        assertions = (
            SupportingSource(
                source_id=submission.source_id,
                revision_id=submission.revision_id,
                json_path=submission.json_path,
                scoring_authority=submission.scoring_authority,
            ),
            *submission.additional_sources,
        )
        for assertion in assertions:
            source_row = self.session.execute(
                text("SELECT visibility,tenant_id FROM sources WHERE source_id=:source_id"),
                {"source_id": assertion.source_id.value},
            ).first()
            revision_row = self.session.execute(
                select(document_revisions.c.visibility, document_revisions.c.tenant_id)
                .join(documents, documents.c.document_id == document_revisions.c.document_id)
                .where(
                    document_revisions.c.revision_id == assertion.revision_id.value,
                    documents.c.source_id == assertion.source_id.value,
                )
            ).first()
            if source_row is None or revision_row is None:
                raise CrossTenantAccessError("resource not found")
            for source_scope in (source_row, revision_row):
                self.access_scope.enforce_visible(str(source_scope[0]), source_scope[1])
                if source_scope[0] == "tenant" and (
                    scope.visibility != "tenant" or scope.tenant_id != source_scope[1]
                ):
                    raise KnowledgePublicationError("derived visibility exceeds source scope")
        if (
            isinstance(record.object_value, LiteratureReferenceValue)
            and record.object_value.target_document_id is not None
        ):
            target = self.session.execute(
                select(document_revisions.c.visibility, document_revisions.c.tenant_id).where(
                    document_revisions.c.document_id == str(record.object_value.target_document_id),
                    document_revisions.c.revision_id == str(record.object_value.target_revision_id),
                )
            ).first()
            if target is None:
                raise CrossTenantAccessError("resource not found")
            self.access_scope.enforce_visible(str(target[0]), target[1])
            if target[0] == "tenant" and (
                scope.visibility != "tenant" or scope.tenant_id != target[1]
            ):
                raise KnowledgePublicationError("derived visibility exceeds reference target scope")
        verified_support = False
        declared_revisions = {assertion.revision_id.value for assertion in assertions}
        used_revisions: set[str] = set()
        for link in submission.evidence_links:
            row = (
                self.session.execute(
                    select(evidence).where(
                        evidence.c.evidence_id == link.evidence_id.value,
                        evidence.c.revision_id.in_(declared_revisions),
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            used_revisions.add(str(row["revision_id"]))
            self.access_scope.enforce_visible(str(row["visibility"]), row["tenant_id"])
            if row["visibility"] == "tenant" and (
                scope.visibility != "tenant" or scope.tenant_id != row["tenant_id"]
            ):
                raise KnowledgePublicationError("derived visibility exceeds evidence scope")
            if link.validation_status == "validated" and (
                row["coordinate_version"] != "fulltext_unicode_v1" or row["verified_at"] is None
            ):
                raise KnowledgePublicationError(
                    "legacy or unverified coordinate cannot be validated"
                )
            if (
                link.support_kind == "supports"
                and link.validation_status == "validated"
                and row["supports_claim"]
            ):
                verified_support = True
        if used_revisions != declared_revisions:
            raise KnowledgePublicationError("every declared source requires its own evidence")
        if record.claim_status == ClaimStatus.SUPPORTED and not verified_support:
            raise KnowledgePublicationError("supported claim requires verified semantic support")

    def publish(
        self,
        publication_key: str,
        scope: VisibilityScope,
        submissions: tuple[ClaimSubmission, ...],
        *,
        relations: tuple[ClaimRelation, ...] = (),
        entity_submissions: tuple[EntitySubmission, ...] = (),
        created_at: datetime,
    ) -> PublicationReceipt:
        """业务发布与epoch/change/jobs/outbox同事务; 失败保存点回滚不占幂等键。"""
        self._require_write_scope(scope)
        submissions = tuple(
            ClaimSubmission.model_validate(item.model_dump()) for item in submissions
        )
        relations = tuple(ClaimRelation.model_validate(item.model_dump()) for item in relations)
        entity_submissions = tuple(
            EntitySubmission.model_validate(item.model_dump()) for item in entity_submissions
        )
        if not publication_key or len(publication_key) > 500 or not submissions:
            raise KnowledgePublicationError(
                "publication requires a bounded key and nonempty claims"
            )
        if created_at.tzinfo is None:
            raise KnowledgePublicationError("publication timestamp must be timezone aware")
        created_at = created_at.astimezone(UTC)
        scope_key = knowledge_scope_key(scope)
        payload = {
            "schema_version": 1,
            "scope": scope.model_dump(mode="json"),
            "claims": [submission.model_dump(mode="json") for submission in submissions],
            "relations": [relation.model_dump(mode="json") for relation in relations],
            "entities": [entity.model_dump(mode="json") for entity in entity_submissions],
        }
        payload_sha256 = publication_payload_digest(payload)
        with self.session.begin_nested():
            prior = find_prior_publication(self.session, scope_key, publication_key, payload_sha256)
            if prior is not None:
                return prior
            for submission in submissions:
                self._validate_submission(submission, scope)
            resolved_ids = {
                submission.record.claim_id.value: self._save_claim(submission, created_at)
                for submission in submissions
            }
            for relation in relations:
                self._apply_relation(relation, resolved_ids, scope, created_at)
            entity_ids = tuple(
                self._save_entity(entity, scope, created_at) for entity in entity_submissions
            )
            claim_ids = tuple(dict.fromkeys(resolved_ids.values()))
            return save_change_publication(
                self.session,
                scope,
                publication_key,
                payload,
                payload_sha256,
                claim_ids,
                claim_ids + entity_ids,
                created_at,
                "knowledge_published",
            )

    def _save_claim(self, submission: ClaimSubmission, created_at: datetime) -> str:
        record = submission.record
        fingerprint_input = submission.model_dump(mode="json", exclude={"evidence_links"})
        fingerprint_input["record"].pop("claim_id")
        locations = []
        for link in submission.evidence_links:
            row = (
                self.session.execute(
                    select(evidence).where(
                        evidence.c.evidence_id == link.evidence_id.value,
                    )
                )
                .mappings()
                .one()
            )
            locations.append(
                {
                    "block_id": row["block_id"],
                    "start_offset": row["start_offset"],
                    "end_offset": row["end_offset"],
                    "quote_sha256": row["quote_sha256"],
                    "support_kind": link.support_kind,
                    "validation_status": link.validation_status,
                }
            )
        fingerprint_input["locations"] = locations
        fingerprint = publication_payload_digest(fingerprint_input)
        prior = self.session.execute(
            select(claims.c.claim_id).where(
                claims.c.field_fingerprint == fingerprint,
            )
        ).scalar_one_or_none()
        if prior is not None:
            return str(prior)
        value = record.object_value
        object_json = None if isinstance(value, str) else value.model_dump(mode="json")
        self.session.execute(
            claims.insert().values(
                claim_id=record.claim_id.value,
                subject=record.subject,
                predicate=record.predicate,
                object_value=_claim_display_value(record),
                object_json=object_json,
                value_kind="text" if isinstance(value, str) else value.kind,
                claim_status=record.claim_status.value,
                claim_origin=record.claim_origin.value,
                condition_value=record.condition_value.value,
                freshness=record.freshness.value,
                asserted_at=record.asserted_at,
                observed_at=record.observed_at,
                visibility=record.scope.visibility,
                tenant_id=record.scope.tenant_id,
                created_at=created_at,
                source_revision_id=submission.revision_id.value,
                schema_version=record.schema_version,
                provenance_status="legacy_unverified"
                if record.schema_version == 1
                else "source_verified",
                field_fingerprint=fingerprint,
                is_current=True,
            )
        )
        assertions = (
            SupportingSource(
                source_id=submission.source_id,
                revision_id=submission.revision_id,
                json_path=submission.json_path,
                scoring_authority=submission.scoring_authority,
            ),
            *submission.additional_sources,
        )
        self.session.execute(
            claim_assertions.insert(),
            [
                {
                    "assertion_id": str(uuid4()),
                    "claim_id": record.claim_id.value,
                    "source_id": assertion.source_id.value,
                    "revision_id": assertion.revision_id.value,
                    "json_path": assertion.json_path,
                    "scoring_authority": assertion.scoring_authority,
                    "assertion_kind": record.claim_origin.value,
                    "created_at": created_at,
                }
                for assertion in assertions
            ],
        )
        for link in submission.evidence_links:
            self.session.execute(
                claim_evidence.insert().values(
                    claim_id=record.claim_id.value,
                    evidence_id=link.evidence_id.value,
                    support_kind=link.support_kind,
                    validation_status=link.validation_status,
                )
            )
        self._record_status(
            record.claim_id.value, record.claim_status.value, "initial publication", created_at
        )
        return record.claim_id.value

    def _record_status(self, claim_id: str, status: str, reason: str, changed_at: datetime) -> None:
        self.session.execute(
            claim_status_history.insert().values(
                history_id=str(uuid4()),
                claim_id=claim_id,
                status=status,
                reason=reason,
                changed_at=changed_at,
            )
        )

    def _save_entity(
        self, entity: EntitySubmission, scope: VisibilityScope, created_at: datetime
    ) -> str:
        if entity.scope != scope:
            raise KnowledgePublicationError("entity scope differs from publication")
        key = canonicalize_entity(entity.entity_type, entity.ecosystem, entity.canonical_name)
        statement = (
            insert(entities)
            .values(
                entity_id=entity.entity_id.value,
                entity_type=key.entity_type,
                ecosystem=key.ecosystem,
                canonical_name=key.canonical_name,
                scope_key=knowledge_scope_key(scope),
                visibility=scope.visibility,
                tenant_id=scope.tenant_id,
                created_at=created_at,
            )
            .on_conflict_do_nothing(
                index_elements=[
                    entities.c.scope_key,
                    entities.c.entity_type,
                    entities.c.ecosystem,
                    entities.c.canonical_name,
                ]
            )
        )
        self.session.execute(statement)
        entity_id = str(
            self.session.execute(
                select(entities.c.entity_id).where(
                    entities.c.scope_key == knowledge_scope_key(scope),
                    entities.c.entity_type == key.entity_type,
                    entities.c.ecosystem == key.ecosystem,
                    entities.c.canonical_name == key.canonical_name,
                )
            ).scalar_one()
        )
        for alias in entity.aliases:
            row = (
                self.session.execute(
                    select(evidence)
                    .join(
                        document_revisions,
                        document_revisions.c.revision_id == evidence.c.revision_id,
                    )
                    .join(documents, documents.c.document_id == document_revisions.c.document_id)
                    .where(
                        evidence.c.evidence_id == alias.evidence_id.value,
                        evidence.c.revision_id == alias.revision_id.value,
                        documents.c.source_id == alias.source_id.value,
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            self.access_scope.enforce_visible(str(row["visibility"]), row["tenant_id"])
            if row["visibility"] == "tenant" and (
                scope.visibility != "tenant" or scope.tenant_id != row["tenant_id"]
            ):
                raise KnowledgePublicationError("alias visibility exceeds evidence scope")
            if (
                alias.valid_from is not None
                and alias.valid_to is not None
                and alias.valid_from > alias.valid_to
            ):
                raise KnowledgePublicationError("alias validity window is inverted")
            if alias.status == "validated" and (
                row["coordinate_version"] != "fulltext_unicode_v1"
                or row["verified_at"] is None
                or not row["supports_claim"]
            ):
                raise KnowledgePublicationError("validated alias requires verified support")
            self.session.execute(
                insert(entity_aliases)
                .values(
                    alias_id=str(uuid4()),
                    entity_id=entity_id,
                    source_id=alias.source_id.value,
                    revision_id=alias.revision_id.value,
                    evidence_id=alias.evidence_id.value,
                    alias_value=alias.alias_value,
                    status=alias.status,
                    created_at=created_at,
                    valid_from=alias.valid_from,
                    valid_to=alias.valid_to,
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        entity_aliases.c.entity_id,
                        entity_aliases.c.alias_value,
                        entity_aliases.c.evidence_id,
                    ]
                )
            )
        return entity_id

    def resolve_entity_alias(self, alias_value: str, *, known_at: datetime) -> tuple[str, ...]:
        self.access_scope.requires(READ_PUBLIC)
        if known_at.tzinfo is None:
            raise KnowledgePublicationError("alias query timestamp must be timezone aware")
        visible = and_(entities.c.visibility == "public", entities.c.tenant_id.is_(None))
        if self.access_scope.tenant_id is not None and READ_ASSET in self.access_scope.permissions:
            visible = or_(
                visible,
                and_(
                    entities.c.visibility == "tenant",
                    entities.c.tenant_id == self.access_scope.tenant_id,
                ),
            )
        statement = (
            select(entity_aliases.c.entity_id)
            .join(entities)
            .where(
                visible,
                entity_aliases.c.alias_value == alias_value,
                entity_aliases.c.status == "validated",
                entity_aliases.c.created_at <= known_at,
                or_(entity_aliases.c.valid_from.is_(None), entity_aliases.c.valid_from <= known_at),
                or_(entity_aliases.c.valid_to.is_(None), entity_aliases.c.valid_to > known_at),
            )
            .distinct()
            .order_by(entity_aliases.c.entity_id)
        )
        return tuple(self.session.execute(statement).scalars().all())

    def _apply_relation(
        self,
        relation: ClaimRelation,
        resolved_ids: dict[str, str],
        scope: VisibilityScope,
        changed_at: datetime,
    ) -> None:
        left_id = resolved_ids.get(relation.left_claim_id.value, relation.left_claim_id.value)
        right_id = resolved_ids.get(relation.right_claim_id.value, relation.right_claim_id.value)
        if left_id == right_id:
            raise KnowledgePublicationError("self relation is invalid")
        rows = (
            self.session.execute(
                select(claims).where(
                    claims.c.claim_id.in_((left_id, right_id)),
                    self._visible_claims(),
                )
            )
            .mappings()
            .all()
        )
        if len(rows) != 2:
            raise CrossTenantAccessError("resource not found")
        by_id = {str(row["claim_id"]): row for row in rows}
        left, right = by_id[left_id], by_id[right_id]
        for row in (left, right):
            if row["visibility"] != scope.visibility or row["tenant_id"] != scope.tenant_id:
                raise KnowledgePublicationError("relation scope differs from publication")
        if left["subject"] != right["subject"] or left["predicate"] != right["predicate"]:
            raise KnowledgePublicationError("relation requires matching subject and predicate")
        for row in (left, right):
            if (
                row["claim_origin"] == "model_hypothesis"
                or row["provenance_status"] != "source_verified"
                or row["claim_status"] not in {"supported", "disputed"}
            ):
                raise KnowledgePublicationError("relation requires verified factual claims")
        assertion_rows = self.session.execute(
            select(claim_assertions.c.claim_id, claim_assertions.c.scoring_authority).where(
                claim_assertions.c.claim_id.in_((left_id, right_id))
            )
        ).all()
        authorities = {row[0]: row[1] for row in assertion_rows}
        if (
            left_id not in authorities
            or right_id not in authorities
            or authorities[left_id] != authorities[right_id]
        ):
            raise KnowledgePublicationError("different scoring authorities remain parallel")
        left_value, right_value = left["object_json"], right["object_json"]
        if isinstance(left_value, dict) and isinstance(right_value, dict):
            if left_value.get("kind") == right_value.get("kind") == "version_range" and (
                left_value.get("branch") != right_value.get("branch")
                or left_value.get("ecosystem") != right_value.get("ecosystem")
            ):
                raise KnowledgePublicationError("different version branches remain parallel")
            if left_value.get("kind") == right_value.get("kind") == "score" and left_value.get(
                "authority"
            ) != right_value.get("authority"):
                raise KnowledgePublicationError("different scoring authorities remain parallel")
        if relation.relation_type == "supersedes":
            if left["claim_status"] != "supported" or right["claim_status"] != "supported":
                raise KnowledgePublicationError("supersede requires supported claims")
            left_source: str = self.session.execute(
                select(claim_assertions.c.source_id).where(
                    claim_assertions.c.claim_id == left_id,
                )
            ).scalar_one()
            right_source: str = self.session.execute(
                select(claim_assertions.c.source_id).where(
                    claim_assertions.c.claim_id == right_id,
                )
            ).scalar_one()
            if (
                left_source != right_source
                or left["source_revision_id"] == right["source_revision_id"]
            ):
                raise KnowledgePublicationError("supersede requires explicit source revision")
            revisions = (
                self.session.execute(
                    select(document_revisions).where(
                        document_revisions.c.revision_id.in_(
                            (left["source_revision_id"], right["source_revision_id"])
                        ),
                    )
                )
                .mappings()
                .all()
            )
            by_revision = {row["revision_id"]: row for row in revisions}
            old_revision = by_revision[left["source_revision_id"]]
            new_revision = by_revision[right["source_revision_id"]]
            if (
                old_revision["document_id"] != new_revision["document_id"]
                or old_revision["revision_number"] >= new_revision["revision_number"]
            ):
                raise KnowledgePublicationError(
                    "supersede requires a later revision of one document"
                )
            self.session.execute(
                update(claims)
                .where(claims.c.claim_id == left_id)
                .values(
                    claim_status="superseded",
                    is_current=False,
                )
            )
            self._record_status(left_id, "superseded", relation.reason, changed_at)
        else:
            if {left["condition_value"], right["condition_value"]} != {"true", "false"}:
                raise KnowledgePublicationError("dispute requires incompatible conditions")
            if left["asserted_at"] != right["asserted_at"]:
                raise KnowledgePublicationError("different effective times remain parallel")
            for claim_id in (left_id, right_id):
                self.session.execute(
                    update(claims)
                    .where(claims.c.claim_id == claim_id)
                    .values(
                        claim_status="disputed",
                    )
                )
                self._record_status(claim_id, "disputed", relation.reason, changed_at)
        self.session.execute(
            claim_relations.insert().values(
                relation_id=str(uuid4()),
                left_claim_id=left_id,
                right_claim_id=right_id,
                relation_type=relation.relation_type,
                reason=relation.reason,
                created_at=changed_at,
            )
        )

    def get_claim(self, claim_id: str, *, known_at: datetime | None = None) -> ClaimRecord:
        statement = select(claims).where(claims.c.claim_id == claim_id, self._visible_claims())
        if known_at is not None:
            if known_at.tzinfo is None:
                raise KnowledgePublicationError("history timestamp must be timezone aware")
            statement = statement.where(claims.c.created_at <= known_at)
        row = self.session.execute(statement).mappings().first()
        if row is None:
            raise CrossTenantAccessError("resource not found")
        status = None
        if known_at is not None:
            status = self.session.execute(
                select(claim_status_history.c.status)
                .where(
                    claim_status_history.c.claim_id == claim_id,
                    claim_status_history.c.changed_at <= known_at,
                )
                .order_by(
                    claim_status_history.c.changed_at.desc(),
                    claim_status_history.c.transition_sequence.desc(),
                )
                .limit(1)
            ).scalar_one_or_none()
        return _claim_from_row(row, status)

    def get_evidence(self, evidence_id: str) -> StoredEvidence:
        self.access_scope.requires(READ_PUBLIC)
        visible = and_(evidence.c.visibility == "public", evidence.c.tenant_id.is_(None))
        if self.access_scope.tenant_id is not None and READ_ASSET in self.access_scope.permissions:
            visible = or_(
                visible,
                and_(
                    evidence.c.visibility == "tenant",
                    evidence.c.tenant_id == self.access_scope.tenant_id,
                ),
            )
        row = (
            self.session.execute(
                select(evidence, document_revisions.c.document_id)
                .join(
                    document_revisions,
                    document_revisions.c.revision_id == evidence.c.revision_id,
                )
                .where(evidence.c.evidence_id == evidence_id, visible)
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        return StoredEvidence.model_validate(
            {
                "record": {
                    "evidence_id": {"value": row["evidence_id"]},
                    "document_id": {"value": row["document_id"]},
                    "span": {
                        "start_offset": row["start_offset"],
                        "end_offset": row["end_offset"],
                        "locator": row["locator"],
                    },
                    "quote": row["quote"],
                    "supports_claim": row["supports_claim"],
                },
                "revision_id": {"value": row["revision_id"]},
                "block_id": {"value": row["block_id"]} if row["block_id"] is not None else None,
                "scope": {"visibility": row["visibility"], "tenant_id": row["tenant_id"]},
                "quote_sha256": row["quote_sha256"],
                "coordinate_version": row["coordinate_version"],
                "verified_at": row["verified_at"]
                if row["coordinate_version"] == "fulltext_unicode_v1"
                else None,
            }
        )

    def list_current_claims(
        self, *, candidate_ids: tuple[str, ...] | None = None, limit: int = 100
    ) -> tuple[ClaimRecord, ...]:
        """SQL先过滤权限/有效性; 搜索候选与导出共享同一入口。"""
        if not 1 <= limit <= 1000:
            raise KnowledgePublicationError("claim read limit must be between 1 and 1000")
        statement = select(claims).where(
            self._visible_claims(),
            claims.c.is_current.is_(True),
            claims.c.claim_status.in_(("supported", "disputed")),
            claims.c.freshness != "stale",
            claims.c.provenance_status == "source_verified",
        )
        if candidate_ids is not None:
            statement = statement.where(claims.c.claim_id.in_(candidate_ids))
        rows = (
            self.session.execute(statement.order_by(claims.c.claim_id).limit(limit))
            .mappings()
            .all()
        )
        return tuple(_claim_from_row(row) for row in rows)

    def export_current_claims(self, *, limit: int = 100) -> str:
        records = self.list_current_claims(limit=limit)
        return json.dumps(
            [record.model_dump(mode="json") for record in records], ensure_ascii=False
        )
