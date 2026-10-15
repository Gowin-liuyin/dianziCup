"""显式合成unit fixtures：修复声明集合判等与全部候选时间入口，不接实际资产。"""

import json
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from itertools import permutations

import pytest

from ai_intel.assets.manifest_parser import (
    ManifestParseResult,
    ManifestValidationError,
    parse_manifest,
)
from ai_intel.domain.access import AccessScope, Role

FIXTURE_CONTEXT = {
    "manifest_format": "json_manifest_v1",
    "scope": AccessScope.for_authenticated_user("fixture-user", "fixture-tenant", Role.ANALYST),
    "authorized_asset_tenant_id": "fixture-tenant",
    "asset_id": "29a06008-8abf-442f-8645-a4c0f8876469",
    "snapshot_number": 1,
    "source_version": "fixture-time-identity-revision-1",
    "observed_at": datetime(2026, 10, 15, 12, tzinfo=UTC),
    "recorded_at": datetime(2026, 10, 15, 13, tzinfo=UTC),
}


def parse_fixture(raw: bytes, **changes: object) -> ManifestParseResult:
    return parse_manifest(raw, **{**FIXTURE_CONTEXT, **changes})


def manifest_fixture(**fields: object) -> bytes:
    return json.dumps({"format_version": 1, "components": [], **fields}).encode()


def test_all_permission_permutations_share_identity_and_retain_original_order() -> None:
    orders = tuple(permutations(("read:inventory", "read:evidence", "read:events")))
    results = tuple(
        parse_fixture(manifest_fixture(tool_permissions=list(order))) for order in orders
    )
    assert len({result.snapshot.snapshot_sha256 for result in results}) == 1
    assert len({result.snapshot.snapshot_id for result in results}) == 1
    assert len({result.source_sha256 for result in results}) == len(orders)
    assert [result.snapshot.tool_permissions for result in results] == list(orders)
    assert parse_fixture(results[0].source_bytes) == results[0]


@pytest.mark.parametrize("changed", ["Read:inventory", " read:inventory", "read:inventory "])
def test_permission_identity_is_not_trimmed_or_coerced(changed: str) -> None:
    first = parse_fixture(manifest_fixture(tool_permissions=["read:inventory"]))
    second = parse_fixture(manifest_fixture(tool_permissions=[changed]))
    assert second.snapshot.tool_permissions == (changed,)
    assert first.snapshot.snapshot_sha256 != second.snapshot.snapshot_sha256


def test_unknown_permission_declaration_and_explicit_empty_keep_distinct_identity() -> None:
    missing = parse_fixture(manifest_fixture())
    unknown = parse_fixture(manifest_fixture(tool_permissions=None))
    empty = parse_fixture(manifest_fixture(tool_permissions=[]))
    assert missing.snapshot.tool_permissions is unknown.snapshot.tool_permissions is None
    assert empty.snapshot.tool_permissions == ()
    assert missing.snapshot.snapshot_sha256 == unknown.snapshot.snapshot_sha256
    assert missing.snapshot.snapshot_sha256 != empty.snapshot.snapshot_sha256
    assert missing.snapshot.snapshot_id != empty.snapshot.snapshot_id


def test_dependency_path_keeps_order_sensitive_identity() -> None:
    first = parse_fixture(
        manifest_fixture(
            components=[{"package_name": "langchain", "dependency_path": ["app", "lib"]}]
        )
    )
    second = parse_fixture(
        manifest_fixture(
            components=[{"package_name": "langchain", "dependency_path": ["lib", "app"]}]
        )
    )
    assert first.snapshot.components[0].dependency_path == ("app", "lib")
    assert second.snapshot.components[0].dependency_path == ("lib", "app")
    assert first.snapshot.snapshot_sha256 != second.snapshot.snapshot_sha256


class MissingOffsetZone(tzinfo):
    def utcoffset(self, value: datetime | None) -> None:
        return None


class InvalidOffsetZone(tzinfo):
    def utcoffset(self, value: datetime | None) -> timedelta:
        return timedelta(hours=25)


class FailingOffsetZone(tzinfo):
    def utcoffset(self, value: datetime | None) -> timedelta:
        raise ValueError("fixture-sensitive-error-canary")


class ChangingOffsetZone(tzinfo):
    """故意不稳定的合成时区；第二次读offset不能退回宿主时区。"""

    def __init__(self) -> None:
        self.offset_reads = 0

    def utcoffset(self, value: datetime | None) -> timedelta | None:
        self.offset_reads += 1
        return timedelta(hours=8) if self.offset_reads == 1 else None


@pytest.mark.parametrize("field", ["observed_at", "recorded_at"])
@pytest.mark.parametrize(
    ("timestamp", "code"),
    [
        (datetime(2026, 10, 15, 12), "timezone_required"),
        (datetime(2026, 10, 15, 12, tzinfo=MissingOffsetZone()), "timezone_required"),
        (datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14))), "invalid_timestamp"),
        (datetime(9999, 12, 31, 23, tzinfo=timezone(timedelta(hours=-14))), "invalid_timestamp"),
        (datetime(2026, 10, 15, 12, tzinfo=InvalidOffsetZone()), "invalid_timestamp"),
        (datetime(2026, 10, 15, 12, tzinfo=FailingOffsetZone()), "invalid_timestamp"),
        (None, "timezone_required"),
        ("2026-10-15T12:00:00+08:00", "timezone_required"),
        (True, "timezone_required"),
        (1, "timezone_required"),
        ({}, "timezone_required"),
    ],
    ids=[
        "naive",
        "offset-missing",
        "lower-utc-overflow",
        "upper-utc-overflow",
        "invalid-offset",
        "offset-error",
        "none",
        "string",
        "bool",
        "integer",
        "object",
    ],
)
def test_all_timestamp_fields_reject_missing_or_unrepresentable_time(
    field: str, timestamp: object, code: str
) -> None:
    with pytest.raises(ManifestValidationError) as error:
        parse_fixture(manifest_fixture(), **{field: timestamp})
    assert error.value.code == code
    assert error.value.locator == f"/{field}"
    assert "fixture-sensitive-error-canary" not in str(error.value)


@pytest.mark.parametrize("field", ["observed_at", "recorded_at"])
@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        (
            datetime(2026, 10, 15, 12, tzinfo=timezone(timedelta(hours=8))),
            datetime(2026, 10, 15, 4, tzinfo=UTC),
        ),
        (datetime.min.replace(tzinfo=UTC), datetime.min.replace(tzinfo=UTC)),
        (datetime.max.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC)),
    ],
    ids=["real-plus-eight", "min-utc", "max-utc"],
)
def test_all_timestamp_fields_normalize_supported_boundaries_to_utc(
    field: str, timestamp: datetime, expected: datetime
) -> None:
    result = parse_fixture(manifest_fixture(), **{field: timestamp})
    normalized = getattr(result.snapshot, field)
    assert normalized == expected
    assert normalized.tzinfo is UTC


@pytest.mark.parametrize("field", ["observed_at", "recorded_at"])
def test_offset_is_read_once_before_normalization(field: str) -> None:
    zone = ChangingOffsetZone()
    timestamp = datetime(2026, 10, 15, 12, tzinfo=zone)
    result = parse_fixture(manifest_fixture(), **{field: timestamp})
    assert getattr(result.snapshot, field) == datetime(2026, 10, 15, 4, tzinfo=UTC)
    assert zone.offset_reads == 1
