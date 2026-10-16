"""Explicit offline adapters verify the controlled gateway contract without external IO."""

import json
import time
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import ValidationError

from ai_intel.api.authentication import Principal
from ai_intel.api.knowledge_contracts import EventDetailResponse, EventSummary
from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.domain.enums import ToolStatus
from ai_intel.investigation.capabilities import AgentRole, available_tools
from ai_intel.investigation.read_adapters import ReadSnapshotChangedError, ReadToolOutcome
from ai_intel.investigation.tool_contracts import (
    ChangesPage,
    ChangeSummary,
    ToolName,
    ToolResult,
    UnconfiguredArguments,
    parse_tool_call,
)
from ai_intel.investigation.tool_gateway import BudgetLimits, ToolGateway

NOW = datetime(2026, 10, 16, tzinfo=UTC)
EVENT_ID, ASSET_ID, SNAPSHOT_ID, GOAL_ID = (uuid4() for _ in range(4))
ROLES = {
    "get_advisory": AgentRole.ENRICHER,
    "get_inventory": AgentRole.ASSESSOR,
    "find_changes": AgentRole.REPORTER,
}
ARGUMENTS = {
    "get_advisory": {"event_id": str(EVENT_ID)},
    "get_inventory": {"asset_id": str(ASSET_ID), "snapshot_id": str(SNAPSHOT_ID)},
    "find_changes": {"event_id": str(EVENT_ID), "limit": 2},
}


def typed_data(tool: str):
    if tool == "get_advisory":
        return EventDetailResponse(
            event=EventSummary(
                event_id=EVENT_ID,
                event_type="fixture",
                title="fixture event",
                external_ids=(),
                primary_product_ids=(),
                first_seen_at=NOW,
                status="active",
                source_count=0,
                latest_revision_id=None,
                freshness="unknown",
            ),
            dimensions=(),
            revisions=(),
            claims=(),
            data_mode="fixture",
        )
    if tool == "get_inventory":
        return AssetSnapshotResponse(
            schema_version="r11-asset-candidate-1",
            snapshot_id=str(SNAPSHOT_ID),
            asset_id=str(ASSET_ID),
            tenant_id="owner",
            snapshot_number=1,
            observed_at=NOW,
            recorded_at=NOW,
            source_kind="fixture",
            inventory_completeness="unknown",
            declared_scope=(),
            components=(),
            configuration=(),
            tool_permissions=None,
            input_channels=None,
            network_exposure=None,
            snapshot_sha256="a" * 64,
        )
    return ChangesPage(event_id=EVENT_ID, items=(), next_cursor=None, data_mode="fixture")


class FixtureReadAdapter:
    data_mode = "fixture"
    configured_tools = frozenset(ToolName(name) for name in ROLES)

    def __init__(self) -> None:
        self.calls = 0
        self.scopes: list[AccessScope] = []
        self.error: Exception | None = None
        self.status = ToolStatus.SUCCEEDED

    def read_tool(self, principal, scope, call, deadline_monotonic):
        self.calls += 1
        self.scopes.append(scope)
        if self.error is not None:
            raise self.error
        return ReadToolOutcome(typed_data(call.tool_name), self.status, None, NOW, ())


def call_bytes(tool: str, arguments: dict | None = None) -> bytes:
    return json.dumps(
        {
            "tool_name": tool,
            "goal_id": str(GOAL_ID),
            "arguments": ARGUMENTS[tool] if arguments is None else arguments,
        }
    ).encode()


def gateway(adapter=None, **changes):
    limits = BudgetLimits.model_validate(
        {
            "max_calls": 8,
            "max_concurrent_calls": 1,
            "max_request_bytes": 4096,
            "max_total_input_bytes": 32768,
            "max_result_bytes": 8192,
            "max_total_output_bytes": 65536,
            "deadline_monotonic": time.monotonic() + 10,
            **changes,
        }
    )
    return ToolGateway(
        Principal("fixture-user", "owner", Role.ANALYST), uuid4(), limits, read_adapter=adapter
    )


@pytest.mark.parametrize("tool", ROLES)
def test_real_dto_passes_gateway_and_result_union(tool):
    adapter = FixtureReadAdapter()
    subject = gateway(adapter)
    result = subject.execute(ROLES[tool], call_bytes(tool))
    assert result.status == "succeeded" and result.data == typed_data(tool)
    assert result.evidence_ids == () and result.is_synthetic
    assert result.usage.service_calls == 1 and not result.usage.cached
    assert result.usage.result_bytes == len(result.model_dump_json().encode())
    assert ToolResult.model_validate_json(result.model_dump_json()).data == result.data
    assert adapter.scopes[0].tenant_id == ("owner" if tool == "get_inventory" else None)
    assert available_tools("B3", subject.configured_tools) == subject.configured_tools


