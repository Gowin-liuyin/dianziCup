"""不透明游标和公开URI边界；显式隔离unit，不算live。"""

import base64
import json
from datetime import UTC, datetime
from uuid import UUID

import pytest
from pydantic import ValidationError

from ai_intel.api.knowledge_read_service import (
    EventFilters,
    InvalidEventCursor,
    decode_event_cursor,
    safe_source_uri,
)


def encoded(payload: object) -> str:
    return base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")


@pytest.mark.parametrize("field", ["q", "product", "risk_type"])
@pytest.mark.parametrize("value", ["invalid\x00text", "invalid\ud800text"])
def test_search_filters_reject_non_database_text(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        EventFilters(**{field: value})


def test_cursor_matches_full_filters_and_timezone() -> None:
    filters = EventFilters(
        q="%_中文",
        product="vLLM",
        risk_type="risk",
        updated_after=datetime(2026, 10, 15, tzinfo=UTC),
    )
    payload = {
        "version": 1,
        "first_seen_at": "2026-10-15T00:00:00Z",
        "event_id": "10000000-0000-0000-0000-000000000001",
        "filters_sha256": filters.fingerprint(),
    }
    cursor = decode_event_cursor(encoded(payload), filters)
    assert cursor.event_id == UUID(payload["event_id"])
    assert cursor.first_seen_at == datetime(2026, 10, 15, tzinfo=UTC)
    for changed in (
        EventFilters(),
        filters.model_copy(update={"product": "other"}),
        filters.model_copy(update={"q": "different"}),
        filters.model_copy(update={"risk_type": "other"}),
        filters.model_copy(update={"updated_after": None}),
    ):
        with pytest.raises(InvalidEventCursor):
            decode_event_cursor(encoded(payload), changed)


@pytest.mark.parametrize("cursor", ["", "?", "a" * 2049, "e30", "bnVsbA", "W10", "a"])
def test_invalid_cursor_rejected(cursor: str) -> None:
    with pytest.raises(InvalidEventCursor):
        decode_event_cursor(cursor, EventFilters())


@pytest.mark.parametrize(
    "change",
    [
        {"first_seen_at": "2026-10-15T00:00:00"},
        {"event_id": "not-a-uuid"},
        {"version": True},
        {"version": 2},
        {"extra": "not-allowed"},
        {"filters_sha256": "bad"},
        {"first_seen_at": None},
    ],
)
def test_cursor_fields_strict(change: dict[str, object]) -> None:
    payload = {
        "version": 1,
        "first_seen_at": "2026-10-15T00:00:00Z",
        "event_id": "10000000-0000-0000-0000-000000000001",
        "filters_sha256": EventFilters().fingerprint(),
    }
    payload.update(change)
    with pytest.raises(InvalidEventCursor):
        decode_event_cursor(encoded(payload), EventFilters())


def test_duplicate_key_cursor_rejected() -> None:
    payload = '{"version":1,"version":1,"first_seen_at":"2026-10-15T00:00:00Z",'
    payload += (
        '"event_id":"10000000-0000-0000-0000-000000000001","filters_sha256":"' + "a" * 64 + '"}'
    )
    with pytest.raises(InvalidEventCursor):
        decode_event_cursor(
            base64.urlsafe_b64encode(payload.encode()).decode().rstrip("="), EventFilters()
        )


@pytest.mark.parametrize(
    "value",
    [
        None,
        "file:///private/object",
        "s3://bucket/key",
        "https://user:password@example.invalid/document",
        "https://example.invalid/?api_key=secret",
        "https://example.invalid/?%61pi_key=secret",
        "https://example.invalid/document#credential",
    ],
)
def test_private_uri_not_returned(value: str | None) -> None:
    assert safe_source_uri(value) is None


def test_public_uri_preserved_without_guessing() -> None:
    assert str(safe_source_uri("https://example.invalid/document?id=public")) == (
        "https://example.invalid/document?id=public"
    )
