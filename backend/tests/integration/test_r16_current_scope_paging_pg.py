"""Synthetic real-PG negatives bind current related ACLs and every continuation dimension."""

import json
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session
from tests.integration import test_r16_revalidation_runtime_pg as candidate

from ai_intel.knowledge.models import job_payloads, job_runs
from ai_intel.revalidation.candidates import CandidateDiscoveryError, CandidateDiscoveryService
from ai_intel.revalidation.execution_contracts import RevalidationChangeRequest
from ai_intel.revalidation.runtime_policy import (
    REVALIDATION_CHANGE_JOB_TYPE,
    _enqueue_owned_job,
    enqueue_reassessment_plan,
)
from ai_intel.revalidation.service import RevalidationError

pg_engine = candidate.pg_engine
pytestmark = pytest.mark.real_pg


def prepare_two_asset_cursor(engine, directory, *, with_history=False):
    seeded = candidate.seed(engine, directory)
    candidate.publish(engine, seeded)
    imported = candidate.asset(engine, seeded)
    candidate.asset(engine, seeded)
    if with_history:
        assessor = candidate.assessor(engine, seeded)
        assessor.commit(
            assessor.prepare(
                imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1
            )
        )
    candidate.original_candidates.synthetic_change(engine, seeded)
    change = candidate.latest_change(engine, seeded)
    cutoff = datetime.now(UTC)
    discovery = CandidateDiscoveryService(
        engine, candidate.actor_reference(engine, seeded), candidate.KEY
    )
    page = discovery.discover(
        change["change_id"], change["epoch"], limit=1, assessment_created_before=cutoff
    )
    assert page.continuation
    return seeded, change, cutoff, discovery, page


@pytest.mark.parametrize("with_history", [False, True])
@pytest.mark.parametrize("visibility", ["public", "foreign_tenant"])
def test_related_source_acl_change_invalidates_frozen_cursor_without_epoch(
    pg_engine, tmp_path, with_history, visibility
):
    seeded, change, cutoff, discovery, first = prepare_two_asset_cursor(
        pg_engine, tmp_path, with_history=with_history
    )
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "UPDATE sources SET visibility=:visibility,tenant_id=:tenant "
                "WHERE source_id=:source"
            ),
            {
                "visibility": "public" if visibility == "public" else "tenant",
                "tenant": None if visibility == "public" else "fixture-other-" + uuid4().hex,
                "source": seeded["source_id"],
            },
        )
    assert candidate.latest_change(pg_engine, seeded)["epoch"] == change["epoch"]
    with pytest.raises(CandidateDiscoveryError, match="cursor_context_changed"):
        discovery.discover(
            change["change_id"],
            change["epoch"],
            limit=1,
            assessment_created_before=cutoff,
            continuation=first.continuation,
        )


def test_unrelated_source_acl_change_does_not_invalidate_relevant_frozen_cursor(
    pg_engine, tmp_path
):
    seeded, change, cutoff, discovery, first = prepare_two_asset_cursor(pg_engine, tmp_path)
    unrelated = str(uuid4())
    with pg_engine.begin() as connection:
        connection.execute(
            text(
                "INSERT INTO sources(source_id,name,category,base_origin,visibility,"
                "tenant_id,created_at) "
                "VALUES(:source,:name,'vendor_advisory','https://example.invalid','tenant',:tenant,:time)"
            ),
            {
                "source": unrelated,
                "name": "synthetic unrelated source",
                "tenant": seeded["tenant"],
                "time": datetime.now(UTC),
            },
        )
        connection.execute(
            text("UPDATE sources SET visibility='public',tenant_id=NULL WHERE source_id=:source"),
            {"source": unrelated},
        )
    second = discovery.discover(
        change["change_id"],
        change["epoch"],
        limit=1,
        assessment_created_before=cutoff,
        continuation=first.continuation,
    )
    assert second.candidates[0].asset_id != first.candidates[0].asset_id
    assert second.rule_scope_fingerprint == first.rule_scope_fingerprint


