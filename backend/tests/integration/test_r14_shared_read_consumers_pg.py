"""Real PG tests require an explicitly authorized slot; source/model content remains fixture."""

import json
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_r14_langgraph_workflow_pg import (
    claim,
    evidence_request,
    fixture_factory,
    principal_session,
    service,
    workflow_resources,
)
from test_r14_read_adapters_pg import store_asset

from ai_intel.api.authentication import Principal
from ai_intel.assets.inventory import InventoryService
from ai_intel.domain.access import AccessScope, Role
from ai_intel.investigation import workflow_service
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.graph_contracts import WorkflowBudget
from ai_intel.investigation.read_adapters import PostgresReadToolAdapter
from ai_intel.investigation.workflow_service import investigation_operations
from ai_intel.knowledge.models import job_runs, scope_epochs
from ai_intel.knowledge.persistence_models import change_events, claims

pytestmark = pytest.mark.real_pg
__all__ = ["workflow_resources"]


@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
def test_real_pg_graph_reads_advisory_fixed_inventory_all_change_pages_and_replays(
    workflow_resources, tmp_path, register_sensitive_failure_value, monkeypatch, strategy
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path, strategy=strategy)
    publisher_id, _ = principal_session(
        engine, register_sensitive_failure_value, role="tenant_admin"
    )
    scope = AccessScope.for_authenticated_user(publisher_id, "fixture-owner", Role.TENANT_ADMIN)
    with Session(engine) as session, session.begin():
        imported = InventoryService(session, scope).import_manifest(
            json.dumps(
                {
                    "format_version": 1,
                    "components": [
                        {"ecosystem": "pypi", "package_name": "fixture-package", "version": "1.0"}
                    ],
                }
            ).encode(),
            manifest_format="json_manifest_v1",
            display_name="Fixture consumer asset",
            source_version="fixture-consumer-1",
            observed_at=datetime.now(UTC),
            idempotency_key=uuid4().hex,
        )
    request = request.model_copy(
        update={
            "asset_id": UUID(imported.asset_id),
            "asset_snapshot_id": UUID(imported.snapshot.snapshot_id),
        }
    )
    now = datetime.now(UTC)
    with engine.begin() as connection:
        public_epoch = connection.scalar(
            select(scope_epochs.c.epoch)
            .where(scope_epochs.c.scope_key == "public")
            .with_for_update()
        )
        assert isinstance(public_epoch, int)
        connection.execute(
            change_events.insert(),
            [
                {
                    "change_id": str(uuid4()),
                    "scope_key": "public",
                    "epoch": public_epoch + index + 1,
                    "change_type": "knowledge_published",
                    "entity_ids": [str(request.event_id)],
                    "payload": {"fixture": True},
                    "created_at": now - timedelta(seconds=index),
                }
                for index in range(26)
            ],
        )
        connection.execute(
            update(scope_epochs)
            .where(scope_epochs.c.scope_key == "public")
            .values(epoch=public_epoch + 26)
        )
        original_fact_count = connection.scalar(select(func.count()).select_from(claims))
    read_calls = []
    original_read = PostgresReadToolAdapter.read_tool

    def observed_read(self, principal, current_scope, call, deadline_monotonic):
        assert not self._connection.in_transaction()
        result = original_read(self, principal, current_scope, call, deadline_monotonic)
        assert not self._connection.in_transaction()
        read_calls.append(call)
        return result

    monkeypatch.setattr(PostgresReadToolAdapter, "read_tool", observed_read)
    model_calls = []
    subject = service(workflow_resources, token, fixture_factory(monkeypatch, request, model_calls))
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="consumer-" + strategy)
    context = claim(engine, job_id)
    result = subject.execute(context)
    assert result.status == "partial" and result.stop_reason == "adapter_gaps"
    assert result.answer is not None and result.evidence_ids == (
        request.evidence_refs[0].evidence_id,
    )
    assert [call.tool_name for call in read_calls] == [
        "get_advisory",
        "get_inventory",
        "find_changes",
        "find_changes",
    ]
    receipts = {receipt.role.value: receipt for receipt in result.receipts}
    inventory = receipts["assessor"].output["inventory"]
    assert inventory["data"]["snapshot_id"] == str(request.asset_snapshot_id)
    assert inventory["data"]["snapshot_sha256"] == imported.snapshot.snapshot_sha256
    assert receipts["collector"].status == receipts["assessor"].status == "partial"
    report = receipts["reporter"].output
    assert report["changes_complete"] is True and report["changes_next_cursor"] is None
    assert [len(page["data"]["items"]) for page in report["changes_pages"]] == [25, 3]
    assert all(page["is_synthetic"] for page in report["changes_pages"])
    assert subject.execute(context).model_dump() == result.model_dump()
    assert len(read_calls) == 4
    with engine.connect() as connection:
        assert connection.scalar(select(func.count()).select_from(claims)) == original_fact_count
        rows = (
            connection.execute(
                select(investigation_operations).where(
                    investigation_operations.c.job_id == str(job_id),
                    investigation_operations.c.kind == "tool",
                )
            )
            .mappings()
            .all()
        )
        assert len(rows) == 6 and sum(row["tool_calls"] for row in rows) == 6
        assert {row["tool_name"] for row in rows} == {
            "get_advisory",
            "get_inventory",
            "find_changes",
            "read_evidence",
        }


