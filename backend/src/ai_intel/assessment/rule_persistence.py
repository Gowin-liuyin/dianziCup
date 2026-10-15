"""PG rule tables and bounded source checks; no API, automatic DDL or alternate facts."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Literal

from sqlalchemy import (
    DDL,
    Boolean,
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    event,
    func,
    select,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import RowMapping
from sqlalchemy.orm import Session

from ai_intel.api.knowledge_read_service import sources
from ai_intel.assessment.conditions import (
    AllOf,
    AnyOf,
    EvidenceReference,
    condition_digest,
    iter_condition_nodes,
)
from ai_intel.assessment.persistence_contracts import (
    CheckedSupport,
    RuleInputSnapshot,
    RuleSupportBinding,
    SourceInput,
)
from ai_intel.assessment.rules import (
    DEFINED_PREDICATES,
    ConditionRule,
    RuleLeafSupport,
    RuleValidationPolicy,
    validate_rule,
)
from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    READ_ASSET,
    READ_PUBLIC,
    WRITE_ASSET,
    AccessScope,
    CrossTenantAccessError,
)
from ai_intel.domain.enums import ClaimStatus
from ai_intel.domain.values import VisibilityScope
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.models import (
    TENANT_XOR,
    VISIBILITY_DOMAIN,
    content_objects,
    document_revisions,
    documents,
    evidence,
    metadata,
    scope_epochs,
    text_blocks,
)
from ai_intel.knowledge.persistence import knowledge_scope_key, publication_payload_digest
from ai_intel.knowledge.persistence_models import (
    claim_assertions,
    claim_evidence,
    claims,
    event_documents,
    events,
)

SERVER_RULE_VALIDATION_POLICY = RuleValidationPolicy(
    policy_version="r11-pg-review-policy-1",
    approved_predicates=DEFINED_PREDICATES,
    automatic_publication_enabled=False,
)


class RulePersistenceError(ValueError):
    """Invalid/currently unsupported source inputs are never converted to a safe result."""


condition_rule_versions = Table(
    "condition_rule_versions",
    metadata,
    Column("rule_id", Text, primary_key=True),
    Column("version", Integer, primary_key=True),
    Column("event_id", Text, ForeignKey("events.event_id"), nullable=False),
    Column("visibility", Text, nullable=False),
    Column("tenant_id", Text),
    Column("rule_kind", Text, nullable=False),
    Column("condition_sha256", Text, nullable=False),
    Column("rule_payload", JSONB, nullable=False),
    Column("status", Text, nullable=False),
    Column("author_user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("published_by", Text, ForeignKey("users.user_id")),
    Column("published_at", DateTime(timezone=True)),
    Column("retired_at", DateTime(timezone=True)),
    Column("created_at", DateTime(timezone=True), nullable=False),
    CheckConstraint("version > 0", name="ck_condition_rule_version"),
    CheckConstraint(VISIBILITY_DOMAIN, name="ck_condition_rule_visibility"),
    CheckConstraint(TENANT_XOR, name="ck_condition_rule_tenant"),
    CheckConstraint(
        "rule_kind IN ('software_applicability','observed_path','research_prerequisites')",
        name="ck_condition_rule_kind",
    ),
    CheckConstraint(
        "status IN ('candidate','validated','published','retired')", name="ck_condition_rule_status"
    ),
    CheckConstraint("condition_sha256 ~ '^[0-9a-f]{64}$'", name="ck_rule_condition_digest"),
    CheckConstraint("jsonb_typeof(rule_payload)='object'", name="ck_rule_payload"),
    CheckConstraint(
        "(status IN ('published','retired'))=(published_at IS NOT NULL)",
        name="ck_rule_published_time",
    ),
    CheckConstraint("(status='retired')=(retired_at IS NOT NULL)", name="ck_rule_retired_time"),
    CheckConstraint(
        "published_by IS NULL OR published_by<>author_user_id", name="ck_rule_reviewer"
    ),
)
Index(
    "uq_current_published_rule_family",
    condition_rule_versions.c.rule_id,
    unique=True,
    postgresql_where=condition_rule_versions.c.status == "published",
)

rule_support_bindings = Table(
    "rule_support_bindings",
    metadata,
    Column("rule_id", Text, primary_key=True),
    Column("rule_version", Integer, primary_key=True),
    Column("node_id", Text, primary_key=True),
    Column("claim_id", Text, ForeignKey("claims.claim_id"), primary_key=True),
    Column("evidence_id", Text, ForeignKey("evidence.evidence_id"), primary_key=True),
    Column("condition_sha256", Text, nullable=False),
    ForeignKeyConstraint(
        ["rule_id", "rule_version"],
        ["condition_rule_versions.rule_id", "condition_rule_versions.version"],
        name="fk_rule_support_version",
    ),
    CheckConstraint("condition_sha256 ~ '^[0-9a-f]{64}$'", name="ck_binding_condition_digest"),
)

rule_leaf_reviews = Table(
    "rule_leaf_reviews",
    metadata,
    Column("review_id", Text, primary_key=True),
    Column("rule_id", Text, nullable=False),
    Column("rule_version", Integer, nullable=False),
    Column("node_id", Text, nullable=False),
    Column("claim_id", Text, nullable=False),
    Column("evidence_id", Text, nullable=False),
    Column("input_digest", Text, nullable=False),
    Column("decision", Text, nullable=False),
    Column("range_complete", Boolean, nullable=False),
    Column("reason", Text, nullable=False),
    Column("actor_user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("actor_role", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["rule_id", "rule_version", "node_id", "claim_id", "evidence_id"],
        [
            "rule_support_bindings.rule_id",
            "rule_support_bindings.rule_version",
            "rule_support_bindings.node_id",
            "rule_support_bindings.claim_id",
            "rule_support_bindings.evidence_id",
        ],
        name="fk_rule_review_binding",
    ),
    CheckConstraint("decision IN ('supports','refutes')", name="ck_rule_review_decision"),
    CheckConstraint("length(reason) BETWEEN 1 AND 2000", name="ck_rule_review_reason"),
    CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="ck_rule_review_digest"),
    UniqueConstraint(
        "rule_id",
        "rule_version",
        "node_id",
        "claim_id",
        "evidence_id",
        "input_digest",
        "actor_user_id",
        "decision",
        "range_complete",
        "reason",
        name="uq_rule_review_replay",
    ),
)

rule_validation_receipts = Table(
    "rule_validation_receipts",
    metadata,
    Column("receipt_id", Text, primary_key=True),
    Column("rule_id", Text, nullable=False),
    Column("rule_version", Integer, nullable=False),
    Column("actor_user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("input_digest", Text, nullable=False),
    Column("policy_version", Text, nullable=False),
    Column("validator_version", Text, nullable=False),
    Column("input_snapshot", JSONB, nullable=False),
    Column("prepared_assessment", JSONB),
    Column("created_at", DateTime(timezone=True), nullable=False),
    ForeignKeyConstraint(
        ["rule_id", "rule_version"],
        ["condition_rule_versions.rule_id", "condition_rule_versions.version"],
        name="fk_rule_validation_version",
    ),
    CheckConstraint("input_digest ~ '^[0-9a-f]{64}$'", name="ck_rule_validation_digest"),
    CheckConstraint("jsonb_typeof(input_snapshot)='object'", name="ck_rule_validation_snapshot"),
)

RULE_LIFECYCLE_SQL = """
CREATE OR REPLACE FUNCTION r11_require_immutable_rule() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
IF TG_OP='DELETE' THEN RAISE EXCEPTION 'rule versions are immutable' USING ERRCODE='23514'; END IF;
IF (to_jsonb(OLD)-'status'-'published_at'-'retired_at'-'published_by') <>
   (to_jsonb(NEW)-'status'-'published_at'-'retired_at'-'published_by') THEN
