"""Immutable HTTP mutation receipts; their writes share the business transaction."""

import hashlib
import re
from collections.abc import Callable
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Session

from ai_intel.domain.access import READ_PUBLIC, AccessScope, PermissionDeniedError
from ai_intel.knowledge.models import metadata
from ai_intel.recommendations.service_contracts import (
    RecommendationConflictError,
    RecommendationIntegrityError,
    canonical_json_bytes,
    content_sha256,
)

recommendation_mutation_receipts = Table(
    "recommendation_mutation_receipts",
    metadata,
    Column("id", Text, primary_key=True),
    Column("tenant_id", Text, nullable=False),
    Column("user_id", Text, ForeignKey("users.user_id"), nullable=False),
    Column("operation", Text, nullable=False),
    Column("target_locator", Text, nullable=False),
    Column("idempotency_sha256", Text, nullable=False),
    Column("input_sha256", Text, nullable=False),
    Column("response_payload", JSONB, nullable=False),
    Column("response_sha256", Text, nullable=False),
    Column("status_code", Integer, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint(
        "tenant_id",
        "user_id",
        "operation",
        "target_locator",
        "idempotency_sha256",
        name="uq_recommendation_mutation_request",
    ),
    CheckConstraint(
        "operation IN ('create_subscription','replace_subscription','set_enabled',"
        "'generate','mark_read','create_report')",
        name="ck_recommendation_mutation_operation",
    ),
    CheckConstraint(
        "length(target_locator) BETWEEN 1 AND 200",
        name="ck_recommendation_mutation_target",
    ),
    CheckConstraint(
        "idempotency_sha256 ~ '^[0-9a-f]{64}$' AND input_sha256 ~ '^[0-9a-f]{64}$' "
        "AND response_sha256 ~ '^[0-9a-f]{64}$'",
        name="ck_recommendation_mutation_hashes",
    ),
    CheckConstraint(
        "jsonb_typeof(response_payload)='object'",
        name="ck_recommendation_mutation_response",
    ),
    CheckConstraint("status_code IN (200,201)", name="ck_recommendation_mutation_status"),
)


def idempotency_key_digest(key: str | None) -> str:
    if key is None or re.fullmatch(r"[\x21-\x7e]{1,200}", key) is None:
        raise ValueError("invalid_idempotency_key")
    return hashlib.sha256(key.encode("ascii")).hexdigest()


def perform_mutation(
    session: Session,
    scope: AccessScope,
    *,
    operation: str,
    target_locator: str,
    key: str,
    request_payload: dict[str, object],
    status_code: int,
    effect: Callable[[], dict[str, object]],
    replay: Callable[[dict[str, object]], dict[str, object]],
) -> tuple[dict[str, object], int]:
    """Caller owns the active transaction and fresh authentication, including replay.

    A scoped transaction advisory lock serializes the first effect before the unique
    insert. Only completed receipts are inserted; any callback/insert failure rolls
    back both records through the caller. No commits or reservations live here.
    """
    if not session.in_transaction():
        raise ValueError("mutation_requires_active_transaction")
    scope.requires(READ_PUBLIC)
    if scope.tenant_id is None:
        raise PermissionDeniedError("subscription_tenant_required")
    digest = idempotency_key_digest(key)
    input_digest = content_sha256(request_payload)
    identity = [scope.tenant_id, scope.user_id, operation, target_locator, digest]
    lock_id = int.from_bytes(
        hashlib.sha256(canonical_json_bytes(identity)).digest()[:8], "big", signed=True
    )
    session.execute(text("SELECT pg_advisory_xact_lock(:lock_id)"), {"lock_id": lock_id})
    table = recommendation_mutation_receipts
    row = (
        session.execute(
            select(table).where(
                table.c.tenant_id == scope.tenant_id,
                table.c.user_id == scope.user_id,
                table.c.operation == operation,
                table.c.target_locator == target_locator,
                table.c.idempotency_sha256 == digest,
            )
        )
        .mappings()
        .first()
    )
    if row is not None:
        if row["input_sha256"] != input_digest:
            raise RecommendationConflictError("idempotency_input_changed")
        payload = row["response_payload"]
        if not isinstance(payload, dict) or content_sha256(payload) != row["response_sha256"]:
            raise RecommendationIntegrityError("mutation_receipt_hash_mismatch")
        if row["status_code"] != status_code:
            raise RecommendationIntegrityError("mutation_receipt_status_mismatch")
        return replay(payload), row["status_code"]
    payload = effect()
    response_digest = content_sha256(payload)
    session.execute(
        insert(table).values(
            id=str(uuid4()),
            tenant_id=scope.tenant_id,
            user_id=scope.user_id,
            operation=operation,
            target_locator=target_locator,
            idempotency_sha256=digest,
            input_sha256=input_digest,
            response_payload=payload,
            response_sha256=response_digest,
            status_code=status_code,
            created_at=datetime.now(UTC),
        )
    )
    return payload, status_code
