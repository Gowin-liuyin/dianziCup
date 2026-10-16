"""Audit is an internal strict contract; public jobs and workflow response shapes stay stable."""

import pytest
from pydantic import ValidationError

from ai_intel.enrichment.job_contracts import (
    EnrichmentExecutionPolicy,
    EnrichmentModelInputVersions,
    EventEnrichmentRequest,
)
from ai_intel.enrichment.job_models import enrichment_job_steps
from ai_intel.enrichment.job_types import (
    MAX_INPUT_AUDIT_BYTES,
    EnrichmentInputAuditView,
    EnrichmentWorkflowView,
)


def test_legacy_policy_does_not_invent_selector_or_prompt_versions():
    policy = EnrichmentExecutionPolicy.model_validate_json('{"data_mode":"fixture"}')
    assert policy.model_input_versions is None
    assert EnrichmentInputAuditView.model_fields["record"].is_required()


@pytest.mark.parametrize(
    "payload",
    [
        {"prompt_version": "p", "selection_version": "s"},
        {"prompt_version": 1, "selection_version": "s", "schema_version": "o"},
        {
            "prompt_version": "p",
            "selection_version": "s",
            "schema_version": "o",
            "egress_granted": True,
        },
    ],
)
def test_server_version_contract_rejects_missing_coercion_or_grants(payload):
    with pytest.raises(ValidationError):
        EnrichmentModelInputVersions.model_validate(payload)


def test_http_request_cannot_set_server_input_versions_or_audit():
    with pytest.raises(ValidationError):
        EventEnrichmentRequest.model_validate(
            {"expected_event_version": 1, "model_input_versions": {"prompt_version": "body"}}
        )
    assert not {
        "input_audit",
        "record",
        "input_selections",
        "quoted_text",
        "model_input_versions",
    }.intersection(EnrichmentWorkflowView.model_fields)


def test_append_columns_are_nullable_and_no_second_job_state_is_added():
    assert enrichment_job_steps.c.input_audit_payload.nullable
    assert enrichment_job_steps.c.input_audit_sha256.nullable
    assert "status" not in enrichment_job_steps.c
    assert MAX_INPUT_AUDIT_BYTES == 4194304