def test_real_pg_consumer_version_change_stops_old_binding_before_new_read_or_model(
    workflow_resources, tmp_path, register_sensitive_failure_value, monkeypatch
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    calls = []
    subject = service(workflow_resources, token, fixture_factory(monkeypatch, request, calls))
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="consumer-version")
    context = claim(engine, job_id)
    monkeypatch.setattr(
        workflow_service, "SHARED_READ_CONSUMER_VERSION", "fixture-changed-consumer"
    )
    result = subject.execute(context)
    assert result.status == "stale" and result.stop_reason == "workflow_inputs_changed"
    assert result.receipts == () and calls == []
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(investigation_operations)
                .where(investigation_operations.c.job_id == str(job_id))
            )
            == 0
        )


def test_real_pg_terminal_consumer_version_change_returns_stale_without_overwriting_history(
    workflow_resources, tmp_path, register_sensitive_failure_value, monkeypatch
):
    engine, _, _ = workflow_resources
    _, token = principal_session(engine, register_sensitive_failure_value)
    subject = service(workflow_resources, token)
    job_id = subject.enqueue(
        evidence_request(engine, tmp_path), WorkflowBudget(), idempotency_key="terminal-version"
    )
    context = claim(engine, job_id)
    original = subject.execute(context)
    assert original.status == "partial"
    with engine.connect() as connection:
        operations_before = (
            connection.execute(
                select(investigation_operations).where(
                    investigation_operations.c.job_id == str(job_id)
                )
            )
            .mappings()
            .all()
        )
        job_before = (
            connection.execute(select(job_runs).where(job_runs.c.job_id == str(job_id)))
            .mappings()
            .one()
        )
    monkeypatch.setattr(
        workflow_service, "SHARED_READ_CONSUMER_VERSION", "fixture-changed-consumer"
    )
    result = subject.execute(context)
    assert result.status == "stale" and result.receipts == ()
    with engine.connect() as connection:
        assert (
            connection.execute(
                select(investigation_operations).where(
                    investigation_operations.c.job_id == str(job_id)
                )
            )
            .mappings()
            .all()
            == operations_before
        )
        assert (
            connection.execute(select(job_runs).where(job_runs.c.job_id == str(job_id)))
            .mappings()
            .one()
            == job_before
        )


@pytest.mark.parametrize(
    "unknown_key,role",
    [
        ("tool:collector:get_advisory", AgentRole.COLLECTOR),
        ("tool:assessor:get_inventory", AgentRole.ASSESSOR),
    ],
)
def test_real_pg_reserved_unknown_read_stops_later_roles_and_paid_operations(
    workflow_resources, tmp_path, register_sensitive_failure_value, monkeypatch, unknown_key, role
):
    engine, _, _ = workflow_resources
    user_id, token = principal_session(engine, register_sensitive_failure_value)
    request = evidence_request(engine, tmp_path)
    imported = store_asset(engine, Principal(user_id, "fixture-owner", Role.ANALYST))
    request = request.model_copy(
        update={
            "asset_id": UUID(imported.asset_id),
            "asset_snapshot_id": UUID(imported.snapshot.snapshot_id),
        }
    )
    calls = []
    subject = service(workflow_resources, token, fixture_factory(monkeypatch, request, calls))
    job_id = subject.enqueue(request, WorkflowBudget(), idempotency_key="unknown-" + role.value)
    context = claim(engine, job_id)
    with engine.begin() as connection:
        connection.execute(
            investigation_operations.insert().values(
                job_id=str(job_id),
                operation_key=unknown_key,
                call_key="f" * 64,
                kind="tool",
                role=role.value,
                status="reserved",
                request_sha256="e" * 64,
                tool_name="get_advisory" if role == AgentRole.COLLECTOR else "get_inventory",
                policy_version="r14-tool-gateway-1",
                pricing_version="unavailable",
                cost_status="unknown",
                input_bytes=0,
                output_bytes=16384,
                model_calls=0,
                tool_calls=1,
                created_at=datetime.now(UTC),
            )
        )
    result = subject.execute(context)
    assert result.status == "partial" and result.stop_reason == "operation_outcome_unknown"
    assert result.receipts[-1].role == role and calls == [] and result.answer is None
    assert [receipt.role for receipt in result.receipts] == list(AgentRole)[
        : list(AgentRole).index(role) + 1
    ]
    replay = subject.execute(context)
    assert replay.model_dump() == result.model_dump() and calls == []
    with engine.connect() as connection:
        rows = (
            connection.execute(
                select(investigation_operations).where(
                    investigation_operations.c.job_id == str(job_id)
                )
            )
            .mappings()
            .all()
        )
    assert not any(row["role"] in {"qa", "critic", "reporter"} for row in rows)
    assert sum(row["model_calls"] for row in rows) == 0
    reserved = next(row for row in rows if row["operation_key"] == unknown_key)
    assert reserved["status"] == "reserved" and reserved["output_json"] is None
