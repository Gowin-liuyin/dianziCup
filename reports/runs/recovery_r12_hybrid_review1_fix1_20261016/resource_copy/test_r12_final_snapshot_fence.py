"""Bounded real writers verify construction locks and hidden-tenant independence."""

from __future__ import annotations

import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from threading import Event
from uuid import uuid4

import pytest
from sqlalchemy import func, select, text, update
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from test_t30_hybrid_retrieval import PUBLIC, index_fact_set
from test_t30_hybrid_retrieval import corpus as corpus
from tests.r12_hybrid_fixtures import NOW, seed_fact

import ai_intel.retrieval.hybrid as hybrid
from ai_intel.api.knowledge_read_service import sources
from ai_intel.domain.access import AccessScope, Role
from ai_intel.domain.records import ClaimRecord
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.knowledge.models import documents, scope_epochs
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import publication_receipts
from ai_intel.retrieval.hybrid_contracts import HybridQuery, RetrievalTrace

pytestmark = pytest.mark.real_pg


def publication(
    engine: Engine,
    source: dict[str, str],
    *,
    tenant: str | None = None,
    withdraw: bool = False,
    ready: Event | None = None,
    writer_pids: list[int] | None = None,
) -> int:
    scope = VisibilityScope(visibility="public" if tenant is None else "tenant", tenant_id=tenant)
    authority = AccessScope.for_authenticated_user(
        "synthetic-authority",
        tenant,
        Role.SYSTEM_ADMIN if tenant is None else Role.TENANT_ADMIN,
    )
    submission = ClaimSubmission(
        record=ClaimRecord.model_validate(
            {
                "schema_version": 2,
                "claim_id": {"value": str(uuid4())},
                "subject": source["event_id"],
                "predicate": "source_status" if withdraw else "risk_description",
                "object_value": "withdrawn"
                if withdraw
                else "prompt injection newly confirmed synthetic risk",
                "claim_status": "supported",
                "claim_origin": "source_explicit",
                "condition_value": "true",
                "freshness": "current",
                "asserted_at": NOW,
                "observed_at": NOW,
                "scope": scope.model_dump(),
            }
        ),
        source_id=Identifier(value=source["source_id"]),
        revision_id=Identifier(value=source["revision_id"]),
        json_path="synthetic description",
        evidence_links=(
            EvidenceLink(
                evidence_id=Identifier(value=source["evidence_id"]),
                support_kind="supports",
                validation_status="validated",
            ),
        ),
    )
    with Session(engine) as session, session.begin():
        session.execute(text("SET LOCAL lock_timeout = '2000ms'"))
        pid = session.scalar(select(func.pg_backend_pid()))
        assert type(pid) is int
        if writer_pids is not None:
            writer_pids.append(pid)
        if ready is not None:
            ready.set()
        receipt = KnowledgeRepository(session, authority).publish(
            "r12-fence-" + str(uuid4()),
            scope,
            (submission,),
            created_at=NOW,
        )
    with engine.connect() as connection:
        assert (
            connection.scalar(
                select(publication_receipts.c.epoch).where(
                    publication_receipts.c.receipt_id == receipt.receipt_id
                )
            )
            == receipt.epoch
        )
    return receipt.epoch


def writer_waits_for_pg_lock(engine: Engine, pid: int) -> bool:
    deadline = time.monotonic() + 1.5
    while time.monotonic() < deadline:
        with engine.connect() as connection:
            waiting = connection.scalar(
                text("SELECT wait_event_type FROM pg_stat_activity WHERE pid=:pid"), {"pid": pid}
            )
        if waiting == "Lock":
            return True
        time.sleep(0.01)
    return False


@pytest.mark.parametrize("withdraw", [False, True], ids=["new_claim", "source_withdrawal"])
def test_legal_publication_waits_until_result_is_constructed(
    corpus, monkeypatch, withdraw: bool
) -> None:
    engine, indexer, retriever = corpus
    target = seed_fact(
        engine, "prompt injection newly confirmed synthetic risk. Source status withdrawn."
    )
    index_fact_set(engine, indexer)
    ready = Event()
    writer_pids: list[int] = []
    pending = []
    with ThreadPoolExecutor(max_workers=1) as executor:

        @dataclass(frozen=True)
        class FencedTrace(RetrievalTrace):
            def __post_init__(self) -> None:
                pending.append(
                    executor.submit(
                        publication,
                        engine,
                        target,
                        withdraw=withdraw,
                        ready=ready,
                        writer_pids=writer_pids,
                    )
                )
                assert ready.wait(1.0)
                assert writer_waits_for_pg_lock(engine, writer_pids[0])
                assert not pending[0].done()

        with monkeypatch.context() as mutation:
            mutation.setattr(hybrid, "RetrievalTrace", FencedTrace)
            result = retriever.retrieve(
                PUBLIC, HybridQuery("prompt injection", include_graph=False)
            )
        committed_epoch = pending[0].result(timeout=3.0)
    assert result.hits and not result.partial and dict(result.scope_epochs) == {"public": 1}
    assert committed_epoch == 2
    after = retriever.retrieve(PUBLIC, HybridQuery("prompt injection", include_graph=False))
    assert after.partial and "index_lag" in after.reasons
    if withdraw:
        assert not after.hits


