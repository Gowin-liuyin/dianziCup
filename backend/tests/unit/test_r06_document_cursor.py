"""资料分页绑定过滤条件，不能把非法游标当首页成功。"""

import base64
import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.api.document_read_service import (
    DocumentFilters,
    InvalidDocumentCursor,
    decode_document_cursor,
    encode_document_cursor,
)


def test_document_cursor_roundtrip_keeps_filter_and_position():
    document_id = uuid4()
    at = datetime(2026, 10, 15, 10, tzinfo=UTC)
    filters = DocumentFilters(q="prompt injection", document_kind="paper")
    result = decode_document_cursor(encode_document_cursor(at, document_id, filters), filters)
    assert result.document_id == document_id and result.ingested_at == at


def test_document_cursor_cannot_be_reused_for_other_filters():
    value = encode_document_cursor(datetime.now(UTC), uuid4(), DocumentFilters(q="original"))
    with pytest.raises(InvalidDocumentCursor):
        decode_document_cursor(value, DocumentFilters(q="changed"))


@pytest.mark.parametrize("value", ["!", "a" * 2049, "e30", "bnVsbA"])
def test_invalid_document_cursor_is_rejected(value):
    with pytest.raises(InvalidDocumentCursor):
        decode_document_cursor(value, DocumentFilters())


def test_duplicate_cursor_keys_are_rejected_even_when_values_match():
    filters = DocumentFilters()
    encoded = encode_document_cursor(datetime.now(UTC), uuid4(), filters)
    payload = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4)).decode()
    duplicated = payload[:-1] + ',"version":1}'
    value = base64.urlsafe_b64encode(duplicated.encode()).decode().rstrip("=")
    assert json.loads(duplicated)["version"] == 1
    with pytest.raises(InvalidDocumentCursor):
        decode_document_cursor(value, filters)


@pytest.mark.parametrize("fields", [{"q": "bad\x00query"}, {"document_kind": "asset_inventory"}])
def test_document_filters_reject_private_kind_or_invalid_text(fields):
    with pytest.raises(ValidationError):
        DocumentFilters.model_validate(fields)
