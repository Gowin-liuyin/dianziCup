"""Internal workflow schemas reject model authority and preserve frozen tool/status contracts."""

import json
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.domain.enums import ToolStatus
from ai_intel.investigation.graph_contracts import InvestigationRequest, parse_investigation_request
from ai_intel.investigation.tool_contracts import ToolResult
from ai_intel.investigation.workflow_service import (
    investigation_operations,
    investigation_workflows,
)


def payload():
    event_id = str(uuid4())
    return {
        "question": "有哪些当前证据？",
        "event_id": event_id,
        "evidence_refs": [
            {"event_id": event_id, "evidence_id": str(uuid4()), "revision_id": str(uuid4())}
        ],
        "strategy": "B2b",
    }


def test_json_input_preserves_only_ids_and_question():
    original = payload()
    request = parse_investigation_request(json.dumps(original).encode())
    assert request.question == original["question"] and request.strategy == "B2b"
    assert str(request.event_id) == original["event_id"]


@pytest.mark.parametrize(
    "raw",
    [b'{"question":"a","question":"b"}', b'{"question":NaN}', b"x" * 65537],
    ids=["duplicate_keys", "nan", "oversized_input"],
)
def test_invalid_json_is_not_empty_unknown_success(raw):
    with pytest.raises(ValueError):
        parse_investigation_request(raw)


@pytest.mark.parametrize("authority", ["budget", "thread_id", "tenant_id", "allowed_tools"])
def test_wire_input_forbids_server_fields(authority):
    with pytest.raises(ValidationError):
        parse_investigation_request(json.dumps({**payload(), authority: {"forged": True}}).encode())


def test_state_authority_remains_job_and_tool_enum_is_unchanged():
    assert "status" not in investigation_workflows.c
    assert "actor_reference" in investigation_workflows.c
    assert investigation_operations.c.status is not None
    assert "tenant_id" not in InvestigationRequest.model_fields
    assert ToolResult.model_fields["status"].annotation is ToolStatus
    assert "budget_exhausted" in [status.value for status in ToolStatus]
