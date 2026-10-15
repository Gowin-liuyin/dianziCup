"""Public workflow output carries actual receipts and keeps paid-call authority out."""

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.api.enrichment_contracts import (
    EnrichmentDimensionResponse,
    EnrichmentEnqueueResponse,
    EnrichmentStepResponse,
    EnrichmentWorkflowResponse,
)
from ai_intel.domain.enums import DimensionStatus


def workflow_payload():
    child = uuid4()
    return {
        "workflow_id": uuid4(),
        "parent_job_id": uuid4(),
        "event_id": uuid4(),
        "data_mode": "live",
        "parent_status": "succeeded",
        "scheduling_complete": True,
        "workflow_complete": False,
        "publication_status": "queued",
        "logical_dimensions": (
            {
                "dimension": "versions",
                "status": "queued",
                "error_code": None,
                "job_ids": (child,),
                "result_status": DimensionStatus.PENDING,
            },
        ),
        "steps": (
            {
                "job_id": child,
                "step_key": "versions",
                "dimension": "versions",
                "provider": None,
                "status": "queued",
                "error_code": None,
                "output_token_budget": 1024,
                "model_call_state": "not_reserved",
                "model_attempts": (),
            },
        ),
        "created_at": datetime.now(UTC),
        "initialized_at": None,
    }


def test_dispatch_success_does_not_claim_finished_enrichment():
    response = EnrichmentWorkflowResponse.model_validate(workflow_payload())
    assert response.parent_status == "succeeded" and response.scheduling_complete
    assert not response.workflow_complete
    assert response.logical_dimensions[0].result_status == DimensionStatus.PENDING


def test_public_response_can_read_typed_internal_attributes():
    payload = workflow_payload()
    payload["logical_dimensions"] = tuple(
        SimpleNamespace(**row) for row in payload["logical_dimensions"]
    )
    payload["steps"] = tuple(SimpleNamespace(**row) for row in payload["steps"])
    response = EnrichmentWorkflowResponse.model_validate(
        SimpleNamespace(**payload), from_attributes=True
    )
    assert response.steps[0].model_attempts == ()


@pytest.mark.parametrize(
    "field", ["actor_session_hash", "raw_prompt", "generation_api_key", "tenant_id"]
)
def test_secret_or_identity_fields_are_not_public_workflow_fields(field):
    payload = workflow_payload()
    payload[field] = "synthetic-forbidden-field"
    with pytest.raises(ValidationError):
        EnrichmentWorkflowResponse.model_validate(payload)


@pytest.mark.parametrize("status", ["safe", "online", "100%", "ready"])
def test_invented_job_success_states_are_rejected(status):
    payload = workflow_payload()
    payload["parent_status"] = status
    with pytest.raises(ValidationError):
        EnrichmentWorkflowResponse.model_validate(payload)


def test_missing_receipt_has_explicit_interrupted_state():
    step = workflow_payload()["steps"][0]
    step.update(
        status="blocked",
        error_code="incomplete_interrupted",
        model_call_state="incomplete_interrupted",
    )
    response = EnrichmentStepResponse.model_validate(step)
    assert response.model_attempts == () and response.status == "blocked"


@pytest.mark.parametrize("count", [0, 10])
def test_requested_dimension_count_is_bounded(count):
    payload = workflow_payload()
    payload["logical_dimensions"] = payload["logical_dimensions"] * count
    with pytest.raises(ValidationError):
        EnrichmentWorkflowResponse.model_validate(payload)


def test_enqueue_response_contains_only_persisted_identifiers_and_replay_flag():
    response = EnrichmentEnqueueResponse(workflow_id=uuid4(), parent_job_id=uuid4(), reused=False)
    assert set(response.model_dump()) == {"workflow_id", "parent_job_id", "reused"}


def test_public_dimension_status_distinguishes_unknown_blocked_from_zero_exposure():
    response = EnrichmentDimensionResponse(
        dimension="exposure",
        status="blocked",
        error_code="aggregate_not_configured",
        job_ids=(uuid4(), uuid4()),
        result_status=DimensionStatus.BLOCKED,
    )
    assert response.result_status == DimensionStatus.BLOCKED
