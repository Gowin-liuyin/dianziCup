"""Explicit synthetic fix recheck inputs; no service, network, secret or real asset access."""

import hashlib
import json
from datetime import UTC, datetime, timedelta, timezone, tzinfo
from itertools import permutations

import pytest

from ai_intel.assets.manifest_parser import ManifestValidationError, parse_manifest
from ai_intel.domain.access import AccessScope, Role

SCOPE = AccessScope.for_authenticated_user("recheck-user", "recheck-tenant", Role.ANALYST)
DEFAULT_TIME = datetime(2026, 10, 15, 19, tzinfo=UTC)


def parse_input(
    raw, manifest_format="json_manifest_v1", field="observed_at", timestamp=DEFAULT_TIME
):
    return parse_manifest(
        raw,
        manifest_format=manifest_format,
        scope=SCOPE,
        authorized_asset_tenant_id="recheck-tenant",
        asset_id="b3c1d42e-cf57-4d16-b8c6-6c62158d7e0e",
        snapshot_number=4,
        source_version="recheck-only-source-4",
        observed_at=timestamp if field == "observed_at" else DEFAULT_TIME,
        recorded_at=timestamp if field == "recorded_at" else DEFAULT_TIME,
        csv_column_mapping={"package_name": "Name", "version": "Ver"}
        if manifest_format == "csv_components_v1"
        else None,
    )


def raw_input(manifest_format):
    if manifest_format == "csv_components_v1":
        return b"Name,Ver\nlangchain,1.10.0\n"
    return b'{"format_version":1,"components":[{"package_name":"langchain","version":"1.10.0"}]}'


class MissingOffset(tzinfo):
    def utcoffset(self, value):
        return None


class ReadOnceOffset(tzinfo):
    def __init__(self):
        self.reads = 0

    def utcoffset(self, value):
        self.reads += 1
        if self.reads > 1:
            raise AssertionError("offset read more than once")
        return timedelta(hours=5, minutes=45, seconds=30)


@pytest.mark.parametrize("manifest_format", ["json_manifest_v1", "csv_components_v1"])
@pytest.mark.parametrize("field", ["observed_at", "recorded_at"])
@pytest.mark.parametrize(
    ("timestamp", "code"),
    [
        (datetime(2026, 10, 15, 19, tzinfo=MissingOffset()), "timezone_required"),
        (datetime(1, 1, 1, tzinfo=timezone(timedelta(hours=14))), "invalid_timestamp"),
        (
            datetime(9999, 12, 31, 23, 59, tzinfo=timezone(timedelta(hours=-14))),
            "invalid_timestamp",
        ),
    ],
    ids=["missing-offset", "lower-overflow", "upper-overflow"],
)
def test_both_formats_and_time_fields_reject_missing_or_unrepresentable_offset(
    manifest_format, field, timestamp, code
):
    with pytest.raises(ManifestValidationError) as caught:
        parse_input(raw_input(manifest_format), manifest_format, field, timestamp)
    assert caught.value.code == code
    assert caught.value.locator == f"/{field}"


@pytest.mark.parametrize("manifest_format", ["json_manifest_v1", "csv_components_v1"])
@pytest.mark.parametrize("field", ["observed_at", "recorded_at"])
def test_custom_offset_read_once_with_seconds_and_no_default_time(manifest_format, field):
    zone = ReadOnceOffset()
    timestamp = datetime(2026, 10, 15, 19, tzinfo=zone)
    raw = raw_input(manifest_format)
    result = parse_input(raw, manifest_format, field, timestamp)
    assert zone.reads == 1
    assert getattr(result.snapshot, field) == datetime(2026, 10, 15, 13, 14, 30, tzinfo=UTC)
    assert getattr(result.snapshot, field).tzinfo is UTC
    assert result.source_bytes == raw


@pytest.mark.parametrize("field", ["observed_at", "recorded_at"])
@pytest.mark.parametrize(
    "timestamp",
    [datetime.min.replace(tzinfo=UTC), datetime.max.replace(tzinfo=UTC)],
    ids=["valid-min", "valid-max"],
)
def test_csv_utc_extremes_are_preserved_without_clamping(field, timestamp):
    result = parse_input(raw_input("csv_components_v1"), "csv_components_v1", field, timestamp)
    assert getattr(result.snapshot, field) == timestamp
    assert getattr(result.snapshot, field).tzinfo is UTC


def test_permission_only_sort_keeps_raw_tuple_and_unknown_empty_distinction():
    results = []
    for order in permutations(("read:z", "read:A", "read:a")):
        raw = json.dumps(
            {"format_version": 1, "components": [], "tool_permissions": order}
        ).encode()
        result = parse_input(raw)
        assert result.source_bytes == raw
        assert result.source_sha256 == hashlib.sha256(raw).hexdigest()
        assert result.snapshot.tool_permissions == order
        results.append(result)
    assert len({result.snapshot.snapshot_sha256 for result in results}) == 1
    assert len({result.snapshot.snapshot_id for result in results}) == 1
    assert len({result.source_sha256 for result in results}) == 6
    unknown = parse_input(b'{"format_version":1,"components":[],"tool_permissions":null}')
    empty = parse_input(b'{"format_version":1,"components":[],"tool_permissions":[]}')
    assert unknown.snapshot.tool_permissions is None
    assert empty.snapshot.tool_permissions == ()
    assert unknown.snapshot.snapshot_sha256 != empty.snapshot.snapshot_sha256


def test_dependency_path_stays_ordered_when_permissions_change_order():
    first_raw = (
        b'{"format_version":1,"components":[{"package_name":"langchain",'
        b'"dependency_path":["root","leaf"]}],"tool_permissions":["read:z","read:a"]}'
    )
    second_raw = (
        b'{"format_version":1,"components":[{"package_name":"langchain",'
        b'"dependency_path":["leaf","root"]}],"tool_permissions":["read:a","read:z"]}'
    )
    first = parse_input(first_raw)
    second = parse_input(second_raw)
    assert first.snapshot.components[0].dependency_path == ("root", "leaf")
    assert second.snapshot.components[0].dependency_path == ("leaf", "root")
    assert first.snapshot.components[0].component_id != second.snapshot.components[0].component_id
    assert first.snapshot.snapshot_sha256 != second.snapshot.snapshot_sha256


@pytest.mark.parametrize("version", ["1.10.0", "01.0.0"])
def test_explicit_versions_are_preserved_without_coercion(version):
    raw = json.dumps(
        {
            "format_version": 1,
            "components": [{"package_name": "langchain", "ecosystem": "PyPI", "version": version}],
        }
    ).encode()
    result = parse_input(raw)
    assert result.snapshot.components[0].version == version
    assert result.snapshot.components[0].version_scheme == "pep440"
    assert result.source_bytes == raw


class KnownOffsetFailure(tzinfo):
    def __init__(self, error_type):
        self.error_type = error_type

    def utcoffset(self, value):
        raise self.error_type("synthetic-private-error-canary")


@pytest.mark.parametrize("field", ["observed_at", "recorded_at"])
@pytest.mark.parametrize("error_type", [TypeError, OverflowError])
def test_known_offset_failures_are_typed_and_do_not_expose_exception_values(field, error_type):
    timestamp = datetime(2026, 10, 15, 19, tzinfo=KnownOffsetFailure(error_type))
    with pytest.raises(ManifestValidationError) as caught:
        parse_input(raw_input("json_manifest_v1"), "json_manifest_v1", field, timestamp)
    assert caught.value.code == "invalid_timestamp"
    assert caught.value.locator == f"/{field}"
    assert "synthetic-private-error-canary" not in str(caught.value)
