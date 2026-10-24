"""Explicit PG IO fixtures exercise the shared apply path and runtime batch qualification."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import MagicMock
from uuid import uuid4

import pytest

from ai_intel.domain.access import AccessScope, Role
from ai_intel.knowledge import graph_projection as projection
from ai_intel.knowledge import graph_runtime_policy as policy
from ai_intel.workers.executor import JobExecutionContext, JobExecutionError

PUBLIC = AccessScope.for_authenticated_user("offline-runtime", None, Role.VIEWER)
TENANT = AccessScope.for_authenticated_user("offline-runtime", "owned", Role.ANALYST)


def apply_fixture(
    monkeypatch,
    *,
    namespace="knowledge-graph",
    scope=PUBLIC,
    epochs=(("public", 1),),
    current_epochs=None,
    random_generation=False,
):
    partition = projection.partition_for_scope(scope)
    generation = (
        uuid4() if random_generation else policy.graph_generation_id(namespace, partition, epochs)
    )
    batch = projection.GraphProjectionBatch(
        batch_id=uuid4(),
        namespace=namespace,
        partition_key=partition,
        generation_id=generation,
        event_id=uuid4(),
        sequence=1,
        kind="tombstone",
        scope_epochs=epochs,
        input_sha256="a" * 64,
        full_graph_sha256="a" * 64,
        nodes=(),
        edges=(),
        captured_at=datetime.now(UTC),
    )
    manifest = projection.ReconciliationManifest(
        namespace=namespace,
        partition_key=partition,
        generation_id=generation,
        scope_epochs=epochs,
        manifest_sha256="b" * 64,
        page_count=1,
        event_count=1,
        captured_count=1,
    )
    slot = projection.ProjectionSlot(
        event_id=batch.event_id,
        captured_sequence=1,
        batch_id=batch.batch_id,
        payload_sha256="c" * 64,
    )
    session = MagicMock()
    session.execute.return_value.one_or_none.return_value = SimpleNamespace(
        tenant_id=scope.tenant_id,
        job_type="graph_apply",
    )
    context = JobExecutionContext(str(uuid4()), "offline-worker", 1, scope.tenant_id)
    reader = MagicMock(return_value=(batch, "c" * 64))
    epoch_reader = MagicMock(return_value=current_epochs or epochs)
    monkeypatch.setattr(projection, "read_projection_batch", reader)
    monkeypatch.setattr(projection, "_epochs", epoch_reader)
    monkeypatch.setattr(projection, "_manifest_entries", lambda *_a: ())
    monkeypatch.setattr(
        projection,
        "_state_row",
        lambda _s, _n, _p, _g, key, **_kw: {
            "body": (manifest if key == "partition" else slot).model_dump(mode="json"),
        },
    )
    updates = MagicMock()
    monkeypatch.setattr(projection, "_update_state", updates)
    store = MagicMock()
    store.apply_batch.return_value = projection.ProjectionReceipt(
        batch_id=batch.batch_id,
        sequence=1,
        payload_sha256="c" * 64,
        outcome="applied",
    )
    payload = ('{"batch_id":"' + str(batch.batch_id) + '"}').encode()
    return SimpleNamespace(
        batch=batch,
        scope=scope,
        session=session,
        context=context,
        reader=reader,
        epoch_reader=epoch_reader,
        updates=updates,
        store=store,
        payload=payload,
    )


@pytest.mark.parametrize(
    "changes,code",
    [
        ({"namespace": "other-graph"}, "graph_projection_namespace_denied"),
        ({"random_generation": True}, "graph_projection_generation_denied"),
    ],
)
def test_runtime_rejects_other_namespace_or_unbound_generation_before_store_and_ack(
    monkeypatch,
    changes,
    code,
):
    fixture = apply_fixture(monkeypatch, **changes)
    runtime = policy.build_graph_runtime_policy(MagicMock(), fixture.store, lambda *_a: PUBLIC)
    with pytest.raises(JobExecutionError, match=code) as rejected:
        runtime.job_handlers["graph_apply"](fixture.session, fixture.context, fixture.payload)
    assert rejected.value.blocked
    fixture.store.apply_batch.assert_not_called()
    fixture.updates.assert_not_called()
    fixture.epoch_reader.assert_not_called()
    fixture.reader.assert_called_once()


@pytest.mark.parametrize(
    "namespace,scope,epochs",
    [
        ("knowledge-graph", PUBLIC, (("public", 1),)),
        ("explicit-runtime", PUBLIC, (("public", 1),)),
        ("knowledge-graph", TENANT, (("public", 4), ("tenant:owned", 2))),
    ],
)
def test_runtime_applies_fixed_namespace_and_full_partition_epoch_generation(
    monkeypatch,
    namespace,
    scope,
    epochs,
):
    fixture = apply_fixture(monkeypatch, namespace=namespace, scope=scope, epochs=epochs)
    runtime = policy.build_graph_runtime_policy(
        MagicMock(), fixture.store, lambda *_a: scope, namespace=namespace
    )
    result = runtime.job_handlers["graph_apply"](fixture.session, fixture.context, fixture.payload)
    assert result.outcome == "succeeded"
    assert result.result_ref == "pg:graph_batch:" + str(fixture.batch.batch_id)
    fixture.reader.assert_called_once_with(fixture.session, scope, fixture.batch.batch_id)
    fixture.store.apply_batch.assert_called_once_with(fixture.batch, "c" * 64)


def test_runtime_cannot_reuse_generation_from_an_incomplete_tenant_epoch_map(monkeypatch):
    epochs = (("public", 4), ("tenant:owned", 2))
    fixture = apply_fixture(monkeypatch, scope=TENANT, epochs=epochs)
    wrong_generation = policy.graph_generation_id(
        "knowledge-graph", "tenant:owned", (("public", 4),)
    )
    fixture.reader.return_value = (
        fixture.batch.model_copy(update={"generation_id": wrong_generation}),
        "c" * 64,
    )
    runtime = policy.build_graph_runtime_policy(MagicMock(), fixture.store, lambda *_a: TENANT)
    with pytest.raises(JobExecutionError, match="graph_projection_generation_denied"):
        runtime.job_handlers["graph_apply"](fixture.session, fixture.context, fixture.payload)
    fixture.store.apply_batch.assert_not_called()
    fixture.updates.assert_not_called()


def test_historical_runtime_generation_keeps_ack_stale_without_becoming_current(monkeypatch):
    fixture = apply_fixture(monkeypatch, current_epochs=(("public", 2),))
    runtime = policy.build_graph_runtime_policy(MagicMock(), fixture.store, lambda *_a: PUBLIC)
    assert (
        runtime.job_handlers["graph_apply"](
            fixture.session,
            fixture.context,
            fixture.payload,
        ).outcome
        == "succeeded"
    )
    updated_manifest = fixture.updates.call_args_list[-1].args[2]
    assert updated_manifest.status == "stale" and updated_manifest.scope_epochs == (("public", 1),)


def test_server_only_restore_without_runtime_policy_keeps_random_generation_contract(monkeypatch):
    fixture = apply_fixture(monkeypatch, namespace="operator-restore", random_generation=True)
    handler = projection.build_graph_apply_handler(fixture.store, lambda *_a: PUBLIC)
    assert handler(fixture.session, fixture.context, fixture.payload).outcome == "succeeded"
    fixture.store.apply_batch.assert_called_once()


def test_runtime_rechecks_batch_partition_before_store_and_ack(monkeypatch):
    fixture = apply_fixture(monkeypatch)
    forged = fixture.batch.model_copy(update={"partition_key": "tenant:other"})
    fixture.reader.return_value = forged, "c" * 64
    runtime = policy.build_graph_runtime_policy(MagicMock(), fixture.store, lambda *_a: PUBLIC)
    with pytest.raises(JobExecutionError, match="graph_projection_scope_denied"):
        runtime.job_handlers["graph_apply"](fixture.session, fixture.context, fixture.payload)
    fixture.store.apply_batch.assert_not_called()
    fixture.updates.assert_not_called()
