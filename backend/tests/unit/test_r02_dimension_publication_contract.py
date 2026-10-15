"""逐维结果发布的纯边界：未知、无证据、失败、版本和权限均不补成功。"""

from datetime import UTC, datetime
from unittest.mock import MagicMock
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, CrossTenantAccessError, PermissionDeniedError, Role
from ai_intel.enrichment.persistence import (
    DimensionPublicationError,
    DimensionRepository,
    DimensionSubmission,
)


@pytest.mark.parametrize(
    "dimension",
    [
        "cvss",
        "epss",
        "kev",
        "cwe",
        "atlas",
        "versions",
        "literature",
        "poc",
        "exposure",
    ],
)
def test_all_frozen_dimensions_can_record_an_explicit_pending_state(dimension: str) -> None:
    submission = DimensionSubmission(
        event_id=uuid4(),
        dimension=dimension,
        status="pending",
        expected_event_version=1,
        input_fingerprint="a" * 64,
    )
    assert submission.status.value == "pending"
    assert submission.observed_at is None
    assert submission.freshness.value == "unknown"
    assert not submission.claim_ids


@pytest.mark.parametrize(
    "invalid",
    [
        {"status": "available"},
        {"status": "conflict", "claim_ids": [uuid4()]},
        {"status": "not_found"},
        {"status": "failed"},
        {"status": "blocked"},
        {"freshness": "current"},
        {"expected_event_version": True},
        {"expected_event_version": 0},
        {"input_fingerprint": "not-a-digest"},
        {"dimension": "made_up_dimension"},
        {"claim_ids": [uuid4()]},
        {"tenant_id": "request-cannot-set-scope"},
    ],
)
def test_invalid_dimension_input_cannot_look_like_a_success(invalid: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        DimensionSubmission.model_validate(
            {
                "event_id": str(uuid4()),
                "dimension": "cvss",
                "status": "pending",
                "expected_event_version": 1,
                "input_fingerprint": "a" * 64,
                **invalid,
            }
        )


def test_failed_and_not_found_are_distinct_observations() -> None:
    failed = DimensionSubmission(
        event_id=uuid4(),
        dimension="epss",
        status="failed",
        error_code="upstream_timeout",
        expected_event_version=1,
        input_fingerprint="a" * 64,
    )
    absent = DimensionSubmission(
        event_id=uuid4(),
        dimension="epss",
        status="not_found",
        source_ids=(uuid4(),),
        searched_at=datetime.now(UTC),
        expected_event_version=1,
        input_fingerprint="a" * 64,
    )
    assert failed.searched_at is None and absent.searched_at is not None
    assert failed.status != absent.status


def test_repository_needs_read_permission_even_for_a_known_event_id() -> None:
    scope = AccessScope("fixture-reader", None, Role.VIEWER)
    repository = DimensionRepository(MagicMock(spec=Session), scope)
    with pytest.raises(PermissionDeniedError):
        repository.read_results(str(uuid4()))


def test_invisible_event_returns_no_dimension_information() -> None:
    session = MagicMock(spec=Session)
    session.execute.return_value.mappings.return_value.first.return_value = None
    scope = AccessScope.for_authenticated_user("fixture-reader", None, Role.VIEWER)
    with pytest.raises(CrossTenantAccessError, match="resource not found"):
        DimensionRepository(session, scope).read_results(str(uuid4()), include_history=True)


def test_publication_key_and_timestamp_are_validated_before_database_use() -> None:
    scope = AccessScope.for_authenticated_user("fixture-reader", None, Role.SYSTEM_ADMIN)
    repository = DimensionRepository(MagicMock(spec=Session), scope)
    submission = DimensionSubmission(
        event_id=uuid4(),
        dimension="cvss",
        status="pending",
        expected_event_version=1,
        input_fingerprint="a" * 64,
    )
    for key, recorded_at in (
        ("", datetime.now(UTC)),
        ("a" * 201, datetime.now(UTC)),
        ("bounded", datetime(2026, 10, 15)),
    ):
        with pytest.raises(DimensionPublicationError):
            repository.publish(key, submission, recorded_at)