RAISE EXCEPTION 'rule content is immutable' USING ERRCODE='23514'; END IF;
IF (OLD.status<>NEW.status AND NOT
 ((OLD.status='candidate' AND NEW.status='validated') OR
  (OLD.status='validated' AND NEW.status='published') OR
  (OLD.status='published' AND NEW.status='retired'))) OR
 (OLD.published_at IS NOT NULL AND OLD.published_at IS DISTINCT FROM NEW.published_at) OR
 (OLD.published_by IS NOT NULL AND OLD.published_by IS DISTINCT FROM NEW.published_by) OR
 (OLD.retired_at IS NOT NULL AND OLD.retired_at IS DISTINCT FROM NEW.retired_at) THEN
RAISE EXCEPTION 'rule lifecycle is forward only' USING ERRCODE='23514'; END IF;
RETURN NEW; END $$;
CREATE TRIGGER condition_rule_versions_immutable BEFORE UPDATE OR DELETE
ON condition_rule_versions FOR EACH ROW EXECUTE FUNCTION r11_require_immutable_rule();
"""
APPEND_ONLY_SQL = """
CREATE OR REPLACE FUNCTION r11_require_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION 'rule and assessment receipts are append only' USING ERRCODE='23514'; END $$;
"""
event.listen(condition_rule_versions, "after_create", DDL(RULE_LIFECYCLE_SQL + APPEND_ONLY_SQL))
for _table in (rule_support_bindings, rule_leaf_reviews, rule_validation_receipts):
    event.listen(
        _table,
        "after_create",
        DDL(
            f"CREATE TRIGGER {_table.name}_immutable BEFORE UPDATE OR DELETE ON {_table.name} "
            "FOR EACH ROW EXECUTE FUNCTION r11_require_append_only();"
        ),
    )
RULE_TABLES = (
    condition_rule_versions,
    rule_support_bindings,
    rule_leaf_reviews,
    rule_validation_receipts,
)


def _json_row(row: RowMapping) -> dict[str, object]:
    return {
        str(key): value.isoformat() if isinstance(value, datetime) else value
        for key, value in row.items()
    }


def require_rule_access(scope: AccessScope, visibility: VisibilityScope, *, write: bool) -> None:
    scope.requires(READ_PUBLIC)
    scope.enforce_visible(visibility.visibility, visibility.tenant_id)
    if visibility.visibility == "tenant":
        scope.requires(WRITE_ASSET if write else READ_ASSET)
    elif write:
        scope.requires(MANAGE_PUBLIC_SOURCES)


def stored_rule(row: RowMapping) -> ConditionRule:
    return ConditionRule.model_validate(
        {
            **row["rule_payload"],
            "status": row["status"],
            "published_at": row["published_at"],
            "retired_at": row["retired_at"],
        }
    )


def read_rule(session: Session, scope: AccessScope, rule_id: str, version: int) -> RowMapping:
    row = (
        session.execute(
            select(condition_rule_versions).where(
                condition_rule_versions.c.rule_id == rule_id,
                condition_rule_versions.c.version == version,
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise CrossTenantAccessError("resource not found")
    require_rule_access(scope, stored_rule(row).scope, write=False)
    return row


def _source_rows(session: Session, rule: ConditionRule) -> tuple[RowMapping, ...]:
    rows = tuple(
        session.execute(
            select(
                document_revisions,
                documents.c.source_id,
                documents.c.content_hash.label("document_content_hash"),
                documents.c.visibility.label("document_visibility"),
                documents.c.tenant_id.label("document_tenant_id"),
                sources.c.visibility.label("source_visibility"),
                sources.c.tenant_id.label("source_tenant_id"),
            )
            .join(documents, documents.c.document_id == document_revisions.c.document_id)
            .join(sources, sources.c.source_id == documents.c.source_id)
            .join(
                event_documents, event_documents.c.revision_id == document_revisions.c.revision_id
            )
            .where(event_documents.c.event_id == rule.event_id, event_documents.c.active.is_(True))
            .order_by(document_revisions.c.revision_id)
            .limit(21)
        ).mappings()
    )
    if len(rows) > 20:
        raise RulePersistenceError("source_roster_budget_exceeded")
    return rows


def _all_source_rows(session: Session, rule: ConditionRule) -> tuple[RowMapping, ...]:
    active = _source_rows(session, rule)
    historical = tuple(
        session.execute(
            select(
                document_revisions,
                documents.c.source_id,
                documents.c.content_hash.label("document_content_hash"),
                documents.c.visibility.label("document_visibility"),
                documents.c.tenant_id.label("document_tenant_id"),
                sources.c.visibility.label("source_visibility"),
                sources.c.tenant_id.label("source_tenant_id"),
            )
            .join(documents, documents.c.document_id == document_revisions.c.document_id)
            .join(sources, sources.c.source_id == documents.c.source_id)
            .where(
                document_revisions.c.revision_id.in_(
                    select(evidence.c.revision_id).where(
                        evidence.c.evidence_id.in_(rule.source_span_ids)
                    )
                )
            )
        ).mappings()
    )
    rows = {row["revision_id"]: row for row in (*active, *historical)}
    if len(rows) > 20:
        raise RulePersistenceError("source_roster_budget_exceeded")
    return tuple(rows[key] for key in sorted(rows))


def require_snapshot_source_access(
    session: Session,
    scope: AccessScope,
    derived: VisibilityScope,
    snapshot: RuleInputSnapshot,
) -> None:
    """Historical references retain today's complete source/document/revision ACL boundary."""
    for item in snapshot.sources:
        row = (
            session.execute(
                select(
                    document_revisions.c.visibility,
                    document_revisions.c.tenant_id,
                    documents.c.visibility.label("document_visibility"),
                    documents.c.tenant_id.label("document_tenant_id"),
                    sources.c.visibility.label("source_visibility"),
                    sources.c.tenant_id.label("source_tenant_id"),
                )
                .join(documents, documents.c.document_id == document_revisions.c.document_id)
                .join(sources, sources.c.source_id == documents.c.source_id)
                .where(
                    document_revisions.c.revision_id == item.revision_id,
                    documents.c.document_id == item.document_id,
                    documents.c.source_id == item.source_id,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            raise CrossTenantAccessError("resource not found")
        for prefix in ("", "document_", "source_"):
            _bounded_scope(scope, derived, row, prefix)


def _bounded_scope(
    scope: AccessScope, derived: VisibilityScope, row: RowMapping, prefix: str
) -> None:
    visibility, tenant_id = row[prefix + "visibility"], row[prefix + "tenant_id"]
    scope.enforce_visible(visibility, tenant_id)
    if visibility == "tenant" and (
        derived.visibility != "tenant" or derived.tenant_id != tenant_id
    ):
        raise RulePersistenceError("derived_scope_exceeds_input")


def lock_rule_inputs(
    session: Session,
    rule: ConditionRule,
    access_scope: AccessScope,
    *,
    lock_rule: bool = True,
) -> None:
    """Source/document precede publication/event; asset callers lock their parent first.

    Actual source publishers hold source/document before knowledge publication; asset imports
    hold asset before tenant publication. No claim lock is held while waiting for publication.
    """
    rows = _all_source_rows(session, rule)
    source_ids = sorted({row["source_id"] for row in rows})
    for source_id in source_ids:
        session.execute(
            select(func.pg_advisory_xact_lock(func.hashtextextended("source:" + source_id, 0)))
        )
    session.execute(
        select(sources.c.source_id)
        .where(sources.c.source_id.in_(source_ids))
        .order_by(sources.c.source_id)
        .with_for_update(read=True)
    ).all()
    revision_ids = [row["revision_id"] for row in rows]
    session.execute(
        select(document_revisions.c.revision_id)
        .join(documents, documents.c.document_id == document_revisions.c.document_id)
        .where(document_revisions.c.revision_id.in_(revision_ids))
        .order_by(documents.c.document_id, document_revisions.c.revision_id)
        .with_for_update(read=True, of=(documents, document_revisions))
    ).all()
    scope_keys = {"public", knowledge_scope_key(rule.scope)}
    if access_scope.tenant_id is not None:
        scope_keys.add("tenant:" + access_scope.tenant_id)
    for key in sorted(scope_keys):
        session.execute(
            select(
                func.pg_advisory_xact_lock(func.hashtextextended("knowledge-publication:" + key, 0))
            )
        )
    session.execute(
        select(
            func.pg_advisory_xact_lock(
                func.hashtextextended("condition-rule-version:" + rule.rule_id, 0)
            )
        )
    )
    session.execute(
        select(events.c.event_id)
        .where(events.c.event_id == rule.event_id)
        .with_for_update(read=True)
    ).all()
    if lock_rule:
        session.execute(
            select(condition_rule_versions.c.rule_id)
            .where(
                condition_rule_versions.c.rule_id == rule.rule_id,
                condition_rule_versions.c.version == rule.version,
            )
            .with_for_update()
        ).all()
    session.execute(
        select(claims.c.claim_id)
        .where(claims.c.claim_id.in_(rule.supporting_claim_ids))
        .order_by(claims.c.claim_id)
        .with_for_update(read=True)
    ).all()
    session.execute(
        select(evidence.c.evidence_id)
        .where(evidence.c.evidence_id.in_(rule.source_span_ids))
        .order_by(evidence.c.evidence_id)
        .with_for_update(read=True)
    ).all()
    session.execute(
        select(claim_evidence.c.claim_id)
        .where(
            claim_evidence.c.claim_id.in_(rule.supporting_claim_ids),
            claim_evidence.c.evidence_id.in_(rule.source_span_ids),
        )
        .with_for_update(read=True)
    ).all()
    session.execute(
        select(claim_assertions.c.assertion_id)
        .where(
            claim_assertions.c.claim_id.in_(rule.supporting_claim_ids),
        )
        .with_for_update(read=True)
    ).all()


def load_rule_inputs(
    session: Session,
    scope: AccessScope,
    row: RowMapping,
    store: ContentStorage | None,
) -> RuleInputSnapshot:
    """Separate Unicode existence from necessity; reviews bind the complete live PG input."""
    rule = stored_rule(row)
    require_rule_access(scope, rule.scope, write=False)
    event_row = (
        session.execute(select(events).where(events.c.event_id == rule.event_id)).mappings().first()
    )
    if event_row is None:
        raise CrossTenantAccessError("resource not found")
    _bounded_scope(scope, rule.scope, event_row, "")
    sources_snapshot = []
    active_revision_ids = tuple(item["revision_id"] for item in _source_rows(session, rule))
    source_rows = _all_source_rows(session, rule)
    total_bytes = 0
    for source in source_rows:
        for prefix in ("", "document_", "source_"):
            _bounded_scope(scope, rule.scope, source, prefix)
        if source["is_current"] and source["document_content_hash"] != source["content_hash"]:
            raise RulePersistenceError("source_document_current_pair_invalid")
        if store is not None:
            size = session.scalar(
                select(content_objects.c.size_bytes).where(
                    content_objects.c.content_hash == source["content_hash"]
                )
            )
            if size is None or size > 2 * 1024 * 1024 or total_bytes + size > 8 * 1024 * 1024:
                raise RulePersistenceError("source_blob_budget_exceeded")
            total_bytes += size
            source_blob = store.read_verified(source["content_hash"])
            if (
                size != len(source_blob)
                or hashlib.sha256(source_blob).hexdigest() != source["content_hash"]
            ):
                raise RulePersistenceError("source_blob_integrity_invalid")
        sources_snapshot.append(
            SourceInput(
                source_id=source["source_id"],
                document_id=source["document_id"],
                revision_id=source["revision_id"],
                content_sha256=source["content_hash"],
                revision_number=source["revision_number"],
                is_current=source["is_current"],
                parse_status=source["parse_status"],
                source_scope=VisibilityScope(
                    visibility=source["source_visibility"], tenant_id=source["source_tenant_id"]
                ),
                document_scope=VisibilityScope(
                    visibility=source["document_visibility"], tenant_id=source["document_tenant_id"]
                ),
                revision_scope=VisibilityScope(
                    visibility=source["visibility"], tenant_id=source["tenant_id"]
                ),
                source_fingerprint=publication_payload_digest(_json_row(source)),
            )
        )
    nodes = {
        node.node_id: node
        for node in iter_condition_nodes(rule.condition_ast)
        if not isinstance(node, AllOf | AnyOf)
    }
    bindings = tuple(
        session.execute(
            select(rule_support_bindings)
            .where(
                rule_support_bindings.c.rule_id == rule.rule_id,
                rule_support_bindings.c.rule_version == rule.version,
            )
            .order_by(
                rule_support_bindings.c.node_id,
                rule_support_bindings.c.claim_id,
                rule_support_bindings.c.evidence_id,
            )
            .limit(65)
        ).mappings()
    )
    if len(bindings) > 64:
        raise RulePersistenceError("rule_support_budget_exceeded")
    checked = []
    supports = []
    for binding in bindings:
        node = nodes.get(binding["node_id"])
        if node is None or condition_digest(node) != binding["condition_sha256"]:
            raise RulePersistenceError("detached_rule_binding")
        claim = (
            session.execute(select(claims).where(claims.c.claim_id == binding["claim_id"]))
            .mappings()
            .one()
        )
        _bounded_scope(scope, rule.scope, claim, "")
        span = (
            session.execute(
                select(evidence, claim_evidence.c.support_kind, claim_evidence.c.validation_status)
                .join(claim_evidence, claim_evidence.c.evidence_id == evidence.c.evidence_id)
                .where(
                    evidence.c.evidence_id == binding["evidence_id"],
                    claim_evidence.c.claim_id == binding["claim_id"],
                )
            )
            .mappings()
            .first()
        )
        if span is None:
            raise RulePersistenceError("claim_evidence_pair_missing")
        _bounded_scope(scope, rule.scope, span, "")
        supporting_source = next(
            (item for item in source_rows if item["revision_id"] == span["revision_id"]), None
        )
        assertion = (
            session.execute(
                select(claim_assertions).where(
                    claim_assertions.c.claim_id == binding["claim_id"],
                    claim_assertions.c.revision_id == span["revision_id"],
                )
            )
            .mappings()
            .first()
        )
        if (
            supporting_source is None
            or assertion is None
            or assertion["source_id"] != supporting_source["source_id"]
        ):
            raise RulePersistenceError("source_document_revision_pair_missing")
        source = supporting_source
        block = (
            session.execute(select(text_blocks).where(text_blocks.c.block_id == span["block_id"]))
            .mappings()
            .first()
        )
        if block is None:
            raise RulePersistenceError("evidence_block_missing")
        start, end = (
            span["start_offset"] - block["start_offset"],
            span["end_offset"] - block["start_offset"],
        )
        if (
            block["revision_id"] != span["revision_id"]
            or not 0 <= start < end <= len(block["block_text"])
            or block["end_offset"] - block["start_offset"] != len(block["block_text"])
            or hashlib.sha256(block["block_text"].encode()).hexdigest() != block["text_sha256"]
            or block["block_text"][start:end] != span["quote"]
            or hashlib.sha256(span["quote"].encode()).hexdigest() != span["quote_sha256"]
            or span["coordinate_version"] != "fulltext_unicode_v1"
            or span["verified_at"] is None
        ):
            raise RulePersistenceError("source_quote_coordinates_invalid")
        ref = EvidenceReference(
            evidence_id=span["evidence_id"],
            source_id=source["source_id"],
            document_id=source["document_id"],
            revision_id=span["revision_id"],
            block_id=span["block_id"],
            start_offset=span["start_offset"],
            end_offset=span["end_offset"],
            quote_text=span["quote"],
            quote_sha256=span["quote_sha256"],
            scope=VisibilityScope(visibility=span["visibility"], tenant_id=span["tenant_id"]),
            support_kind=span["support_kind"],
            validation_status=span["validation_status"],
        )
        fingerprint = publication_payload_digest(
            [
                *(_json_row(item) for item in (binding, claim, span, block, source, assertion)),
            ]
        )
        reviews = tuple(
            session.execute(
                select(rule_leaf_reviews)
                .where(
                    rule_leaf_reviews.c.rule_id == rule.rule_id,
                    rule_leaf_reviews.c.rule_version == rule.version,
                    rule_leaf_reviews.c.node_id == binding["node_id"],
                    rule_leaf_reviews.c.claim_id == binding["claim_id"],
                    rule_leaf_reviews.c.evidence_id == binding["evidence_id"],
                    rule_leaf_reviews.c.input_digest == fingerprint,
                )
                .order_by(rule_leaf_reviews.c.created_at, rule_leaf_reviews.c.review_id)
            ).mappings()
        )
        decisions = {item["decision"] for item in reviews}
        semantic: Literal["supports", "refutes", "pending"] = "pending"
        if "refutes" in decisions:
            semantic = "refutes"
        elif "supports" in decisions:
            semantic = "supports"
        complete = semantic == "supports" and any(item["range_complete"] for item in reviews)
        current = (
            source["is_current"]
            and source["parse_status"] in {"parsed", "partial"}
            and source["revision_id"] in active_revision_ids
            and claim["is_current"]
            and claim["subject"] == "event:" + rule.event_id
            and claim["source_revision_id"] in active_revision_ids
            and claim["provenance_status"] == "source_verified"
            and span["supports_claim"]
        )
        checked.append(
            CheckedSupport(
                binding=RuleSupportBinding(
                    **{key: binding[key] for key in ("node_id", "claim_id", "evidence_id")}
                ),
                condition_sha256=binding["condition_sha256"],
                claim_fingerprint=publication_payload_digest(_json_row(claim)),
                source_fingerprint=publication_payload_digest(_json_row(source)),
                review_fingerprint=publication_payload_digest(
                    [_json_row(item) for item in reviews]
                ),
                input_digest=fingerprint,
                evidence=ref,
                semantic_status=semantic,
                range_completeness_confirmed=complete,
            )
        )
        supports.append(
            RuleLeafSupport(
                node_id=binding["node_id"],
                condition_sha256=binding["condition_sha256"],
                claim_id=claim["claim_id"],
                claim_status=ClaimStatus(claim["claim_status"])
                if current
                else ClaimStatus.UNVERIFIED,
                claim_origin=claim["claim_origin"],
                condition_scope=rule.rule_kind,
                source_id=source["source_id"],
                document_id=source["document_id"],
                source_revision_id=span["revision_id"],
                scope=VisibilityScope(visibility=claim["visibility"], tenant_id=claim["tenant_id"]),
                evidence=(
                    ref.model_copy(update={"support_kind": "refutes"})
                    if semantic == "refutes"
                    else ref,
                ),
                necessary_condition_supported=current and semantic == "supports",
                range_completeness_confirmed=complete,
            )
        )
    keys = {"public", knowledge_scope_key(rule.scope)}
    if scope.tenant_id is not None:
        keys.add("tenant:" + scope.tenant_id)
    epochs: dict[str, int | None] = {}
    for key in sorted(keys):
        value = session.scalar(select(scope_epochs.c.epoch).where(scope_epochs.c.scope_key == key))
        epochs[key] = None if value is None else int(value)
    validation = validate_rule(
        rule, access_scope=scope, policy=SERVER_RULE_VALIDATION_POLICY, supports=tuple(supports)
    )
    pending_semantics = tuple(
        "pending_semantic_review:" + item.binding.node_id
        for item in checked
        if item.semantic_status == "pending"
    )
    if pending_semantics:
        validation = validation.model_copy(
            update={
                "eligible": False,
                "automatic_publication_eligible": False,
                "pending_review": (*validation.pending_review, *pending_semantics),
            }
        )
    if event_row["status"] != "active" or not active_revision_ids:
        validation = validation.model_copy(
            update={
                "eligible": False,
                "automatic_publication_eligible": False,
                "pending_review": (*validation.pending_review, "active_source_roster_required"),
            }
        )
    payload = dict(
        rule=rule.model_dump(mode="json"),
        author_user_id=row["author_user_id"],
        event_version=event_row["business_version"],
        event_status=event_row["status"],
        sources=[item.model_dump(mode="json") for item in sources_snapshot],
        active_revision_ids=active_revision_ids,
        supports=[item.model_dump(mode="json") for item in checked],
        scope_epoch_map=epochs,
        validation=validation.model_dump(mode="json"),
    )
    return RuleInputSnapshot(**payload, input_digest=publication_payload_digest(payload))


def receipt_values(inputs: RuleInputSnapshot, actor: str, receipt_id: str) -> dict[str, object]:
    return dict(
        receipt_id=receipt_id,
        rule_id=inputs.rule.rule_id,
        rule_version=inputs.rule.version,
        actor_user_id=actor,
        input_digest=inputs.input_digest,
        policy_version=inputs.validation.policy_version,
        validator_version=inputs.validation.validator_version,
        input_snapshot=inputs.model_dump(mode="json"),
        created_at=datetime.now(UTC),
    )
