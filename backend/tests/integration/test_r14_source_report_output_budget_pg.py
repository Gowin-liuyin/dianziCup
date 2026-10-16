"""Real authorized isolated PG, source bytes remain fixtures and models stay disabled."""

import copy
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import select, update
from test_r07_structured_fact_proofs_pg import seed_facts
from test_r14_langgraph_workflow_pg import claim, principal_session, workflow_resources

from ai_intel.api.credentials import SessionCredential
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.investigation import workflow_service as module
from ai_intel.investigation.capabilities import AgentRole
from ai_intel.investigation.checkpoint_runtime import open_postgres_checkpointer
from ai_intel.investigation.graph import OUTPUT_BUDGET_FAILURE, build_investigation_graph
from ai_intel.investigation.graph_contracts import InvestigationRequest, WorkflowBudget
from ai_intel.investigation.runtime import build_investigation_service
from ai_intel.investigation.tool_contracts import ReadEvidenceArguments
from ai_intel.investigation.workflow_service import _initial_state, _WorkflowRuntime
from ai_intel.knowledge.models import job_runs, scope_epochs, users
from ai_intel.workers.jobs import JobLeaseLostError

pytestmark = pytest.mark.real_pg
__all__ = ["workflow_resources"]


@pytest.fixture
def runtime_case(workflow_resources, tmp_path, register_sensitive_failure_value, request):
    engine, _, schema = workflow_resources
    facts = seed_facts(engine, tmp_path, register_sensitive_failure_value)
    user_id, token = principal_session(engine, register_sensitive_failure_value)
    settings = ApplicationSettings(
        app_env="test", data_mode="fixture", raw_content_directory=str(tmp_path / "content")
    )
    service = build_investigation_service(
        engine, settings, SessionCredential(SecretStr(token)), checkpoint_schema=schema
    )
    investigation = InvestigationRequest(
        question="Read the saved synthetic source report.",
        event_id=facts.request.event_id,
        evidence_refs=(ReadEvidenceArguments(**facts.request.model_dump()),),
    )
    budget = WorkflowBudget(max_output_bytes=getattr(request, "param", 262144))
    job_id = service.enqueue(investigation, budget, idempotency_key=uuid4().hex)
    return engine, facts, service, job_id, claim(engine, job_id), user_id


@contextmanager
def runtime_for(case):
    engine, _, service, _, context, _ = case
    with engine.connect() as connection:
        runtime = _WorkflowRuntime(service, connection, context)
        runtime.guard(require_lease=True)
        yield runtime


def test_default_factory_consumes_real_pg_original_source_proof_without_promoting_qa_support(
    runtime_case,
):
    engine, facts, service, job_id, context, _ = runtime_case
    result = service.execute(context)
    output = next(
        receipt.output for receipt in result.receipts if receipt.role == AgentRole.ENRICHER
    )
    assert output["source_report_read_status"] == "reported"
    report = output["source_reports"][0]
    assert report["request"]["evidence_id"] == str(facts.request.evidence_id)
    assert report["facts"][0]["record"]["condition_value"] == "unknown"
    assert report["facts"][0]["record"]["freshness"] == "unknown"
    assert result.answer is None and result.evidence_ids == ()
    with engine.connect() as connection:
        original = list(
            connection.execute(
                select(module.investigation_operations).where(
                    module.investigation_operations.c.job_id == str(job_id)
                )
            ).mappings()
        )
    replay = service.execute(context)
    assert replay == result and service.read_result(job_id) == result
    with engine.connect() as connection:
        replayed = list(
            connection.execute(
                select(module.investigation_operations).where(
                    module.investigation_operations.c.job_id == str(job_id)
                )
            ).mappings()
        )
    assert replayed == original
    assert all(row["model_calls"] == 0 for row in replayed)


@pytest.mark.parametrize("runtime_case", [1024], indirect=True)
def test_real_pg_actual_chinese_budget_failure_preserves_reservation_and_replay_receipt(
    runtime_case,
):
    engine, _, service, job_id, _, _ = runtime_case
    with runtime_for(runtime_case) as runtime:
        assert (
            runtime.reserve("node:enricher", "node", AgentRole.ENRICHER, b"fixture", input_bytes=0)
            is None
        )
        original_bytes = module.OUTPUT_BUDGET_FAILURE_BYTES
        assert (
            runtime.complete_operation("node:enricher", {"report": "中" * 400})
            == OUTPUT_BUDGET_FAILURE
        )
        assert (
            runtime.complete_operation("node:enricher", {"replacement": "small"})
            == OUTPUT_BUDGET_FAILURE
        )
        restored = runtime.restore_node_state(
            {
                **_initial_state(runtime.input_sha256),
                "stop_reason": "model_outcome_unknown",
                "verified": True,
                "draft": {"secret": "rejected"},
            }
        )
        assert restored["stop_reason"] == OUTPUT_BUDGET_FAILURE
        assert restored["draft"] is None and not restored["verified"]
    with engine.connect() as connection:
        row = (
            connection.execute(
                select(module.investigation_operations).where(
                    module.investigation_operations.c.job_id == str(job_id)
                )
            )
            .mappings()
            .one()
        )
    assert row["output_bytes"] == original_bytes
    assert row["output_json"] == {"error_code": OUTPUT_BUDGET_FAILURE} and row["status"] == "failed"
    assert service.read_result(job_id).stop_reason == OUTPUT_BUDGET_FAILURE


