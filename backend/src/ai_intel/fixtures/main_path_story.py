"""Load one explicit fixture story for the main path. Live mode never opens a database."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from uuid import UUID, uuid4, uuid5

from pydantic import JsonValue
from sqlalchemy import insert, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import auth_sessions
from ai_intel.assessment.conditions import parse_condition_tree
from ai_intel.assessment.persistence_contracts import RuleSupportBinding
from ai_intel.assessment.rule_service import RuleService
from ai_intel.assessment.rules import ConditionRule
from ai_intel.assets.inventory import InventoryService
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.enums import (
    ClaimOrigin,
    ClaimStatus,
    ConditionValue,
    FreshnessStatus,
    RuleStatus,
)
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.models import document_revisions, documents, users
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import event_documents, events
from ai_intel.knowledge.revision_mode import TRUSTED_SOURCE_MODE_POLICY
from ai_intel.knowledge.revisions import (
    SourceRevisionBlock,
    attach_evidence_span,
    register_response_content,
    register_source_revision_blocks,
    save_document_revision,
)
from ai_intel.recommendations.persistence_models import r15_subscriptions
from ai_intel.recommendations.service import RecommendationService
from ai_intel.recommendations.service_contracts import SubscriptionSpec

STORY_SOURCE_NAME = "main-path-story"
ANALYST_USERNAME = "main-path-analyst"
AUTHOR_USERNAME = "main-path-author"
REVIEWER_USERNAME = "main-path-reviewer"
STORY_NAMESPACE = uuid5(UUID("6ba7b811-9dad-11d1-80b4-00c04fd430c8"), "dianzi:main-path-story:v1")
FIXTURE_METADATA: dict[str, JsonValue] = {
    "data_mode": "fixture",
    "data_mode_policy_version": TRUSTED_SOURCE_MODE_POLICY,
}
AFFECTED_VERSION = "1.4.1"
UNAFFECTED_VERSION = "1.4.2"


class FixtureModeRequired(RuntimeError):
    """The synthetic story is refused unless the process is explicitly in fixture mode."""


class StoryIncomplete(RuntimeError):
    """A previous fixture load stopped before every required object existed."""


class StoryReceipt(Protocol):
    """Identifiers only. Passwords and connection strings are never part of a receipt."""

    analyst_username: str
    tenant_id: str
    event_id: str
    evidence_id: str
    affected_asset_id: str
    unaffected_asset_id: str
    rule_id: str
    affected_subscription_id: str
    unaffected_subscription_id: str
    already_present: bool


class MainPathStory:
    """One public event, two versioned assets, one published rule, and two subscriptions."""

    def __init__(
        self,
        *,
        analyst_username: str,
        tenant_id: str,
        event_id: str,
        evidence_id: str,
        affected_asset_id: str,
        unaffected_asset_id: str,
        rule_id: str,
        affected_subscription_id: str,
        unaffected_subscription_id: str,
        already_present: bool,
    ) -> None:
        self.analyst_username = analyst_username
        self.tenant_id = tenant_id
        self.event_id = event_id
        self.evidence_id = evidence_id
        self.affected_asset_id = affected_asset_id
        self.unaffected_asset_id = unaffected_asset_id
        self.rule_id = rule_id
        self.affected_subscription_id = affected_subscription_id
        self.unaffected_subscription_id = unaffected_subscription_id
        self.already_present = already_present

    def public_lines(self) -> tuple[str, ...]:
        """Lines safe to print. They contain no secret and no database URL."""
        state = "already-present" if self.already_present else "created"
        return (
            f"main-path story {state}",
            f"username={self.analyst_username}",
            f"tenant_id={self.tenant_id}",
            f"event_id={self.event_id}",
            f"evidence_id={self.evidence_id}",
            f"affected_asset_id={self.affected_asset_id}",
            f"unaffected_asset_id={self.unaffected_asset_id}",
            f"rule_id={self.rule_id}",
            f"affected_subscription_id={self.affected_subscription_id}",
            f"unaffected_subscription_id={self.unaffected_subscription_id}",
        )


def require_fixture_mode(data_mode: str) -> None:
    """Refuse before any connection when the deployment is not an explicit fixture."""
    if data_mode != "fixture":
        raise FixtureModeRequired("main-path story is refused unless DATA_MODE=fixture")


def _story_id(name: str) -> str:
    return str(uuid5(STORY_NAMESPACE, name))


def _session(engine: Engine, user_id: str) -> str:
    token = f"fixture-session-{uuid4().hex}"
    unused_csrf = "fixture-unused"
    now = datetime.now(UTC)
    with engine.begin() as connection:
        connection.execute(
            insert(auth_sessions).values(
                session_hash=hashlib.sha256(token.encode()).hexdigest(),
                user_id=user_id,
                csrf_token=unused_csrf,
                issued_at=now,
                expires_at=now + timedelta(hours=2),
            )
        )
    return token


def _claim_user(
    engine: Engine,
    username: str,
    tenant_id: str | None,
    role: Role,
    password_hash: str,
) -> str:
    """Bind a deterministic story account, and refuse a username owned by someone else."""
    user_id = _story_id(username)
    with engine.begin() as connection:
        row = (
            connection.execute(
                select(users.c.user_id, users.c.role, users.c.tenant_id).where(
                    users.c.username == username
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            connection.execute(
                insert(users).values(
                    user_id=user_id,
                    username=username,
                    password_hash=password_hash,
                    tenant_id=tenant_id,
                    role=role.value,
                    created_at=datetime.now(UTC),
                )
            )
            return user_id
        if (
            str(row["user_id"]) != user_id
            or row["role"] != role.value
            or row["tenant_id"] != tenant_id
        ):
            raise StoryIncomplete(f"username {username} belongs to a different account")
        if username == ANALYST_USERNAME:
            connection.execute(
                update(users).where(users.c.user_id == user_id).values(password_hash=password_hash)
            )
        return user_id


def _existing_story(engine: Engine) -> MainPathStory | None:
    with engine.connect() as connection:
        source_id = connection.scalar(
            text("SELECT source_id FROM sources WHERE name = :name"),
            {"name": STORY_SOURCE_NAME},
        )
        if source_id is None:
            return None
        event_id = connection.scalar(
            text(
                "SELECT event_documents.event_id FROM event_documents "
                "JOIN document_revisions ON "
                "document_revisions.revision_id = event_documents.revision_id "
                "JOIN documents ON documents.document_id = document_revisions.document_id "
                "WHERE documents.source_id = :source_id LIMIT 1"
            ),
            {"source_id": source_id},
        )
        evidence_id = connection.scalar(
            text(
                "SELECT evidence.evidence_id FROM evidence "
                "JOIN document_revisions ON "
                "document_revisions.revision_id = evidence.revision_id "
                "JOIN documents ON documents.document_id = document_revisions.document_id "
                "WHERE documents.source_id = :source_id LIMIT 1"
            ),
            {"source_id": source_id},
        )
        rule_id = connection.scalar(
            text(
                "SELECT rule_id FROM condition_rule_versions WHERE event_id = :event_id "
                "AND status = 'published' LIMIT 1"
            ),
            {"event_id": event_id},
        )
        analyst_id = connection.scalar(
            select(users.c.user_id).where(users.c.username == ANALYST_USERNAME)
        )
        tenant_id = connection.scalar(
            select(users.c.tenant_id).where(users.c.username == ANALYST_USERNAME)
        )
        assets = connection.execute(
            text(
                "SELECT asset_id::text, display_name FROM assets "
                "WHERE tenant_id = :tenant AND display_name LIKE '主路径夹具资产 %' "
                "ORDER BY display_name"
            ),
            {"tenant": tenant_id},
        ).all()
        subscriptions: list[Any] = []
        if analyst_id is not None:
            subscriptions = list(
                connection.execute(
                    select(r15_subscriptions.c.id, r15_subscriptions.c.spec_payload).where(
                        r15_subscriptions.c.user_id == analyst_id
                    )
                ).all()
            )
    asset_ids = {row[0] for row in assets}
    matched = []
    for subscription_id, payload in subscriptions:
        raw_ids = payload.get("asset_ids") if isinstance(payload, dict) else None
        if isinstance(raw_ids, list) and len(raw_ids) == 1 and raw_ids[0] in asset_ids:
            matched.append((str(subscription_id), str(raw_ids[0])))
    if (
        event_id is None
        or evidence_id is None
        or rule_id is None
        or tenant_id is None
        or len(assets) != 2
        or len(matched) != 2
    ):
        raise StoryIncomplete("main-path story exists but is missing a required object")
    affected = next(row[0] for row in assets if AFFECTED_VERSION in row[1])
    unaffected = next(row[0] for row in assets if UNAFFECTED_VERSION in row[1])
    affected_subscription = next(item[0] for item in matched if item[1] == affected)
    unaffected_subscription = next(item[0] for item in matched if item[1] == unaffected)
    return MainPathStory(
        analyst_username=ANALYST_USERNAME,
        tenant_id=str(tenant_id),
        event_id=str(event_id),
        evidence_id=str(evidence_id),
        affected_asset_id=str(affected),
        unaffected_asset_id=str(unaffected),
        rule_id=str(rule_id),
        affected_subscription_id=affected_subscription,
        unaffected_subscription_id=unaffected_subscription,
        already_present=True,
    )


def load_main_path_story(
    engine: Engine,
    store: ContentStorage,
    *,
    data_mode: str,
    analyst_password: str,
) -> MainPathStory:
    """Write the story only after fixture mode is confirmed. Live mode performs no query."""
    require_fixture_mode(data_mode)
    if not analyst_password:
        raise ValueError("empty password refused")
    existing = _existing_story(engine)
    if existing is not None:
        return existing
    from argon2 import PasswordHasher

    now = datetime.now(UTC)
    tenant_id = _story_id("tenant")
    hasher = PasswordHasher()
    analyst_hash = hasher.hash(analyst_password)
    unused_hash = hasher.hash(uuid4().hex)
    author_id = _claim_user(engine, AUTHOR_USERNAME, None, Role.SYSTEM_ADMIN, unused_hash)
    reviewer_id = _claim_user(engine, REVIEWER_USERNAME, None, Role.SYSTEM_ADMIN, unused_hash)
    analyst_id = _claim_user(engine, ANALYST_USERNAME, tenant_id, Role.TENANT_ADMIN, analyst_hash)
    author_token = _session(engine, author_id)
    reviewer_token = _session(engine, reviewer_id)
    analyst_token = _session(engine, analyst_id)
    author_scope = AccessScope.for_authenticated_user(author_id, None, Role.SYSTEM_ADMIN)
    analyst_scope = AccessScope.for_authenticated_user(analyst_id, tenant_id, Role.TENANT_ADMIN)
    scope = VisibilityScope(visibility="public", tenant_id=None)
    source_id = _story_id("source")
    document_id = _story_id("document")
    event_id = _story_id("event")
    claim_id = _story_id("claim")
    quote = "夹具必要条件：组件 fixture 版本 [1.0,1.4.2)，完整受影响范围。"
    body = "前缀：" + quote + "后缀。"
    payload = body.encode()
    with Session(engine) as session, session.begin():
        session.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,"
                "visibility,tenant_id,created_at) "
                "VALUES (:id,:name,'vendor_advisory','https://example.invalid',"
                "'public',NULL,:time)"
            ),
            {"id": source_id, "name": STORY_SOURCE_NAME, "time": now},
        )
        content = register_response_content(session, store, payload, now)
        session.execute(
            insert(documents).values(
                document_id=document_id,
                source_id=source_id,
                kind="advisory",
                title="主路径夹具公告",
                retrieved_at=now,
                content_hash=content.content_hash,
                visibility="public",
                tenant_id=None,
                schema_version=2,
            )
        )
        revision = save_document_revision(
            session,
            store,
            document_id,
            payload,
            "public",
            None,
            now,
            revision_metadata=FIXTURE_METADATA,
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == revision.revision_id)
            .values(parse_status="parsed")
        )
        block_id = register_source_revision_blocks(
            session,
            revision.revision_id,
            (
                SourceRevisionBlock(
                    0,
                    0,
                    len(body),
                    body,
                    hashlib.sha256(payload).hexdigest(),
                    "paragraph",
                    None,
                    None,
                ),
            ),
            "public",
            None,
            now,
            attach_full_block_evidence=False,
        )[0]
        start = len("前缀：")
        span_id = attach_evidence_span(
            session,
            revision.revision_id,
            start,
            start + len(quote),
            "fixture:block",
            quote,
            True,
            "public",
            None,
            now,
            block_id,
            hashlib.sha256(quote.encode()).hexdigest(),
            now,
        )
        session.execute(
            insert(events).values(
                event_id=event_id,
                event_type="vulnerability",
                title="主路径夹具事件",
                scope_key="public",
                visibility="public",
                tenant_id=None,
                status="active",
                first_seen_at=now,
                business_version=1,
            )
        )
        session.execute(
            insert(event_documents).values(
                event_id=event_id,
                revision_id=revision.revision_id,
                active=True,
                associated_at=now,
            )
        )
        record = ClaimRecord(
            schema_version=2,
            claim_id=Identifier(value=claim_id),
            subject="event:" + event_id,
            predicate="necessary_condition",
            object_value=quote,
            claim_status=ClaimStatus.SUPPORTED,
            claim_origin=ClaimOrigin.SOURCE_EXPLICIT,
            condition_value=ConditionValue.UNKNOWN,
            freshness=FreshnessStatus.UNKNOWN,
            asserted_at=now,
            scope=scope,
        )
        KnowledgeRepository(session, author_scope).publish(
            "fixture-claim-" + claim_id,
            scope,
            (
                ClaimSubmission(
                    record=record,
                    source_id=Identifier(value=source_id),
                    revision_id=Identifier(value=revision.revision_id),
                    json_path="fixture:block",
                    evidence_links=(
                        EvidenceLink(
                            evidence_id=Identifier(value=span_id),
                            support_kind="supports",
                            validation_status="validated",
                        ),
                    ),
                ),
            ),
            created_at=now,
        )
    node = {
        "node_id": "version",
        "kind": "version_in_range",
        "range_complete": True,
        "assertion": {
            "kind": "version_assertion",
            "package_key": "fixture",
            "ecosystem": "PyPI",
            "scheme": "pep440",
            "raw_expression": "[1.0,1.4.2)",
            "intervals": [{"introduced": "1.0", "fixed": "1.4.2"}],
            "comparison_support": "supported",
        },
    }
    rule = ConditionRule(
        rule_id=_story_id("rule"),
        version=1,
        event_id=event_id,
        rule_kind="software_applicability",
        condition_ast=parse_condition_tree(node),
        supporting_claim_ids=(claim_id,),
        source_span_ids=(span_id,),
        scope=scope,
        status=RuleStatus.CANDIDATE,
    )
    binding = RuleSupportBinding(node_id="version", claim_id=claim_id, evidence_id=span_id)
    author_rules = RuleService(engine, author_token, store)
    author_rules.create_candidate(rule, (binding,))
    reviewer_rules = RuleService(engine, reviewer_token, store)
    reviewer_rules.record_leaf_review(
        rule.rule_id,
        1,
        binding,
        decision="supports",
        reason="Fixture reviewer confirms the exact necessary condition and complete range.",
        range_completeness_confirmed=True,
    )
    author_rules.validate(rule.rule_id, 1)
    reviewer_rules.publish(rule.rule_id, 1)
    observed = datetime.now(UTC)
    imports = []
    for version in (AFFECTED_VERSION, UNAFFECTED_VERSION):
        raw = json.dumps(
            {
                "format_version": 1,
                "components": [
                    {"ecosystem": "PyPI", "package_name": "fixture", "version": version}
                ],
            }
        ).encode()
        with Session(engine) as session, session.begin():
            imports.append(
                InventoryService(session, analyst_scope).import_manifest(
                    raw,
                    manifest_format="json_manifest_v1",
                    display_name=f"主路径夹具资产 {version}",
                    source_version="main-path-story-1",
                    observed_at=observed,
                    idempotency_key=f"main-path-story-{version}",
                )
            )
    recommendations = RecommendationService(engine, analyst_token, store, data_mode="fixture")
    subscription_ids = []
    for imported in imports:
        created = recommendations.create_subscription(
            SubscriptionSpec(asset_ids=(UUID(imported.asset_id),))
        )
        subscription_ids.append(str(created.subscription_id))
    return MainPathStory(
        analyst_username=ANALYST_USERNAME,
        tenant_id=tenant_id,
        event_id=event_id,
        evidence_id=span_id,
        affected_asset_id=imports[0].asset_id,
        unaffected_asset_id=imports[1].asset_id,
        rule_id=rule.rule_id,
        affected_subscription_id=subscription_ids[0],
        unaffected_subscription_id=subscription_ids[1],
        already_present=False,
    )