def test_enqueue_rechecks_rule_source_acl_fingerprint_without_epoch_change(pg_engine, tmp_path):
    seeded = candidate.seed(pg_engine, tmp_path)
    candidate.publish(pg_engine, seeded)
    candidate.asset(pg_engine, seeded)
    change = candidate.latest_change(pg_engine, seeded)
    service = candidate.service(pg_engine, seeded)
    plan = service.plan_change(change["change_id"], change["epoch"])
    with pg_engine.begin() as connection:
        connection.execute(
            text("UPDATE sources SET visibility='public',tenant_id=NULL WHERE source_id=:source"),
            {"source": seeded["source_id"]},
        )
    with (
        pytest.raises(RevalidationError, match="plan_inputs_changed"),
        Session(pg_engine) as session,
        session.begin(),
    ):
        enqueue_reassessment_plan(session, service.actor, plan, datetime.now(UTC))
    with pg_engine.connect() as connection:
        assert (
            connection.scalar(
                select(func.count())
                .select_from(job_runs)
                .where(
                    job_runs.c.tenant_id == seeded["tenant"],
                    job_runs.c.job_type == "revalidate_assessment",
                )
            )
            == 0
        )


@pytest.mark.parametrize("legacy_payload", [False, True])
def test_rule_only_page_restarts_for_new_lower_candidate_without_epoch(
    pg_engine, tmp_path, legacy_payload
):
    seeded = candidate.seed(pg_engine, tmp_path)
    candidate.publish(pg_engine, seeded)
    candidate.asset(pg_engine, seeded)
    for _ in range(64):
        rule = seeded["rule"].model_copy(update={"rule_id": str(uuid4())})
        seeded["service"].create_candidate(rule, (seeded["binding"],))
    parent = candidate.queue_change(pg_engine, seeded)
    assert candidate.execute(pg_engine, seeded, parent) == "partial"
    next_parent = candidate.row(pg_engine, parent)["result_ref"].removeprefix("pg:job:")
    with pg_engine.connect() as connection:
        payload = bytes(
            connection.scalar(
                select(job_payloads.c.payload).where(job_payloads.c.job_id == next_parent)
            )
        )
    request = RevalidationChangeRequest.model_validate_json(payload)
    assert request.continuation is None and request.rule_after_id
    assert request.frozen_rule_scope_fingerprint and request.frozen_scope_epoch_map
    old_epoch = candidate.latest_change(pg_engine, seeded)["epoch"]
    lower_rule_id = (
        "00000000-0000-4000-8000-000000000002"
        if legacy_payload
        else "00000000-0000-4000-8000-000000000001"
    )
    new_rule = seeded["rule"].model_copy(update={"rule_id": lower_rule_id})
    seeded["service"].create_candidate(new_rule, (seeded["binding"],))
    assert candidate.latest_change(pg_engine, seeded)["epoch"] == old_epoch
    if legacy_payload:
        decoded = json.loads(payload)
        decoded.pop("frozen_scope_epoch_map")
        decoded.pop("frozen_rule_scope_fingerprint")
        with Session(pg_engine) as session, session.begin():
            next_parent = _enqueue_owned_job(
                session,
                candidate.actor_reference(pg_engine, seeded),
                REVALIDATION_CHANGE_JOB_TYPE,
                json.dumps(decoded).encode(),
                datetime.now(UTC),
            )
    assert candidate.execute(pg_engine, seeded, next_parent) == "partial"
    resumed_parent = candidate.row(pg_engine, next_parent)["result_ref"].removeprefix("pg:job:")
    with pg_engine.connect() as connection:
        resumed_request = RevalidationChangeRequest.model_validate_json(
            bytes(
                connection.scalar(
                    select(job_payloads.c.payload).where(job_payloads.c.job_id == resumed_parent)
                )
            )
        )
        assert resumed_request.remaining_pages == request.remaining_pages - 1
        assert resumed_request.remaining_children == request.remaining_children - 64
        payloads = (
            connection.execute(
                select(job_payloads.c.payload)
                .join(job_runs)
                .where(
                    job_runs.c.tenant_id == seeded["tenant"],
                    job_runs.c.job_type == "revalidate_assessment",
                )
            )
            .scalars()
            .all()
        )
    requested = {
        candidate.ReassessmentRequest.model_validate_json(bytes(value)).rule_id
        for value in payloads
    }
    assert new_rule.rule_id in requested
