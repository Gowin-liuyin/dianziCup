"""Only the scheduling namespace changes; the worker protocol and rule remain frozen."""

import hashlib
from uuid import UUID

from ai_intel.enrichment.job_service import RULE_VERSION, _enrichment_idempotency_key
from ai_intel.enrichment.job_types import EnrichmentJobPayload, json_payload


def test_fixed_json_scope_has_a_stable_protocol_digest_and_no_delimiter_encoding():
    raw = (
        b'{"actor_user_id":"actor","idempotency_key":"key",'
        b'"namespace_version":"r07-scope-v2",'
        b'"route":"/v1/events/00000000-0000-0000-0000-000000000001/enrichment-jobs",'
        b'"tenant_id":null}'
    )
    expected = "r07-scope-v2:" + hashlib.sha256(raw).hexdigest()
    assert _enrichment_idempotency_key(None, UUID(int=1), "actor", "key") == expected


def test_execution_rule_and_parent_payload_fields_are_not_upgraded():
    assert RULE_VERSION == "r07-enrichment-workflow-1"
    payload = EnrichmentJobPayload(workflow_id=UUID(int=1), binding_sha256="a" * 64)
    assert set(payload.model_dump()) == {"workflow_id", "binding_sha256", "step_key"}
    assert b"namespace_version" not in json_payload(payload)
