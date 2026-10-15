"""Canonical scope identity keeps independent subjects, routes and nullable tenants apart."""

from uuid import UUID

import pytest

from ai_intel.enrichment.job_service import _enrichment_idempotency_key

EVENT = UUID("00000000-0000-0000-0000-000000000001")


def test_same_identity_is_stable_but_each_authority_or_route_component_matters():
    first = _enrichment_idempotency_key(None, EVENT, "actor", "key")
    assert first == _enrichment_idempotency_key(None, UUID(str(EVENT).upper()), "actor", "key")
    alternatives = (
        _enrichment_idempotency_key("public", EVENT, "actor", "key"),
        _enrichment_idempotency_key(None, UUID(int=2), "actor", "key"),
        _enrichment_idempotency_key(None, EVENT, "other", "key"),
        _enrichment_idempotency_key(None, EVENT, "actor", "different-key"),
    )
    assert len({first, *alternatives}) == 5


def test_delimiter_and_unicode_values_do_not_alias_or_exceed_pg_key_budget():
    assert _enrichment_idempotency_key("a:b", EVENT, "c", "d") != _enrichment_idempotency_key(
        "a", EVENT, "b:c", "d"
    )
    assert _enrichment_idempotency_key(
        None, EVENT, "actor:key", "part"
    ) != _enrichment_idempotency_key(None, EVENT, "actor", "key:part")
    namespaced = _enrichment_idempotency_key(None, EVENT, "用户|actor", "🙂" * 200)
    assert namespaced.startswith("r07-scope-v2:") and len(namespaced.encode()) == 77


@pytest.mark.parametrize("key", ["", " ", "a" * 201, "🙂" * 201])
def test_invalid_original_key_is_rejected_before_hashing(key):
    with pytest.raises(ValueError):
        _enrichment_idempotency_key(None, EVENT, "actor", key)