@pytest.mark.parametrize("tool", ROLES)
def test_read_replay_including_empty_and_partial_rechecks_adapter(tool):
    adapter = FixtureReadAdapter()
    adapter.status = ToolStatus.NO_RESULT if tool == "find_changes" else ToolStatus.PARTIAL
    subject = gateway(adapter)
    first = subject.execute(ROLES[tool], call_bytes(tool))
    second = subject.execute(ROLES[tool], call_bytes(tool))
    assert first.status == second.status == adapter.status
    assert adapter.calls == 2 and not second.usage.cached
    adapter.error = PermissionDeniedError("fixture revoked")
    revoked = subject.execute(ROLES[tool], call_bytes(tool))
    assert revoked.status == "denied" and revoked.data is None
    assert revoked.evidence_ids == () and "fixture revoked" not in revoked.model_dump_json()


@pytest.mark.parametrize("tool", ROLES)
def test_missing_adapter_retains_legacy_empty_input_shape(tool):
    for arguments in ({}, ARGUMENTS[tool]):
        result = gateway().execute(ROLES[tool], call_bytes(tool, arguments))
        assert result.status == "not_configured" and result.error_code == "tool_not_configured"
        assert result.usage.service_calls == 0 and result.data is None
        assert not result.is_synthetic


@pytest.mark.parametrize("tool", ROLES)
def test_configured_empty_arguments_never_read_all_objects(tool):
    adapter = FixtureReadAdapter()
    parsed = parse_tool_call(call_bytes(tool, {}), 4096)
    assert isinstance(parsed.arguments, UnconfiguredArguments)
    result = gateway(adapter).execute(ROLES[tool], call_bytes(tool, {}))
    assert result.status == "denied" and result.error_code == "invalid_arguments"
    assert adapter.calls == 0


@pytest.mark.parametrize("tool", ROLES)
@pytest.mark.parametrize(
    "field,value",
    [
        ("tenant_id", "other"),
        ("actor", "admin"),
        ("url", "http://127.0.0.1/"),
        ("sql", "SELECT secret"),
        ("shell", "whoami"),
    ],
)
def test_model_cannot_inject_authority_or_freeform_execution(tool, field, value):
    adapter = FixtureReadAdapter()
    arguments = {**ARGUMENTS[tool], field: value}
    result = gateway(adapter).execute(ROLES[tool], call_bytes(tool, arguments))
    assert result.status == "denied" and result.error_code == "invalid_tool_input"
    assert adapter.calls == 0


@pytest.mark.parametrize("limit", [0, 26, True, "2", -1])
def test_change_limit_is_strict_and_bounded(limit):
    result = gateway(FixtureReadAdapter()).execute(
        AgentRole.REPORTER, call_bytes("find_changes", {"event_id": str(EVENT_ID), "limit": limit})
    )
    assert result.error_code == "invalid_tool_input"


@pytest.mark.parametrize("tool", ROLES)
def test_wrong_role_cannot_use_read_adapter(tool):
    adapter = FixtureReadAdapter()
    result = gateway(adapter).execute(AgentRole.ORCHESTRATOR, call_bytes(tool))
    assert result.error_code == "role_tool_denied" and adapter.calls == 0


@pytest.mark.parametrize("tool", ROLES)
def test_call_and_deadline_budget_still_precede_io(tool):
    adapter = FixtureReadAdapter()
    subject = gateway(adapter, max_calls=1)
    assert subject.execute(ROLES[tool], call_bytes(tool)).usage.service_calls == 1
    assert subject.execute(ROLES[tool], call_bytes(tool)).error_code == "call_budget_exhausted"
    assert adapter.calls == 1
    expired = gateway(adapter, deadline_monotonic=time.monotonic() - 1)
    assert expired.execute(ROLES[tool], call_bytes(tool)).error_code == "deadline_exhausted"
    assert adapter.calls == 1


def test_source_snapshot_failure_is_partial_without_old_data():
    adapter = FixtureReadAdapter()
    adapter.error = ReadSnapshotChangedError("fixture ACL changed")
    result = gateway(adapter).execute(AgentRole.REPORTER, call_bytes("find_changes"))
    assert result.status == "partial" and result.error_code == "read_snapshot_changed"
    assert result.data is None and "ACL changed" not in result.model_dump_json()


def test_change_summary_rejects_raw_payload_and_private_identifiers():
    with pytest.raises(ValidationError):
        ChangeSummary(
            change_id=uuid4(),
            change_type="events_published",
            knowledge_epoch=1,
            recorded_at=NOW,
            payload={"private_source_id": str(uuid4())},
        )
    with pytest.raises(ValidationError):
        ChangesPage(event_id=EVENT_ID, items=(), data_mode="fixture", source_ids=())
