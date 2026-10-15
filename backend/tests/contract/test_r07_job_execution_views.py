"""Workflow view schema is bounded and cannot project stored authority or input text."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.enrichment.job_types import EnrichmentJobPayload, EnrichmentWorkflowView


def test_public_workflow_projection_has_only_typed_safe_fields():
    view = EnrichmentWorkflowView(
        workflow_id=uuid4(),
        parent_job_id=uuid4(),
        event_id=uuid4(),
        data_mode="fixture",
        parent_status="succeeded",
        scheduling_complete=True,
        workflow_complete=False,
        publication_status="queued",
        logical_dimensions=(),
        steps=(),
        created_at=datetime.now(UTC),
        initialized_at=None,
    )
    encoded = view.model_dump_json()
    assert "actor_session_hash" not in encoded and "input_context" not in encoded
    assert not view.workflow_complete and view.scheduling_complete
    with pytest.raises(ValidationError):
        EnrichmentWorkflowView.model_validate({**view.model_dump(), "raw_prompt": "forbidden"})


@pytest.mark.parametrize(
    "field",
    ["tenant_id", "role", "egress_granted", "api_key", "model", "session_token", "raw_prompt"],
)
def test_internal_job_payload_rejects_body_authority_and_secrets(field):
    with pytest.raises(ValidationError):
        EnrichmentJobPayload.model_validate(
            {"workflow_id": uuid4(), "binding_sha256": "a" * 64, field: "forbidden"}
        )