@pytest.mark.parametrize("runtime_case", [1024], indirect=True)
def test_real_pg_completed_actual_and_pending_reservations_share_one_cumulative_budget(
    runtime_case,
):
    with runtime_for(runtime_case) as runtime:
        assert (
            runtime.reserve("node:enricher", "node", AgentRole.ENRICHER, b"fixture", input_bytes=0)
            is None
        )
        assert (
            runtime.reserve(
                "model:pending", "model", AgentRole.QA, b"fixture", model_calls=1, output_bytes=800
            )
            is None
        )
        assert (
            runtime.complete_operation("node:enricher", {"report": "中" * 80})
            == OUTPUT_BUDGET_FAILURE
        )
        assert runtime.lookup("model:pending") == {"error_code": "model_outcome_unknown"}


@pytest.mark.parametrize("runtime_case", [1024], indirect=True)
def test_real_pg_workflow_lock_serializes_simultaneous_actual_output_decisions(runtime_case):
    engine, _, service, _, context, _ = runtime_case
    with runtime_for(runtime_case) as runtime:
        for role in (AgentRole.ENRICHER, AgentRole.QA):
            assert (
                runtime.reserve("node:" + role.value, "node", role, b"fixture", input_bytes=0)
                is None
            )

    def complete(role):
        with engine.connect() as connection:
            runtime = _WorkflowRuntime(service, connection, context)
            runtime.guard(require_lease=True)
            return runtime.complete_operation("node:" + role.value, {"report": "中" * 230})

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(complete, (AgentRole.ENRICHER, AgentRole.QA)))
    assert results.count(None) == 1 and results.count(OUTPUT_BUDGET_FAILURE) == 1


@pytest.mark.parametrize("mutation", ["acl", "epoch", "lease"])
def test_source_io_revalidates_current_acl_epoch_and_job_lease_before_node_receipt(
    runtime_case, mutation
):
    engine, facts, service, job_id, _, user_id = runtime_case
    changed = False

    class MutatingStore:
        def read_verified(self, content_hash):
            nonlocal changed
            value = facts.store.read_verified(content_hash)
            if not changed:
                changed = True
                with engine.begin() as connection:
                    if mutation == "acl":
                        connection.execute(
                            update(users).where(users.c.user_id == user_id).values(role="viewer")
                        )
                    elif mutation == "epoch":
                        connection.execute(
                            update(scope_epochs)
                            .where(scope_epochs.c.scope_key == "public")
                            .values(epoch=scope_epochs.c.epoch + 1)
                        )
                    else:
                        connection.execute(
                            update(job_runs)
                            .where(job_runs.c.job_id == str(job_id))
                            .values(lease_expires_at=datetime.now(UTC))
                        )
            return value

        def store_bytes(self, payload):
            return facts.store.store_bytes(payload)

        def delete_object(self, content_hash):
            facts.store.delete_object(content_hash)

    service._content_store = MutatingStore()
    expected = (
        CrossTenantAccessError
        if mutation == "acl"
        else module.WorkflowChangedError
        if mutation == "epoch"
        else JobLeaseLostError
    )
    with runtime_for(runtime_case) as runtime, pytest.raises(expected):
        runtime.run_role(AgentRole.ENRICHER, _initial_state(runtime.input_sha256))
    with engine.connect() as connection:
        row = (
            connection.execute(
                select(module.investigation_operations).where(
                    module.investigation_operations.c.job_id == str(job_id)
                )
            )
            .mappings()
            .one()
        )
    assert changed and row["status"] == "reserved" and row["output_json"] is None


@pytest.mark.parametrize(
    "version", ["_source_report_consumer_version", "_operation_output_accounting_version"]
)
def test_changed_configuration_stops_without_replaying_or_rewriting_history(runtime_case, version):
    engine, _, service, job_id, context, _ = runtime_case
    with engine.connect() as connection:
        original = copy.deepcopy(
            connection.execute(
                select(module.investigation_workflows).where(
                    module.investigation_workflows.c.job_id == str(job_id)
                )
            )
            .mappings()
            .one()
        )
    setattr(service, version, "older-configuration")
    result = service.execute(context)
    assert result.status == "stale" and result.stop_reason == "workflow_inputs_changed"
    with engine.connect() as connection:
        unchanged = (
            connection.execute(
                select(module.investigation_workflows).where(
                    module.investigation_workflows.c.job_id == str(job_id)
                )
            )
            .mappings()
            .one()
        )
        operations = list(
            connection.execute(
                select(module.investigation_operations).where(
                    module.investigation_operations.c.job_id == str(job_id)
                )
            )
        )
    assert original == unchanged and operations == []


@pytest.mark.parametrize("runtime_case", [1024], indirect=True)
@pytest.mark.parametrize("strategy", ["B2", "B2b", "B3"])
def test_real_pg_large_source_report_is_absent_from_graph_checkpoints_and_public_result(
    runtime_case, strategy
):
    _, _, service, job_id, _, _ = runtime_case
    with (
        runtime_for(runtime_case) as runtime,
        open_postgres_checkpointer(
            service._checkpoint_connection_string, service._checkpoint_schema, 30
        ) as saver,
    ):
        graph = build_investigation_graph(
            strategy, lambda role, state: runtime.run_role(AgentRole.ENRICHER, state), saver
        )
        config = {"configurable": {"thread_id": "test-budget-" + str(job_id)}}
        state = graph.invoke(_initial_state(runtime.input_sha256), config)
        assert state["stop_reason"] == OUTPUT_BUDGET_FAILURE and state["receipts"] == []
        for checkpoint in saver.list(config):
            for value in checkpoint.checkpoint["channel_values"].values():
                assert "source_reports" not in str(value)
    result = service.read_result(job_id)
    assert result.stop_reason == OUTPUT_BUDGET_FAILURE
    assert result.answer is None and result.receipts == () and result.evidence_ids == ()