def test_acl_update_waits_for_visible_source_until_construction_finishes(
    corpus, monkeypatch
) -> None:
    engine, indexer, retriever = corpus
    target = seed_fact(engine, "prompt injection newly confirmed synthetic risk")
    index_fact_set(engine, indexer)
    ready = Event()
    writer_pids: list[int] = []
    pending = []

    def make_source_private() -> None:
        with engine.begin() as connection:
            connection.execute(text("SET LOCAL lock_timeout = '2000ms'"))
            writer_pids.append(connection.scalar(select(func.pg_backend_pid())))
            ready.set()
            connection.execute(
                update(sources)
                .where(sources.c.source_id == target["source_id"])
                .values(visibility="tenant", tenant_id="tenant-b")
            )

    with ThreadPoolExecutor(max_workers=1) as executor:

        @dataclass(frozen=True)
        class FencedTrace(RetrievalTrace):
            def __post_init__(self) -> None:
                pending.append(executor.submit(make_source_private))
                assert ready.wait(1.0)
                assert writer_waits_for_pg_lock(engine, writer_pids[0])
                assert not pending[0].done()

        with monkeypatch.context() as mutation:
            mutation.setattr(hybrid, "RetrievalTrace", FencedTrace)
            result = retriever.retrieve(
                PUBLIC, HybridQuery("prompt injection", include_graph=False)
            )
        pending[0].result(timeout=3.0)
    assert result.hits and not result.partial
    after = retriever.retrieve(PUBLIC, HybridQuery("prompt injection", include_graph=False))
    assert not after.hits and after.partial


def test_acl_change_after_final_candidate_read_is_filtered_without_manual_epoch(
    corpus, monkeypatch
) -> None:
    engine, indexer, retriever = corpus
    target = seed_fact(engine, "prompt injection newly confirmed synthetic risk")
    index_fact_set(engine, indexer)
    original = hybrid.candidates_from_rows
    calls = 0

    def hide_document(session, scope, rows):
        nonlocal calls
        result = original(session, scope, rows)
        calls += 1
        if calls == 3:
            with engine.begin() as connection:
                connection.execute(
                    update(documents)
                    .where(documents.c.document_id == target["document_id"])
                    .values(visibility="tenant", tenant_id="tenant-b")
                )
        return result

    monkeypatch.setattr(hybrid, "candidates_from_rows", hide_document)
    result = retriever.retrieve(PUBLIC, HybridQuery("prompt injection", include_graph=False))
    assert not result.hits and result.partial and "facts_changed_during_rerank" in result.reasons
    with engine.connect() as connection:
        assert connection.scalar(select(scope_epochs.c.epoch)) == 1


def test_hidden_other_tenant_publication_is_not_locked_by_public_reader(
    corpus, monkeypatch
) -> None:
    engine, indexer, retriever = corpus
    seed_fact(engine, "prompt injection newly confirmed synthetic risk")
    hidden = seed_fact(engine, "prompt injection newly confirmed synthetic risk", tenant="tenant-b")
    index_fact_set(engine, indexer)
    index_fact_set(engine, indexer, "tenant:tenant-b")
    committed = []
    with ThreadPoolExecutor(max_workers=1) as executor:

        @dataclass(frozen=True)
        class FencedTrace(RetrievalTrace):
            def __post_init__(self) -> None:
                receipt = executor.submit(publication, engine, hidden, tenant="tenant-b").result(
                    timeout=2.0
                )
                committed.append(receipt)

        monkeypatch.setattr(hybrid, "RetrievalTrace", FencedTrace)
        result = retriever.retrieve(PUBLIC, HybridQuery("prompt injection", include_graph=False))
    assert committed == [2]
    assert result.hits and not result.partial and dict(result.scope_epochs) == {"public": 1}
    assert all(hit.candidate.tenant_id is None for hit in result.hits)
