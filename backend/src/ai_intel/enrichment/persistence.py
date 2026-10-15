"""逐维尝试共享PG事实、发布收据与outbox；失败不删除既有事实。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import Field, model_validator
from sqlalchemy import and_, or_, select, text, update
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
from ai_intel.domain.enums import DimensionStatus, FreshnessStatus
from ai_intel.domain.records import StrictRecord
from ai_intel.domain.values import UtcTimestamp, VisibilityScope
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.knowledge.models import evidence
from ai_intel.knowledge.persistence import (
    PublicationReceipt,
    find_prior_publication,
    knowledge_scope_key,
    publication_payload_digest,
    save_change_publication,
)
from ai_intel.knowledge.persistence_models import claim_evidence, claims, event_documents, events


class DimensionPublicationError(ValueError):
    """拒绝无支持、跨范围、过期事件版本或不一致的维度发布。"""


class DimensionSubmission(StrictRecord):
    """内部持久化输入只引用已验证事实，不能直接接收模型的任意值。"""

    event_id: UUID
    dimension: Literal[
        "cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure"
    ]
    status: DimensionStatus
    expected_event_version: int = Field(strict=True, ge=1)
    input_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    claim_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    reference_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    source_ids: tuple[UUID, ...] = Field(default=(), max_length=100)
    searched_at: UtcTimestamp | None = None
    observed_at: UtcTimestamp | None = None
    source_version: str | None = Field(default=None, max_length=200)
    freshness: FreshnessStatus = FreshnessStatus.UNKNOWN
    error_code: str | None = Field(default=None, pattern=r"^[a-z0-9_]{1,120}$")
    last_job_id: UUID | None = None

    @model_validator(mode="after")
    def validate_result_state(self) -> DimensionSubmission:
        if self.freshness == FreshnessStatus.CURRENT and self.observed_at is None:
            raise ValueError("current dimension requires observed_at")
        if self.status in {DimensionStatus.AVAILABLE, DimensionStatus.CONFLICT}:
            minimum = 2 if self.status == DimensionStatus.CONFLICT else 1
            if len(set(self.claim_ids)) < minimum or not self.reference_ids:
                raise ValueError("available or conflicting dimension requires supported claims")
        elif self.claim_ids:
            raise ValueError("unavailable dimension cannot publish new claim references")
        if self.status == DimensionStatus.NOT_FOUND and (
            self.searched_at is None or not self.source_ids
        ):
            raise ValueError("not_found requires a searched source scope and time")
        if self.status in {DimensionStatus.FAILED, DimensionStatus.BLOCKED} and not self.error_code:
            raise ValueError("failed or blocked dimension requires error_code")
        return self


@dataclass(frozen=True)
class SavedDimensionResult:
    result_id: str
    publication: PublicationReceipt
    reused: bool


class DimensionRepository:
    """同Session登记维度状态和变更，调用方决定整体事务提交。"""

    def __init__(self, session: Session, access_scope: AccessScope) -> None:
        self.session = session
        self.scope = access_scope

    def _event(self, event_id: str, *, writing: bool = False) -> RowMapping:
        self.scope.requires(READ_PUBLIC)
        visibility = and_(events.c.visibility == "public", events.c.tenant_id.is_(None))
        if self.scope.tenant_id is not None and READ_ASSET in self.scope.permissions:
            visibility = or_(
                visibility,
                and_(events.c.visibility == "tenant", events.c.tenant_id == self.scope.tenant_id),
            )
        query = select(events).where(events.c.event_id == event_id, visibility)
        if writing:
            query = query.with_for_update()
        row = self.session.execute(query).mappings().first()
        if row is None:
            raise CrossTenantAccessError("resource not found")
        if writing:
            self.scope.requires(
                MANAGE_PUBLIC_SOURCES if row["visibility"] == "public" else WRITE_ASSET
            )
        return row

    def _validate_references(self, submission: DimensionSubmission, scope: VisibilityScope) -> None:
        for source_id in submission.source_ids:
            source_row = self.session.execute(
                text("SELECT visibility,tenant_id FROM sources WHERE source_id=:id"),
                {"id": str(source_id)},
            ).first()
            if source_row is None or (
                source_row[0] == "tenant"
                and (scope.visibility != "tenant" or scope.tenant_id != source_row[1])
            ):
                raise CrossTenantAccessError("resource not found")
        for reference_id in submission.reference_ids:
            reference_row = (
                self.session.execute(
                    select(evidence).where(evidence.c.evidence_id == str(reference_id))
                )
                .mappings()
                .first()
            )
            if reference_row is None or (
                reference_row["visibility"] == "tenant"
                and (scope.visibility != "tenant" or scope.tenant_id != reference_row["tenant_id"])
            ):
                raise CrossTenantAccessError("resource not found")
            associated = self.session.scalar(
                select(event_documents.c.event_id).where(
                    event_documents.c.event_id == str(submission.event_id),
                    event_documents.c.revision_id == reference_row["revision_id"],
                    event_documents.c.active.is_(True),
                )
            )
            if associated is None:
                raise DimensionPublicationError("evidence revision is not active on this event")
        for claim_id in submission.claim_ids:
            claim_row = (
                self.session.execute(select(claims).where(claims.c.claim_id == str(claim_id)))
                .mappings()
                .first()
            )
            if claim_row is None or (
                claim_row["visibility"] == "tenant"
                and (scope.visibility != "tenant" or scope.tenant_id != claim_row["tenant_id"])
            ):
                raise CrossTenantAccessError("resource not found")
            if (
                not claim_row["is_current"]
                or claim_row["claim_status"] not in {"supported", "disputed"}
                or claim_row["claim_origin"] == "model_hypothesis"
                or claim_row["provenance_status"] != "source_verified"
            ):
                raise DimensionPublicationError(
                    "dimension requires a current supported source claim"
                )
            supported = self.session.scalar(
                select(claim_evidence.c.evidence_id)
                .join(evidence, evidence.c.evidence_id == claim_evidence.c.evidence_id)
                .where(
                    claim_evidence.c.claim_id == str(claim_id),
                    claim_evidence.c.evidence_id.in_(tuple(map(str, submission.reference_ids))),
                    claim_evidence.c.validation_status == "validated",
                    claim_evidence.c.support_kind == "supports",
                    evidence.c.supports_claim.is_(True),
                    evidence.c.verified_at.is_not(None),
                )
                .limit(1)
            )
            if supported is None:
                raise DimensionPublicationError("claim is not supported by the submitted evidence")
        if submission.last_job_id is not None:
            job_row = self.session.execute(
                text("SELECT tenant_id FROM job_runs WHERE job_id=:id"),
                {"id": str(submission.last_job_id)},
            ).first()
            if job_row is None or job_row[0] != scope.tenant_id:
                raise CrossTenantAccessError("resource not found")

    def publish(
        self, publication_key: str, submission: DimensionSubmission, recorded_at: datetime
    ) -> SavedDimensionResult:
        """相同请求复用收据；同输入的新尝试保留新历史，旧事件版本拒绝覆盖。"""
        if not publication_key or len(publication_key) > 200 or recorded_at.tzinfo is None:
            raise DimensionPublicationError("bounded publication key and aware timestamp required")
        submission = DimensionSubmission.model_validate(submission.model_dump())
        event = self._event(str(submission.event_id))
        visibility = VisibilityScope(visibility=event["visibility"], tenant_id=event["tenant_id"])
        self.scope.requires(
            MANAGE_PUBLIC_SOURCES if visibility.visibility == "public" else WRITE_ASSET
        )
        key = f"dimension:{submission.event_id}:{submission.dimension}:{publication_key}"
        payload = submission.model_dump(mode="json")
        digest = publication_payload_digest(payload)
        with self.session.begin_nested():
            prior = find_prior_publication(
                self.session, knowledge_scope_key(visibility), key, digest
            )
            if prior is not None:
                result_id = self.session.scalar(
                    select(enrichment_results.c.result_id).where(
                        enrichment_results.c.event_id == str(submission.event_id),
                        enrichment_results.c.dimension == submission.dimension,
                        enrichment_results.c.publication_key == publication_key,
                    )
                )
                if result_id is None:
                    raise DimensionPublicationError("dimension receipt lacks its result")
                return SavedDimensionResult(str(result_id), prior, True)
            locked_event = self._event(str(submission.event_id), writing=True)
            if (
                locked_event["status"] != "active"
                or locked_event["business_version"] != submission.expected_event_version
            ):
                raise DimensionPublicationError("event version changed; revalidation required")
            self._validate_references(submission, visibility)
            result_id = str(uuid4())
            self.session.execute(
                update(enrichment_results)
                .where(
                    enrichment_results.c.event_id == str(submission.event_id),
                    enrichment_results.c.dimension == submission.dimension,
                    enrichment_results.c.is_current.is_(True),
                )
                .values(is_current=False)
            )
            self.session.execute(
                enrichment_results.insert().values(
                    result_id=result_id,
                    event_id=str(submission.event_id),
                    dimension=submission.dimension,
                    status=submission.status.value,
                    claim_ids=list(map(str, submission.claim_ids)),
                    reference_ids=list(map(str, submission.reference_ids)),
                    error_code=submission.error_code,
                    searched_at=submission.searched_at,
                    source_scope=list(map(str, submission.source_ids)),
                    last_job_id=str(submission.last_job_id) if submission.last_job_id else None,
                    input_fingerprint=submission.input_fingerprint,
                    recorded_at=recorded_at,
                    is_current=True,
                    publication_key=publication_key,
                    payload_sha256=digest,
                    event_version=submission.expected_event_version,
                    observed_at=submission.observed_at,
                    source_version=submission.source_version,
                    freshness=submission.freshness.value,
                )
            )
            receipt = save_change_publication(
                self.session,
                visibility,
                key,
                payload,
                digest,
                tuple(map(str, submission.claim_ids)),
                (str(submission.event_id), result_id),
                recorded_at,
                "dimension_result_published",
            )
            return SavedDimensionResult(result_id, receipt, False)

    def read_results(
        self, event_id: str, *, include_history: bool = False
    ) -> tuple[RowMapping, ...]:
        """先按事件权限过滤；旧结果未知来源时间保持NULL，历史不被覆盖。"""
        self._event(event_id)
        query = select(enrichment_results).where(enrichment_results.c.event_id == event_id)
        if not include_history:
            query = query.where(enrichment_results.c.is_current.is_(True))
        return tuple(
            self.session.execute(
                query.order_by(enrichment_results.c.recorded_at, enrichment_results.c.result_id)
            ).mappings()
        )
