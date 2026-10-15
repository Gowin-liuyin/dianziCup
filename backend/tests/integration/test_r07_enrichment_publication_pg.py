"""Real source-worker inputs become scoped dimensions through the shared PG publisher."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from uuid import uuid4

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session
from test_r06_catalog_documents_pg import catalog_engine as catalog_engine
from test_r06_source_worker_pg import handler_for, queue, run
from test_r07_enrichment_inputs_pg import ADMIN, seeded_event

from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.domain.values import Identifier
from ai_intel.enrichment.contracts import DimensionAttempt, EvidenceBoundCandidate
from ai_intel.enrichment.inputs import load_event_enrichment_inputs
from ai_intel.enrichment.persistence_models import enrichment_results
from ai_intel.enrichment.publication import EnrichmentPublicationError, publish_enrichment_attempts
from ai_intel.enrichment.signals import enrich_structured_fields
from ai_intel.infrastructure.outbox import IdempotencyConflictError
from ai_intel.knowledge.event_linking import EventIdentifier, EventRepository, EventSubmission
from ai_intel.knowledge.models import document_revisions, evidence, scope_epochs
from ai_intel.knowledge.persistence import KnowledgePublicationError
from ai_intel.knowledge.persistence_models import claims, events

pytestmark = pytest.mark.real_pg


def inputs(engine, tmp_path):
    store, event_id = seeded_event(engine, tmp_path)
    with Session(engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, event_id, "fixture-publish-1")
    attempts = enrich_structured_fields(loaded.context, loaded.documents)
    assert attempts[0].status == DimensionStatus.AVAILABLE
    return loaded, attempts


def publish(engine, loaded, attempts, request_id=None, at=None, scope=ADMIN):
    recorded_at = at or loaded.documents[0].observed_at
    with Session(engine) as session, session.begin():
        return publish_enrichment_attempts(
            session,
            scope,
            loaded,
            attempts,
            request_id=request_id or uuid4(),
            recorded_at=recorded_at,
        )


def counts(engine):
    with Session(engine) as session:
        return tuple(
            session.scalar(select(func.count()).select_from(table))
            for table in (claims, evidence, enrichment_results, scope_epochs)
        )


def test_source_claims_dimensions_and_global_citations_survive_session_and_replay(
    catalog_engine, tmp_path
):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    request_id = uuid4()
    first = publish(catalog_engine, loaded, attempts, request_id)
    before = counts(catalog_engine)
    second = publish(
        catalog_engine,
        loaded,
        attempts,
        request_id,
        loaded.documents[0].observed_at + timedelta(seconds=1),
    )
    assert [(r.result_id, r.claim_ids) for r in first] == [
        (r.result_id, r.claim_ids) for r in second
    ]
    assert all(r.reused for r in second) and counts(catalog_engine) == before
    with Session(catalog_engine) as session:
        detail = KnowledgeReadService(session, ADMIN, data_mode="fixture").event_detail(
            loaded.context.event_id
        )
        cvss = next(dimension for dimension in detail.dimensions if dimension.dimension == "cvss")
        assert cvss.status == "available" and cvss.claim_ids
        assert cvss.citations and all(
            citation.revision_id in loaded.context.revision_ids for citation in cvss.citations
        )
        for citation in cvss.citations:
            row = (
                session.execute(
                    select(evidence).where(evidence.c.evidence_id == str(citation.evidence_id))
                )
                .mappings()
                .one()
            )
            assert row["coordinate_version"] == "fulltext_unicode_v1" and row["supports_claim"]
            block = next(
                block
                for document in loaded.documents
                for block in document.blocks
                if str(block.block_id) == row["block_id"]
            )
            assert (
                block.text[
                    row["start_offset"] - block.start_offset : row["end_offset"]
                    - block.start_offset
                ]
                == row["quote"]
            )


def test_new_source_values_cannot_reuse_an_enrichment_request_identity(catalog_engine, tmp_path):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    request_id = uuid4()
    publish(catalog_engine, loaded, attempts, request_id)
    with pytest.raises(IdempotencyConflictError):
        publish(catalog_engine, loaded, attempts[:1], request_id)


def test_changed_event_version_rejects_new_results_but_replays_original_history(
    catalog_engine, tmp_path
):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    request_id = uuid4()
    old = publish(catalog_engine, loaded, attempts, request_id)
    with catalog_engine.begin() as connection:
        connection.execute(update(events).values(business_version=2))
    with pytest.raises(EnrichmentPublicationError, match="inputs_changed"):
        publish(catalog_engine, loaded, attempts)
    replay = publish(catalog_engine, loaded, attempts, request_id)
    assert [r.result_id for r in replay] == [r.result_id for r in old]
    with Session(catalog_engine) as session:
        detail = KnowledgeReadService(session, ADMIN, data_mode="fixture").event_detail(
            loaded.context.event_id
        )
        assert all(d.freshness == "stale" for d in detail.dimensions)


def test_changed_score_with_existing_exact_quotes_cannot_be_promoted(catalog_engine, tmp_path):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    candidate = attempts[0].candidates[0]
    forged = candidate.model_copy(
        update={"value": candidate.value.model_copy(update={"base_score": 1.0})}
    )
    altered = attempts[0].model_copy(update={"candidates": (forged,)})
    before = counts(catalog_engine)
    with pytest.raises(EnrichmentPublicationError, match="verified_fields"):
        publish(catalog_engine, loaded, (altered,))
    assert counts(catalog_engine) == before


def test_model_candidate_remains_unverified_and_cannot_fill_available_dimension(
    catalog_engine, tmp_path
):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    candidate = EvidenceBoundCandidate(
        dimension="versions",
        value={
            "kind": "version_assertion",
            "package_key": "fixture-package",
            "ecosystem": "unknown",
            "scheme": "unknown",
            "raw_expression": "Synthetic proposal without a confirmed range",
        },
        evidence=attempts[0].candidates[0].evidence,
        origin=ClaimOrigin.MODEL_HYPOTHESIS,
    )
    pending = DimensionAttempt(
        dimension="versions",
        status=DimensionStatus.PENDING,
        candidates=(candidate,),
        source_ids=attempts[0].source_ids,
    )
    publish(catalog_engine, loaded, (pending,))
    with Session(catalog_engine) as session:
        row = (
            session.execute(select(claims).where(claims.c.predicate == "version_assertion"))
            .mappings()
            .one()
        )
        assert row["claim_status"] == "unverified" and row["condition_value"] == "unknown"
        result = (
            session.execute(
                select(enrichment_results).where(
                    enrichment_results.c.dimension == "versions",
                    enrichment_results.c.event_id == str(loaded.context.event_id),
                    enrichment_results.c.is_current.is_(True),
                )
            )
            .mappings()
            .one()
        )
        assert result["status"] == "pending" and result["claim_ids"] == []
    with pytest.raises(KnowledgePublicationError, match="cannot promote"):
        publish(
            catalog_engine,
            loaded,
            (pending.model_copy(update={"status": DimensionStatus.AVAILABLE}),),
        )


def test_viewer_cannot_replay_a_write_receipt(catalog_engine, tmp_path):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    request_id = uuid4()
    publish(catalog_engine, loaded, attempts, request_id)
    viewer = AccessScope.for_authenticated_user("fixture-viewer", "fixture-other", Role.VIEWER)
    with pytest.raises(PermissionDeniedError):
        publish(catalog_engine, loaded, attempts, request_id, scope=viewer)


@pytest.mark.parametrize(
    "field,value",
    [
        ("blocks_complete", False),
        ("source_version", "forged-version"),
        ("content_coverage", "excerpt"),
        ("source_record_id", "forged-record"),
        ("observed_at", None),
        ("json_payload", None),
    ],
)
def test_saved_source_snapshot_metadata_cannot_be_forged(catalog_engine, tmp_path, field, value):
    loaded, _ = inputs(catalog_engine, tmp_path)
    document = loaded.documents[0].model_copy(update={field: value})
    altered = replace(loaded, documents=(document,))
    attempts = enrich_structured_fields(altered.context, altered.documents)
    before = counts(catalog_engine)
    with pytest.raises(EnrichmentPublicationError, match="snapshot_changed"):
        publish(catalog_engine, altered, attempts, at=loaded.documents[0].observed_at)
    assert counts(catalog_engine) == before


def test_event_cve_context_cannot_be_replaced_by_a_model_identifier(catalog_engine, tmp_path):
    loaded, _ = inputs(catalog_engine, tmp_path)
    altered = replace(
        loaded, context=loaded.context.model_copy(update={"external_cve_ids": ("CVE-2099-9999",)})
    )
    attempts = enrich_structured_fields(altered.context, altered.documents)
    with pytest.raises(EnrichmentPublicationError, match="identifiers_changed"):
        publish(catalog_engine, altered, attempts)


def test_failed_model_dimension_does_not_erase_supported_source_dimension(catalog_engine, tmp_path):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    failed = DimensionAttempt(
        dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout"
    )
    results = publish(catalog_engine, loaded, (attempts[0], failed))
    assert len(results) == 2 and results[0].claim_ids and not results[1].claim_ids
    with Session(catalog_engine) as session:
        detail = KnowledgeReadService(session, ADMIN, data_mode="fixture").event_detail(
            loaded.context.event_id
        )
        assert next(d for d in detail.dimensions if d.dimension == "cvss").status == "available"
        versions = next(d for d in detail.dimensions if d.dimension == "versions")
        assert versions.status == "failed" and versions.error_code == "model_timeout"


def test_concurrent_duplicate_request_has_one_set_of_facts(catalog_engine, tmp_path):
    loaded, attempts = inputs(catalog_engine, tmp_path)
    request_id = uuid4()
    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(publish, catalog_engine, loaded, attempts, request_id) for _ in range(2)
        ]
        results = [future.result(timeout=30) for future in futures]
    assert [(r.result_id, r.claim_ids) for r in results[0]] == [
        (r.result_id, r.claim_ids) for r in results[1]
    ]
    assert sorted(all(r.reused for r in result) for result in results) == [False, True]


@pytest.mark.parametrize("roster", ["missing", "duplicated"])
def test_source_snapshot_revision_roster_cannot_omit_or_repeat_sources(
    catalog_engine, tmp_path, roster
):
    loaded, _ = inputs(catalog_engine, tmp_path)
    altered = replace(loaded, documents=() if roster == "missing" else loaded.documents * 2)
    failed = DimensionAttempt(
        dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout"
    )
    before = counts(catalog_engine)
    with pytest.raises(EnrichmentPublicationError, match="roster_changed"):
        publish(catalog_engine, altered, (failed,), at=loaded.documents[0].observed_at)
    assert counts(catalog_engine) == before


def test_source_snapshot_cannot_drop_one_of_two_current_pg_revisions(catalog_engine, tmp_path):
    store, event_id = seeded_event(catalog_engine, tmp_path)
    job_id = queue(catalog_engine, "vllm_vendor")
    assert run(catalog_engine, job_id, handler_for(store, "vllm_vendor")) in {
        "succeeded",
        "partial",
    }
    with Session(catalog_engine) as session, session.begin():
        original = load_event_enrichment_inputs(session, store, ADMIN, event_id, "fixture-roster-1")
        revision_ids = tuple(
            session.scalars(
                select(document_revisions.c.revision_id).where(
                    document_revisions.c.is_current.is_(True)
                )
            )
        )
        assert len(revision_ids) == 2
        EventRepository(session, ADMIN).publish_events(
            "fixture-roster-association-" + str(uuid4()),
            original.scope,
            (
                EventSubmission(
                    event_id=Identifier(value=str(event_id)),
                    event_type="vulnerability",
                    title="Synthetic two-source snapshot association",
                    scope=original.scope,
                    external_ids=tuple(
                        EventIdentifier(id_type="cve", id_value=value)
                        for value in original.context.external_cve_ids
                    ),
                    source_revision_ids=tuple(Identifier(value=value) for value in revision_ids),
                ),
            ),
            original.documents[0].observed_at,
        )
    with Session(catalog_engine) as session:
        loaded = load_event_enrichment_inputs(session, store, ADMIN, event_id, "fixture-roster-1")
    assert len(loaded.documents) == len(loaded.context.revision_ids) == 2
    nvd_document = next(
        document
        for document in loaded.documents
        if any(block.json_pointer == "/cve/id" for block in document.blocks)
    )
    altered = replace(loaded, documents=(nvd_document,))
    failed = DimensionAttempt(
        dimension="versions", status=DimensionStatus.FAILED, error_code="model_timeout"
    )
    before = counts(catalog_engine)
    with pytest.raises(EnrichmentPublicationError, match="roster_changed"):
        publish(catalog_engine, altered, (failed,), at=nvd_document.observed_at)
    assert counts(catalog_engine) == before
