"""Cookie-authenticated PG subscriptions and immutable, evidence-bound local outputs."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from threading import get_ident
from typing import Literal
from uuid import UUID, uuid4

from pydantic import TypeAdapter
from sqlalchemy import DateTime, case, cast, exists, func, insert, select, tuple_, update
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.orm import Session, SessionTransaction

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.document_read_service import sources
from ai_intel.assessment.assessment_persistence import assessment_results
from ai_intel.assessment.assessment_service import AssessmentService
from ai_intel.assessment.rule_persistence import condition_rule_versions
from ai_intel.assets.inventory_models import assets
from ai_intel.domain.access import (
    READ_ASSET,
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
)
from ai_intel.domain.values import UtcTimestamp
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService, GraphReadInputs
from ai_intel.knowledge.models import document_revisions, documents
from ai_intel.knowledge.persistence_models import event_documents, events
from ai_intel.recommendations.candidate_loader import (
    CandidateLoader,
    LoadedCandidates,
    visible_clause,
)
from ai_intel.recommendations.contracts import (
    MAX_CANDIDATES,
    MAX_INPUT_EVENTS,
    POLICY_VERSION,
    RecommendationCandidate,
    RecommendationKey,
)
from ai_intel.recommendations.persistence_models import (
    r15_generations,
    r15_recommendations,
    r15_reports,
    r15_subscriptions,
)
from ai_intel.recommendations.policy import generate_recommendation_candidates, require_item_budget
from ai_intel.recommendations.report_builder import build_report_candidate
from ai_intel.recommendations.service_contracts import (
    CandidateGap,
    CurrentStatus,
    GenerationContent,
    GenerationReceipt,
    PreparedGeneration,
    RecommendationConflictError,
    RecommendationIntegrityError,
    RecommendationPage,
    RecommendationRecord,
    ReportPage,
    ReportReceipt,
    StoredReportContent,
    SubscriptionPage,
    SubscriptionRecord,
    SubscriptionSpec,
    content_sha256,
)


def require_version(value: int) -> None:
    if type(value) is not int or value < 1:
        raise ValueError("subscription_version_invalid")


class RecommendationCursorError(ValueError):
    """A UUID cursor must locate a visible row within the requested owner scope."""


def verify_payload(payload: object, expected_sha256: str) -> None:
    if content_sha256(payload) != expected_sha256:
        raise RecommendationIntegrityError("stored_payload_hash_mismatch")


def generation_input_digest(
    subscription: SubscriptionRecord,
    scope: AccessScope,
    loaded: LoadedCandidates,
    cutoff: datetime,
    event_ids: tuple[UUID, ...],
    max_candidates: int,
    existing_keys: tuple[RecommendationKey, ...],
    input_scope_partial: bool = False,
) -> str:
    payload: dict[str, object] = {
        "subscription": subscription.model_dump(mode="json"),
        "actor": [scope.user_id, scope.tenant_id, scope.role.value, scope.permission_version],
        "facts": loaded.facts_sha256,
        "epochs": loaded.epochs,
        "cutoff": cutoff.isoformat(),
        "event_ids": [str(value) for value in event_ids],
        "max_candidates": max_candidates,
        "policy": POLICY_VERSION,
        "existing_keys": [key.model_dump(mode="json") for key in existing_keys],
    }
    if input_scope_partial:
        payload["input_scope_partial"] = True
    return content_sha256(payload)


class RecommendationService:
    """Every public operation locks the current cookie/user and then the owner's PG row.

    PreparedGeneration is an in-process server receipt, never a public body decoder.
    generate is the public/worker operation; historical cutoffs only come from saved rows.
    No method sends messages, invokes models, creates schema or commits nested sessions.
    """

    def __init__(
        self,
        engine: Engine,
        session_token: str,
        content_store: ContentStorage,
        *,
        data_mode: Literal["live", "fixture"] = "live",
    ) -> None:
        if data_mode not in {"live", "fixture"}:
            raise ValueError("invalid_data_mode")
        self.engine = engine
        self._session_token = session_token
        self.content_store = content_store
        self.data_mode = data_mode
        self.assessor = AssessmentService(engine, session_token, content_store)
        self._request_session: Session | None = None
        self._request_thread: int | None = None
        self._request_transaction: SessionTransaction | None = None

    @contextmanager
    def in_transaction(self, session: Session) -> Iterator[RecommendationService]:
        """A fresh request-only binding never begins, commits or outlives the caller's txn."""
        transaction = session.get_transaction()
        if (
            self._request_thread is not None
            or not session.in_transaction()
            or session.in_nested_transaction()
            or session.get_bind() is not self.engine
            or transaction is None
            or not transaction.is_active
        ):
            raise ValueError("trusted_request_transaction_required")
        bound = RecommendationService(
            self.engine, self._session_token, self.content_store, data_mode=self.data_mode
        )
        bound._request_session = session
        bound._request_thread = get_ident()
        bound._request_transaction = transaction
        try:
            yield bound
        finally:
            bound._request_session = None
            bound._request_thread = -1
            bound._request_transaction = None

    @contextmanager
    def _transaction(self) -> Iterator[Session]:
        if self._request_thread is not None:
            if (
                self._request_thread != get_ident()
                or self._request_session is None
                or not self._request_session.in_transaction()
                or not self._request_session.is_active
                or self._request_session.in_nested_transaction()
                or self._request_transaction is None
                or not self._request_transaction.is_active
                or self._request_session.get_transaction() is not self._request_transaction
            ):
                raise ValueError("trusted_request_transaction_expired")
            yield self._request_session
            return
        with Session(self.engine) as session, session.begin():
            yield session

    def _scope(self, session: Session) -> AccessScope:
        scope = lock_authenticated_scope(
            session.connection(), self._session_token, datetime.now(UTC)
        )
        scope.requires(READ_PUBLIC)
        if scope.tenant_id is None:
            raise PermissionDeniedError("subscription_tenant_required")
        return scope

    def _loader(self, session: Session, scope: AccessScope) -> CandidateLoader:
        return CandidateLoader(session, scope, self.assessor, self.content_store, self.data_mode)

    @staticmethod
    def _subscription(
        session: Session, scope: AccessScope, subscription_id: UUID
    ) -> SubscriptionRecord:
        row = (
            session.execute(
                select(r15_subscriptions)
                .where(
                    r15_subscriptions.c.id == str(subscription_id),
                    r15_subscriptions.c.tenant_id == scope.tenant_id,
                    r15_subscriptions.c.user_id == scope.user_id,
                )
                .with_for_update()
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        verify_payload(row["spec_payload"], row["spec_sha256"])
        spec = SubscriptionSpec.model_validate(row["spec_payload"])
        if spec.enabled != row["enabled"] or spec.model_dump(mode="json") != row["spec_payload"]:
            raise RecommendationIntegrityError("stored_subscription_spec_mismatch")
        record = SubscriptionRecord(
            subscription_id=UUID(row["id"]),
            tenant_id=row["tenant_id"],
            user_id=row["user_id"],
            version=row["version"],
            spec=spec,
            spec_sha256=row["spec_sha256"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
        RecommendationService._lock_assets(session, scope, tuple(map(str, spec.asset_ids)))
        return record

    @staticmethod
    def _lock_assets(session: Session, scope: AccessScope, asset_ids: tuple[str, ...]) -> None:
        """Asset interest remains private even when disabled, empty or historically inactive."""
        if asset_ids:
            scope.requires(READ_ASSET)
        for asset_id in sorted(set(asset_ids)):
            row = session.execute(
                select(assets.c.asset_id)
                .where(
                    assets.c.asset_id == asset_id,
                    assets.c.tenant_id == scope.tenant_id,
                )
                .with_for_update(read=True)
            ).first()
            if row is None:
                raise CrossTenantAccessError("resource not found")

    @staticmethod
    def _expected(subscription: SubscriptionRecord, expected_version: int) -> None:
        require_version(expected_version)
        if subscription.version != expected_version:
            raise RecommendationConflictError("subscription_version_changed")

    def create_subscription(self, spec: SubscriptionSpec) -> SubscriptionRecord:
        spec = SubscriptionSpec.model_validate(spec.model_dump(mode="python"))
        now = datetime.now(UTC)
        with self._transaction() as session:
            scope = self._scope(session)
            if scope.tenant_id is None:
                raise PermissionDeniedError("subscription_tenant_required")
            record = SubscriptionRecord(
                subscription_id=uuid4(),
                tenant_id=scope.tenant_id,
                user_id=scope.user_id,
                version=1,
                spec=spec,
                spec_sha256=content_sha256(spec.model_dump(mode="json")),
                created_at=now,
                updated_at=now,
            )
            self._loader(session, scope).validate_assets(record)
            session.execute(
                insert(r15_subscriptions).values(
                    id=str(record.subscription_id),
                    tenant_id=record.tenant_id,
                    user_id=record.user_id,
                    version=record.version,
                    enabled=spec.enabled,
                    spec_payload=spec.model_dump(mode="json"),
                    spec_sha256=record.spec_sha256,
                    created_at=now,
                    updated_at=now,
                )
            )
            return record

    def read_subscription(self, subscription_id: UUID) -> SubscriptionRecord:
        with self._transaction() as session:
            scope = self._scope(session)
            record = self._subscription(session, scope, subscription_id)
            self._loader(session, scope).validate_assets(record)
            return record

    def list_subscriptions(
        self, *, limit: int = MAX_CANDIDATES, cursor: UUID | None = None
    ) -> SubscriptionPage:
        require_item_budget(limit)
        with self._transaction() as session:
            scope = self._scope(session)
            query = select(r15_subscriptions.c.id).where(
                r15_subscriptions.c.tenant_id == scope.tenant_id,
                r15_subscriptions.c.user_id == scope.user_id,
            )
            if cursor is not None:
                self._subscription(session, scope, cursor)
                query = query.where(r15_subscriptions.c.id > str(cursor))
            identifiers: list[str] = list(
                session.scalars(query.order_by(r15_subscriptions.c.id).limit(limit + 1))
            )
            records = tuple(
                self._subscription(session, scope, UUID(value)) for value in identifiers[:limit]
            )
            for record in records:
                self._loader(session, scope).validate_assets(record)
            return SubscriptionPage(
                items=records,
                next_cursor=UUID(identifiers[limit - 1]) if len(identifiers) > limit else None,
            )

    def replace_subscription(
        self, subscription_id: UUID, *, expected_version: int, spec: SubscriptionSpec
    ) -> SubscriptionRecord:
        require_version(expected_version)
        spec = SubscriptionSpec.model_validate(spec.model_dump(mode="python"))
        with self._transaction() as session:
            scope = self._scope(session)
            previous = self._subscription(session, scope, subscription_id)
            self._expected(previous, expected_version)
            now = datetime.now(UTC)
            record = previous.model_copy(
                update={
                    "version": previous.version + 1,
                    "spec": spec,
                    "spec_sha256": content_sha256(spec.model_dump(mode="json")),
                    "updated_at": now,
                }
            )
            self._loader(session, scope).validate_assets(record)
            session.execute(
                update(r15_subscriptions)
                .where(
                    r15_subscriptions.c.id == str(subscription_id),
                    r15_subscriptions.c.version == expected_version,
                )
                .values(
                    version=record.version,
                    enabled=spec.enabled,
                    spec_payload=spec.model_dump(mode="json"),
                    spec_sha256=record.spec_sha256,
                    updated_at=now,
                )
            )
            return record

    def set_enabled(
        self, subscription_id: UUID, *, expected_version: int, enabled: bool
    ) -> SubscriptionRecord:
        require_version(expected_version)
        if type(enabled) is not bool:
            raise ValueError("subscription_enabled_invalid")
        with self._transaction() as session:
            scope = self._scope(session)
            previous = self._subscription(session, scope, subscription_id)
            self._expected(previous, expected_version)
            spec = previous.spec.model_copy(update={"enabled": enabled})
            record = previous.model_copy(
                update={
                    "version": previous.version + 1,
                    "spec": spec,
                    "spec_sha256": content_sha256(spec.model_dump(mode="json")),
                    "updated_at": datetime.now(UTC),
                }
            )
            if enabled:
                self._loader(session, scope).validate_assets(record)
            session.execute(
                update(r15_subscriptions)
                .where(
                    r15_subscriptions.c.id == str(subscription_id),
                    r15_subscriptions.c.version == expected_version,
                )
                .values(
                    version=record.version,
                    enabled=enabled,
                    spec_payload=spec.model_dump(mode="json"),
                    spec_sha256=record.spec_sha256,
                    updated_at=record.updated_at,
                )
            )
            return record

    @staticmethod
    def _existing_keys(
        session: Session, subscription: SubscriptionRecord, loaded: LoadedCandidates
    ) -> tuple[RecommendationKey, ...]:
        material = {item.event_id: item.material_version for item in loaded.events}
        rows = session.execute(
            select(r15_recommendations.c.event_id, r15_recommendations.c.material_version)
            .where(
                r15_recommendations.c.subscription_id == str(subscription.subscription_id),
                r15_recommendations.c.tenant_id == subscription.tenant_id,
                r15_recommendations.c.user_id == subscription.user_id,
                r15_recommendations.c.event_id.in_(material),
            )
            .order_by(r15_recommendations.c.event_id, r15_recommendations.c.material_version)
        ).all()
        return tuple(
            RecommendationKey(
                subscription_id=str(subscription.subscription_id),
                event_id=row.event_id,
                material_version=row.material_version,
            )
            for row in rows
            if material.get(row.event_id) == row.material_version
        )

    @staticmethod
    def _stable_observations(
        session: Session, subscription: SubscriptionRecord, loaded: LoadedCandidates
    ) -> LoadedCandidates:
        """Re-reading an unchanged receipt cannot move an already saved first material time."""
        material = {item.event_id: item.material_version for item in loaded.events}
        rows = session.execute(
            select(r15_recommendations).where(
                r15_recommendations.c.subscription_id == str(subscription.subscription_id),
                r15_recommendations.c.tenant_id == subscription.tenant_id,
                r15_recommendations.c.user_id == subscription.user_id,
                r15_recommendations.c.event_id.in_(material),
            )
        ).mappings()
        original = {}
        for row in rows:
            if material.get(row["event_id"]) == row["material_version"]:
                original[row["event_id"]] = RecommendationService._candidate(row)
        events = tuple(
            item.model_copy(
                update={
                    "observed_at": original[item.event_id].observed_at,
                    "valid_from": original[item.event_id].valid_from,
                }
            )
            if item.event_id in original
            else item
            for item in loaded.events
        )
        return LoadedCandidates(
            events, loaded.gaps, loaded.epochs, loaded.facts_sha256, loaded.partial
        )

    def prepare_generation(
        self,
        subscription_id: UUID,
        *,
        expected_version: int,
        event_ids: tuple[UUID, ...],
        max_candidates: int = MAX_CANDIDATES,
        _input_scope_partial: bool = False,
    ) -> PreparedGeneration:
        require_version(expected_version)
        require_item_budget(max_candidates)
        event_ids = tuple(sorted(event_ids))
        if len(event_ids) > MAX_INPUT_EVENTS or len(set(event_ids)) != len(event_ids):
            raise ValueError("event_input_budget_or_identity_invalid")
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, subscription_id)
            self._expected(subscription, expected_version)
            if not subscription.spec.enabled:
                event_ids = ()
            cutoff = datetime.now(UTC)
            loaded = self._loader(session, scope).load(subscription, event_ids, cutoff)
            loaded = self._stable_observations(session, subscription, loaded)
            existing_keys = self._existing_keys(session, subscription, loaded)
            return PreparedGeneration(
                subscription_id=subscription_id,
                subscription_version=subscription.version,
                subscription_sha256=subscription.spec_sha256,
                actor_user_id=scope.user_id,
                actor_tenant_id=subscription.tenant_id,
                actor_role=scope.role,
                permission_version=scope.permission_version,
                cutoff_at=cutoff,
                event_ids=event_ids,
                max_candidates=max_candidates,
                scope_epochs=loaded.epochs,
                input_sha256=generation_input_digest(
                    subscription,
                    scope,
                    loaded,
                    cutoff,
                    event_ids,
                    max_candidates,
                    existing_keys,
                    _input_scope_partial,
                ),
                existing_keys=existing_keys,
            )

    @staticmethod
    def _generation_content(row: RowMapping) -> GenerationContent:
        verify_payload(row["result_payload"], row["content_sha256"])
        content = GenerationContent.model_validate(row["result_payload"])
        if content.model_dump(mode="json") != row["result_payload"] or (
            str(content.subscription.subscription_id),
            content.subscription.tenant_id,
            content.subscription.user_id,
            content.subscription.version,
            content.batch.cutoff_at,
            content.input_sha256,
        ) != (
            row["subscription_id"],
            row["tenant_id"],
            row["user_id"],
            row["subscription_version"],
            row["cutoff_at"],
            row["input_sha256"],
        ):
            raise RecommendationIntegrityError("stored_generation_binding_mismatch")
        return content

    def _generation_asset_ids(
        self,
        session: Session,
        scope: AccessScope,
        subscription_id: UUID,
        generation_ids: tuple[str, ...],
    ) -> tuple[UUID, ...]:
        asset_ids: set[UUID] = set()
        for generation_id in sorted(set(generation_ids)):
            row = (
                session.execute(
                    select(r15_generations).where(
                        r15_generations.c.id == generation_id,
                        r15_generations.c.subscription_id == str(subscription_id),
                        r15_generations.c.tenant_id == scope.tenant_id,
                        r15_generations.c.user_id == scope.user_id,
                    )
                )
                .mappings()
                .one()
            )
            asset_ids.update(self._generation_content(row).subscription.spec.asset_ids)
        return tuple(sorted(asset_ids, key=str))

    @staticmethod
    def _generation_receipt(
        session: Session, row: RowMapping, *, reused: bool
    ) -> GenerationReceipt:
        content = RecommendationService._generation_content(row)
        saved_rows = list(
            session.execute(
                select(r15_recommendations)
                .where(
                    r15_recommendations.c.generation_id == row["id"],
                    r15_recommendations.c.subscription_id == row["subscription_id"],
                    r15_recommendations.c.tenant_id == row["tenant_id"],
                    r15_recommendations.c.user_id == row["user_id"],
                )
                .order_by(r15_recommendations.c.id)
            ).mappings()
        )
        candidates = {item.key: item for item in content.batch.candidates}
        if len(saved_rows) != len(candidates):
            raise RecommendationIntegrityError("stored_generation_recommendation_count_mismatch")
        for saved in saved_rows:
            candidate = RecommendationService._candidate(saved)
            if candidates.get(candidate.key) != candidate:
                raise RecommendationIntegrityError(
                    "stored_generation_recommendation_binding_mismatch"
                )
        identifiers = tuple(UUID(saved["id"]) for saved in saved_rows)
        return GenerationReceipt(
            generation_id=UUID(row["id"]),
            content_sha256=row["content_sha256"],
            content=content,
            recommendation_ids=identifiers,
            reused=reused,
        )

    def commit_generation(
        self, prepared: PreparedGeneration, *, _input_scope_partial: bool = False
    ) -> GenerationReceipt:
        prepared = PreparedGeneration.model_validate(prepared.model_dump(mode="python"))
        TypeAdapter(UtcTimestamp).validate_python(prepared.cutoff_at)
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, prepared.subscription_id)
            self._expected(subscription, prepared.subscription_version)
            if (
                scope.user_id,
                scope.tenant_id,
                scope.role,
                scope.permission_version,
                subscription.spec_sha256,
            ) != (
                prepared.actor_user_id,
                prepared.actor_tenant_id,
                prepared.actor_role,
                prepared.permission_version,
                prepared.subscription_sha256,
            ):
                raise RecommendationConflictError("generation_actor_or_config_changed")
            if prepared.cutoff_at > datetime.now(UTC):
                raise RecommendationConflictError("generation_cutoff_in_future")
            loaded = self._loader(session, scope).load(
                subscription, prepared.event_ids, prepared.cutoff_at
            )
            loaded = self._stable_observations(session, subscription, loaded)
            digest = generation_input_digest(
                subscription,
                scope,
                loaded,
                prepared.cutoff_at,
                prepared.event_ids,
                prepared.max_candidates,
                prepared.existing_keys,
                _input_scope_partial,
            )
            if digest != prepared.input_sha256 or loaded.epochs != prepared.scope_epochs:
                raise RecommendationConflictError("generation_inputs_changed")
            previous = (
                session.execute(
                    select(r15_generations).where(
                        r15_generations.c.subscription_id == str(subscription.subscription_id),
                        r15_generations.c.tenant_id == scope.tenant_id,
                        r15_generations.c.user_id == scope.user_id,
                        r15_generations.c.subscription_version == subscription.version,
                        r15_generations.c.input_sha256 == digest,
                        r15_generations.c.policy_version == POLICY_VERSION,
                    )
                )
                .mappings()
                .first()
            )
            if previous is not None:
                return self._generation_receipt(session, previous, reused=True)
            if self._existing_keys(session, subscription, loaded) != prepared.existing_keys:
                raise RecommendationConflictError("generation_delivery_state_changed")
            batch = generate_recommendation_candidates(
                subscription.policy_subscription(),
                loaded.events,
                cutoff_at=prepared.cutoff_at,
                max_candidates=prepared.max_candidates,
                existing_keys=prepared.existing_keys,
            )
            report_batch = generate_recommendation_candidates(
                subscription.policy_subscription(),
                loaded.events,
                cutoff_at=prepared.cutoff_at,
                max_candidates=prepared.max_candidates,
            )
            content = GenerationContent(
                subscription=subscription,
                batch=batch,
                report_batch=report_batch,
                gaps=loaded.gaps
                + ((CandidateGap(code="input_scope_partial"),) if _input_scope_partial else ()),
                event_ids=prepared.event_ids,
                scope_epochs=loaded.epochs,
                input_sha256=digest,
                material_versions={item.event_id: item.material_version for item in loaded.events},
                partial=batch.partial
                or report_batch.partial
                or loaded.partial
                or _input_scope_partial,
                data_mode=self.data_mode,
            )
            generation_id = uuid4()
            now = datetime.now(UTC)
            payload = content.model_dump(mode="json")
            session.execute(
                insert(r15_generations).values(
                    id=str(generation_id),
                    subscription_id=str(subscription.subscription_id),
                    tenant_id=scope.tenant_id,
                    user_id=scope.user_id,
                    subscription_version=subscription.version,
                    cutoff_at=prepared.cutoff_at,
                    input_sha256=digest,
                    policy_version=POLICY_VERSION,
                    scope_epochs=loaded.epochs,
                    result_payload=payload,
                    content_sha256=content_sha256(payload),
                    created_at=now,
                )
            )
            recommendation_ids: list[UUID] = []
            for candidate in batch.candidates:
                identifier = uuid4()
                candidate_payload = candidate.model_dump(mode="json")
                session.execute(
                    insert(r15_recommendations).values(
                        id=str(identifier),
                        subscription_id=str(subscription.subscription_id),
                        tenant_id=scope.tenant_id,
                        user_id=scope.user_id,
                        generation_id=str(generation_id),
                        event_id=candidate.key.event_id,
                        material_version=candidate.key.material_version,
                        payload=candidate_payload,
                        content_sha256=content_sha256(candidate_payload),
                        created_at=now,
                        read_at=None,
                        current_status="current",
                        current_reason="current_inputs_verified",
                        current_checked_at=now,
                    )
                )
                recommendation_ids.append(identifier)
            return GenerationReceipt(
                generation_id=generation_id,
                content_sha256=content_sha256(payload),
                content=content,
                recommendation_ids=tuple(recommendation_ids),
            )

    def generate(
        self,
        subscription_id: UUID,
        *,
        expected_version: int,
        event_ids: tuple[UUID, ...],
        max_candidates: int = MAX_CANDIDATES,
        _input_scope_partial: bool = False,
    ) -> GenerationReceipt:
        prepared = self.prepare_generation(
            subscription_id,
            expected_version=expected_version,
            event_ids=event_ids,
            max_candidates=max_candidates,
            _input_scope_partial=_input_scope_partial,
        )
        return self.commit_generation(prepared, _input_scope_partial=_input_scope_partial)

    @staticmethod
    def _current_event_ids(session: Session, scope: AccessScope) -> tuple[UUID, ...]:
        """Bounded server roster respects each existing event and source parent ACL."""
        parent = (
            event_documents.join(
                document_revisions,
                event_documents.c.revision_id == document_revisions.c.revision_id,
            )
            .join(documents)
            .join(sources, sources.c.source_id == documents.c.source_id)
        )
        visible_parent = exists(
            select(event_documents.c.event_id)
            .select_from(parent)
            .where(
                event_documents.c.event_id == events.c.event_id,
                event_documents.c.active.is_(True),
                document_revisions.c.is_current.is_(True),
                documents.c.kind != "asset_inventory",
                visible_clause(scope, document_revisions),
                visible_clause(scope, documents),
                visible_clause(scope, sources),
            )
        )
        identifiers: list[str] = list(
            session.scalars(
                select(events.c.event_id)
                .where(
                    visible_clause(scope, events),
                    events.c.status == "active",
                    visible_parent,
                )
                .order_by(events.c.first_seen_at.desc(), events.c.event_id)
                .limit(MAX_INPUT_EVENTS + 1)
            )
        )
        return tuple(UUID(value) for value in identifiers)

    def generate_current(
        self, subscription_id: UUID, *, max_candidates: int = MAX_CANDIDATES
    ) -> GenerationReceipt:
        """Only the server selects event scope, current config and stored cutoff."""
        require_item_budget(max_candidates)
        with self._transaction() as session:
            if self._request_thread is None:
                with self.in_transaction(session) as bound:
                    return bound._generate_current_bound(session, subscription_id, max_candidates)
            return self._generate_current_bound(session, subscription_id, max_candidates)

    def _generate_current_bound(
        self, session: Session, subscription_id: UUID, max_candidates: int
    ) -> GenerationReceipt:
        scope = self._scope(session)
        subscription = self._subscription(session, scope, subscription_id)
        roster = self._current_event_ids(session, scope) if subscription.spec.enabled else ()
        partial = len(roster) > MAX_INPUT_EVENTS
        selected = roster[: MAX_INPUT_EVENTS - 1] if partial else roster
        prepared = self.prepare_generation(
            subscription_id,
            expected_version=subscription.version,
            event_ids=selected,
            max_candidates=max_candidates,
            _input_scope_partial=partial,
        )
        if subscription.spec.enabled and roster != self._current_event_ids(session, scope):
            raise RecommendationConflictError("generation_event_scope_changed")
        return self.commit_generation(prepared, _input_scope_partial=partial)

    def read_generation(self, subscription_id: UUID, generation_id: UUID) -> GenerationReceipt:
        """HTTP replay rechecks the entire saved scope, including gaps and empty results."""
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, subscription_id)
            row = (
                session.execute(
                    select(r15_generations).where(
                        r15_generations.c.id == str(generation_id),
                        r15_generations.c.subscription_id == str(subscription_id),
                        r15_generations.c.tenant_id == scope.tenant_id,
                        r15_generations.c.user_id == scope.user_id,
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            receipt = self._generation_receipt(session, row, reused=True)
            content = receipt.content
            self._history_fence(
                session,
                scope,
                content.report_batch.candidates,
                event_ids=content.event_ids,
                asset_ids=content.subscription.spec.asset_ids
                + tuple(gap.asset_id for gap in content.gaps if gap.asset_id is not None),
            )
            self._historical_state(
                session, scope, subscription, content.report_batch.candidates, generation=content
            )
            return receipt

    def _history_fence(
        self,
        session: Session,
        scope: AccessScope,
        candidates: tuple[RecommendationCandidate, ...],
        *,
        event_ids: tuple[UUID, ...] = (),
        asset_ids: tuple[UUID, ...] = (),
    ) -> None:
        """Lock the complete page's asset/source roster before any publication fence."""
        loader = self._loader(session, scope)
        required_assets = sorted(
            {reference.asset_id for candidate in candidates for reference in candidate.assessments}
            | {str(value) for value in asset_ids}
        )
        self._lock_assets(session, scope, tuple(required_assets))
        revision_ids: set[str] = set()
        evidence_ids: set[UUID] = set()
        for candidate in candidates:
            for reason in candidate.reasons:
                evidence_ids.update(item.evidence_id for item in reason.citations)
                revision_ids.update(str(item.revision_id) for item in reason.citations)
            for reference in candidate.assessments:
                evidence_ids.update(UUID(item.evidence_id) for item in reference.evidence)
        for evidence_id in evidence_ids:
            span = loader.reader.read_evidence(evidence_id)
            revision_ids.add(str(span.revision_id))
        event_ids = tuple(
            sorted({UUID(candidate.key.event_id) for candidate in candidates} | set(event_ids))
        )
        inputs = list(
            GraphReadInputs(
                event_id=event_id,
                scope=scope,
                source_ids=(),
                document_ids=(),
                revision_ids=tuple(sorted(revision_ids)),
                claim_ids=(),
                evidence_ids=(),
                block_ids=(),
                assertion_ids=(),
                support_pairs=(),
            )
            for event_id in event_ids
        )
        actual_inputs: list[GraphReadInputs] = []
        for event_id in event_ids:
            reader = EvidenceGraphReadService(session, scope)
            reader.event_graph(event_id)
            if reader.read_inputs is None:
                raise RecommendationIntegrityError("graph_read_fence_unavailable")
            actual_inputs.append(reader.read_inputs)
        loader._lock_parents(event_ids, tuple(inputs + actual_inputs), ())
        for graph_input in actual_inputs:
            EvidenceGraphReadService(session, scope).lock_graph_inputs(
                graph_input.event_id, graph_input
            )

    def _historical_state(
        self,
        session: Session,
        scope: AccessScope,
        subscription: SubscriptionRecord,
        candidates: tuple[RecommendationCandidate, ...],
        *,
        generation: GenerationContent | None = None,
    ) -> tuple[CurrentStatus, str, datetime]:
        """Requires the complete history fence; never rewrites the original payload."""
        loader = self._loader(session, scope)
        stale = bool(
            generation is not None
            and generation.scope_epochs
            and generation.scope_epochs != loader._epochs()
        )
        if generation is not None:
            stale = stale or generation.subscription.spec.model_dump(exclude={"enabled"}) != (
                subscription.spec.model_dump(exclude={"enabled"})
            )
        withdrawn = False
        revision_ids = {
            str(item.revision_id)
            for candidate in candidates
            for reason in candidate.reasons
            for item in reason.citations
        }
        revision_ids.update(
            item.revision_id
            for candidate in candidates
            for reference in candidate.assessments
            for item in reference.evidence
        )
        for revision_id in sorted(revision_ids):
            state, is_withdrawn = loader.revision_state(revision_id)
            withdrawn = withdrawn or is_withdrawn
            stale = stale or not state["current"]
        event_ids = tuple(
            sorted(
                {UUID(candidate.key.event_id) for candidate in candidates}
                | (set(generation.event_ids) if generation is not None else set())
            )
        )
        for event_id in event_ids:
            detail = loader.reader.event_detail(event_id)
            stale = stale or detail.event.status != "active"
            graph = EvidenceGraphReadService(session, scope).event_graph(event_id)
            selectors, gaps, _, _, _ = loader._selectors(event_id, graph, datetime.now(UTC))
            withdrawn = withdrawn or any(gap.code == "source_withdrawn" for gap in gaps)
            for candidate in candidates:
                if candidate.key.event_id != str(event_id):
                    continue
                for reason in candidate.reasons:
                    if reason.claim_id is not None:
                        stale = stale or not any(
                            selector.claim_id == reason.claim_id
                            and selector.selector_value == reason.matched_key
                            and selector.citations == reason.citations
                            for selector in selectors
                        )
                for reference in candidate.assessments:
                    row = (
                        session.execute(
                            select(assessment_results).where(
                                assessment_results.c.assessment_id == reference.assessment_id,
                                assessment_results.c.tenant_id == scope.tenant_id,
                            )
                        )
                        .mappings()
                        .first()
                    )
                    if row is None:
                        raise RecommendationIntegrityError("historical_assessment_unavailable")
                    receipt = self.assessor._read_result(session, scope, row)
                    stale = (
                        stale
                        or receipt.freshness.value != "current"
                        or receipt.input_digest != reference.input_digest
                    )
                    newer_rule = session.scalar(
                        select(condition_rule_versions.c.version)
                        .where(
                            condition_rule_versions.c.rule_id == reference.rule_id,
                            condition_rule_versions.c.version > reference.rule_version,
                            condition_rule_versions.c.status == "published",
                        )
                        .limit(1)
                    )
                    stale = stale or newer_rule is not None
        if withdrawn:
            return "withdrawn", "current_source_withdrawn", datetime.now(UTC)
        if stale:
            return "stale", "historical_inputs_changed", datetime.now(UTC)
        state_reason = (
            "current_inputs_verified"
            if subscription.spec.enabled
            else "subscription_disabled_history_retained"
        )
        return "current", state_reason, datetime.now(UTC)

    @staticmethod
    def _candidate(row: RowMapping) -> RecommendationCandidate:
        verify_payload(row["payload"], row["content_sha256"])
        candidate = RecommendationCandidate.model_validate(row["payload"])
        if candidate.model_dump(mode="json") != row["payload"] or (
            candidate.key.subscription_id,
            candidate.tenant_id,
            candidate.user_id,
            candidate.key.event_id,
            candidate.key.material_version,
        ) != (
            row["subscription_id"],
            row["tenant_id"],
            row["user_id"],
            row["event_id"],
            row["material_version"],
        ):
            raise RecommendationIntegrityError("stored_recommendation_binding_mismatch")
        return candidate

    def list_recommendations(
        self, subscription_id: UUID, *, limit: int = MAX_CANDIDATES, cursor: UUID | None = None
    ) -> RecommendationPage:
        require_item_budget(limit)
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, subscription_id)
            query = select(r15_recommendations).where(
                r15_recommendations.c.subscription_id == str(subscription_id),
                r15_recommendations.c.tenant_id == scope.tenant_id,
                r15_recommendations.c.user_id == scope.user_id,
            )
            priority = r15_recommendations.c.payload["priority_bucket"].as_integer()
            kind = r15_recommendations.c.payload["kind"].as_string()
            rank = case(
                (kind == "prioritize_verification", 0),
                (kind == "supported_risk", 1),
                (kind == "intelligence_update", 2),
                else_=3,
            )
            observed = -func.extract(
                "epoch",
                cast(
                    r15_recommendations.c.payload["observed_at"].as_string(),
                    DateTime(timezone=True),
                ),
            )
            ordering = (
                priority,
                rank,
                observed,
                r15_recommendations.c.event_id,
                r15_recommendations.c.material_version,
                r15_recommendations.c.id,
            )
            if cursor is not None:
                position = session.execute(
                    select(*ordering).where(
                        r15_recommendations.c.id == str(cursor),
                        r15_recommendations.c.subscription_id == str(subscription_id),
                        r15_recommendations.c.tenant_id == scope.tenant_id,
                        r15_recommendations.c.user_id == scope.user_id,
                    )
                ).first()
                if position is None:
                    raise RecommendationCursorError("recommendation_cursor_invalid")
                query = query.where(tuple_(*ordering) > tuple_(*position))
            rows = session.execute(query.order_by(*ordering).limit(limit + 1)).mappings().all()
            records: list[RecommendationRecord] = []
            self._history_fence(
                session,
                scope,
                tuple(self._candidate(row) for row in rows[:limit]),
                asset_ids=self._generation_asset_ids(
                    session,
                    scope,
                    subscription_id,
                    tuple(row["generation_id"] for row in rows[:limit]),
                ),
            )
            for row in rows[:limit]:
                candidate = self._candidate(row)
                status, reason, checked_at = self._historical_state(
                    session, scope, subscription, (candidate,)
                )
                session.execute(
                    update(r15_recommendations)
                    .where(r15_recommendations.c.id == row["id"])
                    .values(
                        current_status=status, current_reason=reason, current_checked_at=checked_at
                    )
                )
                records.append(
                    RecommendationRecord(
                        recommendation_id=UUID(row["id"]),
                        generation_id=UUID(row["generation_id"]),
                        content_sha256=row["content_sha256"],
                        content=candidate,
                        created_at=row["created_at"],
                        read_at=row["read_at"],
                        current_status=status,
                        current_reason=reason,
                        current_checked_at=checked_at,
                    )
                )
            return RecommendationPage(
                items=tuple(records),
                next_cursor=UUID(rows[limit - 1]["id"]) if len(rows) > limit else None,
            )

    def mark_read(
        self, subscription_id: UUID, recommendation_id: UUID, *, _mark_read: bool = True
    ) -> RecommendationRecord:
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, subscription_id)
            row = (
                session.execute(
                    select(r15_recommendations)
                    .where(
                        r15_recommendations.c.id == str(recommendation_id),
                        r15_recommendations.c.subscription_id == str(subscription_id),
                        r15_recommendations.c.tenant_id == scope.tenant_id,
                        r15_recommendations.c.user_id == scope.user_id,
                    )
                    .with_for_update()
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            candidate = self._candidate(row)
            self._history_fence(
                session,
                scope,
                (candidate,),
                asset_ids=self._generation_asset_ids(
                    session,
                    scope,
                    subscription_id,
                    (row["generation_id"],),
                ),
            )
            status, reason, checked_at = self._historical_state(
                session, scope, subscription, (candidate,)
            )
            read_at = (row["read_at"] or checked_at) if _mark_read else row["read_at"]
            session.execute(
                update(r15_recommendations)
                .where(r15_recommendations.c.id == row["id"])
                .values(
                    read_at=read_at,
                    current_status=status,
                    current_reason=reason,
                    current_checked_at=checked_at,
                )
            )
            return RecommendationRecord(
                recommendation_id=recommendation_id,
                generation_id=UUID(row["generation_id"]),
                content_sha256=row["content_sha256"],
                content=candidate,
                created_at=row["created_at"],
                read_at=read_at,
                current_status=status,
                current_reason=reason,
                current_checked_at=checked_at,
            )

    def create_report(
        self,
        subscription_id: UUID,
        generation_id: UUID,
        *,
        frequency: Literal["day", "week"],
        max_items: int = MAX_CANDIDATES,
    ) -> ReportReceipt:
        require_item_budget(max_items)
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, subscription_id)
            row = (
                session.execute(
                    select(r15_generations)
                    .where(
                        r15_generations.c.id == str(generation_id),
                        r15_generations.c.subscription_id == str(subscription_id),
                        r15_generations.c.tenant_id == scope.tenant_id,
                        r15_generations.c.user_id == scope.user_id,
                    )
                    .with_for_update(read=True)
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            content = self._generation_content(row)
            self._history_fence(
                session,
                scope,
                content.report_batch.candidates,
                event_ids=content.event_ids,
                asset_ids=content.subscription.spec.asset_ids
                + tuple(gap.asset_id for gap in content.gaps if gap.asset_id is not None),
            )
            status, reason, checked = self._historical_state(
                session, scope, subscription, content.report_batch.candidates, generation=content
            )
            previous = (
                session.execute(
                    select(r15_reports).where(
                        r15_reports.c.generation_id == str(generation_id),
                        r15_reports.c.frequency == frequency,
                        r15_reports.c.cutoff_at == row["cutoff_at"],
                        r15_reports.c.tenant_id == scope.tenant_id,
                        r15_reports.c.user_id == scope.user_id,
                    )
                )
                .mappings()
                .first()
            )
            if previous is not None:
                saved = self._stored_report(previous)
                if saved.max_items != max_items:
                    raise RecommendationConflictError("report_budget_changed")
                verify_payload(previous["payload"], previous["content_sha256"])
                return ReportReceipt(
                    report_id=UUID(previous["id"]),
                    content_sha256=previous["content_sha256"],
                    content=saved,
                    current_status=status,
                    current_reason=reason,
                    current_checked_at=checked,
                    reused=True,
                )
            report = build_report_candidate(
                content.report_batch,
                frequency=frequency,
                cutoff_at=row["cutoff_at"],
                generated_at=checked,
                max_items=max_items,
            )
            if content.partial and not report.partial:
                report = report.model_copy(
                    update={
                        "partial": True,
                        "stop_reason": "item_budget",
                        "limitations": (
                            *report.limitations,
                            "input_graph_budget_incomplete_see_gaps",
                        ),
                    }
                )
            saved = StoredReportContent(
                report=report,
                generation_id=generation_id,
                event_ids=content.event_ids,
                data_mode=content.data_mode,
                gaps=content.gaps,
                max_items=max_items,
            )
            payload = saved.model_dump(mode="json")
            identifier = uuid4()
            session.execute(
                insert(r15_reports).values(
                    id=str(identifier),
                    subscription_id=str(subscription_id),
                    tenant_id=scope.tenant_id,
                    user_id=scope.user_id,
                    generation_id=str(generation_id),
                    frequency=frequency,
                    cutoff_at=row["cutoff_at"],
                    generated_at=checked,
                    payload=payload,
                    content_sha256=content_sha256(payload),
                    current_status=status,
                    current_reason=reason,
                    current_checked_at=checked,
                )
            )
            return ReportReceipt(
                report_id=identifier,
                content_sha256=content_sha256(payload),
                content=saved,
                current_status=status,
                current_reason=reason,
                current_checked_at=checked,
            )

    def list_reports(
        self, subscription_id: UUID, *, limit: int = MAX_CANDIDATES, cursor: UUID | None = None
    ) -> ReportPage:
        require_item_budget(limit)
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, subscription_id)
            query = select(r15_reports).where(
                r15_reports.c.subscription_id == str(subscription_id),
                r15_reports.c.tenant_id == scope.tenant_id,
                r15_reports.c.user_id == scope.user_id,
            )
            if cursor is not None:
                position = session.scalar(
                    select(r15_reports.c.id).where(
                        r15_reports.c.id == str(cursor),
                        r15_reports.c.subscription_id == str(subscription_id),
                        r15_reports.c.tenant_id == scope.tenant_id,
                        r15_reports.c.user_id == scope.user_id,
                    )
                )
                if position is None:
                    raise RecommendationCursorError("report_cursor_invalid")
                query = query.where(r15_reports.c.id > str(cursor))
            rows = (
                session.execute(query.order_by(r15_reports.c.id).limit(limit + 1)).mappings().all()
            )
            receipts: list[ReportReceipt] = []
            saved_reports = []
            generations: dict[UUID, GenerationContent] = {}
            for row in rows[:limit]:
                verify_payload(row["payload"], row["content_sha256"])
                saved = self._stored_report(row)
                saved_reports.append(saved)
                generations[saved.generation_id] = self._generation_content(
                    session.execute(
                        select(r15_generations).where(
                            r15_generations.c.id == str(saved.generation_id),
                            r15_generations.c.subscription_id == str(subscription_id),
                            r15_generations.c.tenant_id == scope.tenant_id,
                            r15_generations.c.user_id == scope.user_id,
                        )
                    )
                    .mappings()
                    .one()
                )
            all_candidates = tuple(
                candidate
                for saved in saved_reports
                for candidate in saved.report.supported_risks
                + saved.report.verification_items
                + saved.report.excluded_items
                + saved.report.intelligence_updates
            )
            self._history_fence(
                session,
                scope,
                all_candidates,
                event_ids=tuple(
                    {event_id for saved in saved_reports for event_id in saved.event_ids}
                ),
                asset_ids=tuple(
                    {
                        gap.asset_id
                        for saved in saved_reports
                        for gap in saved.gaps
                        if gap.asset_id is not None
                    }
                    | {
                        asset_id
                        for generation in generations.values()
                        for asset_id in generation.subscription.spec.asset_ids
                    }
                ),
            )
            for row in rows[:limit]:
                verify_payload(row["payload"], row["content_sha256"])
                saved = self._stored_report(row)
                generation = generations[saved.generation_id]
                candidates = (
                    saved.report.supported_risks
                    + saved.report.verification_items
                    + saved.report.excluded_items
                    + saved.report.intelligence_updates
                )
                status, reason, checked = self._historical_state(
                    session, scope, subscription, candidates, generation=generation
                )
                receipts.append(
                    ReportReceipt(
                        report_id=UUID(row["id"]),
                        content_sha256=row["content_sha256"],
                        content=saved,
                        current_status=status,
                        current_reason=reason,
                        current_checked_at=checked,
                    )
                )
            return ReportPage(
                items=tuple(receipts),
                next_cursor=UUID(rows[limit - 1]["id"]) if len(rows) > limit else None,
            )

    @staticmethod
    def _stored_report(row: RowMapping) -> StoredReportContent:
        verify_payload(row["payload"], row["content_sha256"])
        saved = StoredReportContent.model_validate(row["payload"])
        if saved.model_dump(mode="json") != row["payload"] or (
            str(saved.generation_id),
            saved.report.subscription_id,
            saved.report.tenant_id,
            saved.report.user_id,
            saved.report.frequency,
            saved.report.cutoff_at,
            saved.report.generated_at,
        ) != (
            row["generation_id"],
            row["subscription_id"],
            row["tenant_id"],
            row["user_id"],
            row["frequency"],
            row["cutoff_at"],
            row["generated_at"],
        ):
            raise RecommendationIntegrityError("stored_report_binding_mismatch")
        return saved

    def read_report(self, subscription_id: UUID, report_id: UUID) -> ReportReceipt:
        with self._transaction() as session:
            scope = self._scope(session)
            subscription = self._subscription(session, scope, subscription_id)
            row = (
                session.execute(
                    select(r15_reports).where(
                        r15_reports.c.id == str(report_id),
                        r15_reports.c.subscription_id == str(subscription_id),
                        r15_reports.c.tenant_id == scope.tenant_id,
                        r15_reports.c.user_id == scope.user_id,
                    )
                )
                .mappings()
                .first()
            )
            if row is None:
                raise CrossTenantAccessError("resource not found")
            saved = self._stored_report(row)
            generation = self._generation_content(
                session.execute(
                    select(r15_generations).where(
                        r15_generations.c.id == str(saved.generation_id),
                        r15_generations.c.subscription_id == str(subscription_id),
                        r15_generations.c.tenant_id == scope.tenant_id,
                        r15_generations.c.user_id == scope.user_id,
                    )
                )
                .mappings()
                .one()
            )
            candidates = (
                saved.report.supported_risks
                + saved.report.verification_items
                + saved.report.excluded_items
                + saved.report.intelligence_updates
            )
            self._history_fence(
                session,
                scope,
                candidates,
                event_ids=saved.event_ids,
                asset_ids=generation.subscription.spec.asset_ids
                + tuple(gap.asset_id for gap in saved.gaps if gap.asset_id is not None),
            )
            status, reason, checked = self._historical_state(
                session,
                scope,
                subscription,
                candidates,
                generation=generation,
            )
            return ReportReceipt(
                report_id=report_id,
                content_sha256=row["content_sha256"],
                content=saved,
                current_status=status,
                current_reason=reason,
                current_checked_at=checked,
            )
