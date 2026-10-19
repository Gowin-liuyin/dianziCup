"""Independent observable PG negatives; fixture approvals are never human gold labels."""

from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
from threading import Event

import pytest
from sqlalchemy import event, select, text, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from test_original_pg_resourceadapt import original
from ai_intel.assessment import assessment_service as module
from ai_intel.assessment.assessment_persistence import ASSESSMENT_TABLES, assessment_results
from ai_intel.assessment.rule_persistence import RULE_TABLES, RulePersistenceError
from ai_intel.assessment.rule_service import RuleService
from ai_intel.knowledge.persistence import find_prior_publication
from ai_intel.knowledge.persistence_models import claims


def prepared_case(engine, directory, public=False):
    seeded = original.seed(engine, directory, public=public)
    original.publish(engine, seeded)
    imported = original.asset(engine, seeded)
    service = original.assessor(engine, seeded)
    prepared = service.prepare(imported.asset_id, imported.snapshot.snapshot_id, seeded["rule"].rule_id, 1)
    return seeded, imported, service, prepared


def corrupt_raw(seeded, prepared):
    source = prepared.inputs.sources[0]
    seeded["store"].object_path_for_hash(source.content_sha256).write_bytes(b"independent review: damaged CAS object")


def test_prepare_then_corrupt_raw_must_not_commit_current(pg_engine, tmp_path):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    corrupt_raw(seeded, prepared)
    before = original.count(pg_engine, assessment_results)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.commit(prepared)
    assert original.count(pg_engine, assessment_results) == before


def test_current_history_read_checks_raw_integrity(pg_engine, tmp_path):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    receipt = service.commit(prepared)
    corrupt_raw(seeded, prepared)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.read(receipt.assessment_id)


def test_observe_damaged_evidence_receipt_and_sql_cost(pg_engine, tmp_path):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    corrupt_raw(seeded, prepared)
    digest = prepared.inputs.sources[0].content_sha256
    with pytest.raises(ValueError, match="hash mismatch"):
        seeded["store"].read_verified(digest)
    before = original.count(pg_engine, assessment_results)
    statements = []

    def count_statement(connection, cursor, statement, parameters, context, executemany):
        statements.append(statement.split(None, 1)[0])

    event.listen(pg_engine, "before_cursor_execute", count_statement)
    try:
        receipt = service.commit(prepared)
    finally:
        event.remove(pg_engine, "before_cursor_execute", count_statement)
    reread = service.read(receipt.assessment_id)
    assert receipt.freshness == reread.freshness == "current"
    assert receipt.status == reread.status == "supported_applicability"
    assert original.count(pg_engine, assessment_results) == before + 1
    record = dict(fixture_data=True, human_labels=0, source_sha256=digest, raw_read_verified="hash_mismatch", assessment_id=receipt.assessment_id, commit_status=receipt.status.value, commit_freshness=receipt.freshness.value, read_status=reread.status.value, read_freshness=reread.freshness.value, result_row_delta=1, source_count=len(prepared.inputs.sources), support_binding_count=len(prepared.inputs.supports), commit_sql_count=len(statements), commit_sql_verbs=statements)
    (Path(__file__).resolve().parent / "damaged_raw_observation.json").write_text(json.dumps(record, indent=2), encoding="utf-8")


@pytest.mark.parametrize("operation", ["commit", "read"])
def test_minimal_store_recheck_seam_rejects_damage(pg_engine, tmp_path, monkeypatch, operation):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    receipt = service.commit(prepared) if operation == "read" else None
    corrupt_raw(seeded, prepared)
    before = original.count(pg_engine, assessment_results)
    real_loader = module.load_rule_inputs

    def recheck(session, scope, row, store):
        return real_loader(session, scope, row, seeded["store"] if store is None else store)

    monkeypatch.setattr(module, "load_rule_inputs", recheck)
    with pytest.raises(ValueError, match="hash mismatch"):
        service.commit(prepared) if operation == "commit" else service.read(receipt.assessment_id)
    assert original.count(pg_engine, assessment_results) == before


@pytest.mark.parametrize("status", ["withdrawn", "superseded", "unverified"])
def test_changed_claim_cannot_remain_current_or_republish(pg_engine, tmp_path, status):
    seeded, _, service, prepared = prepared_case(pg_engine, tmp_path)
    with Session(pg_engine) as session, session.begin():
        find_prior_publication(session, "tenant:" + seeded["tenant"], "review-status-" + status, "f" * 64)
        session.execute(update(claims).where(claims.c.claim_id == seeded["claim_id"]).values(claim_status=status, is_current=False))
    receipt = service.commit(prepared)
    assert receipt.freshness == "stale"
    current = seeded["service"].validate(seeded["rule"].rule_id, 1)
    assert not current.validation.eligible
    with pytest.raises(RulePersistenceError, match="pending_or_invalid"):
        RuleService(pg_engine, seeded["reviewer_token"], seeded["store"]).publish(seeded["rule"].rule_id, 1)


def test_unrelated_third_tenant_publication_lock_does_not_block(pg_engine, tmp_path):
    _, _, service, prepared = prepared_case(pg_engine, tmp_path, public=True)
    with pg_engine.connect() as connection, connection.begin():
        connection.execute(text("SELECT pg_advisory_xact_lock(hashtextextended(:key,0))"), dict(key="knowledge-publication:tenant:unrelated-review-third-tenant"))
        with ThreadPoolExecutor(max_workers=1) as pool:
            receipt = pool.submit(service.commit, prepared).result(timeout=3)
        assert receipt.freshness == "current"


def test_every_append_only_table_has_active_pg_trigger(pg_engine, tmp_path):
    _, _, service, prepared = prepared_case(pg_engine, tmp_path)
    service.commit(prepared)
    for table in (*RULE_TABLES[1:], *ASSESSMENT_TABLES):
        primary = next(iter(table.primary_key.columns))
        with pytest.raises(IntegrityError, match="append only"), pg_engine.begin() as connection:
            connection.execute(update(table).where(primary == select(primary).limit(1).scalar_subquery()).values({primary.name: primary}))


def test_foreign_family_new_version_is_hidden(pg_engine, tmp_path):
    first = original.seed(pg_engine, tmp_path / "first")
    second = original.seed(pg_engine, tmp_path / "second")
    rule = second["rule"].model_copy(update=dict(rule_id=first["rule"].rule_id, version=2))
    with pytest.raises(original.CrossTenantAccessError, match="resource not found"):
        second["service"].create_candidate(rule, (second["binding"],))


def test_legal_inventory_writer_during_commit_waits_then_history_is_stale(pg_engine, tmp_path):
    seeded, imported, service, prepared = prepared_case(pg_engine, tmp_path)
    commit_paused, writer_started, release = Event(), Event(), Event()

    def pause_after_asset(connection, cursor, statement, parameters, context, executemany):
        if statement.startswith("SELECT rule_validation_receipts.prepared_assessment"):
            commit_paused.set()
            assert release.wait(5)

    event.listen(pg_engine, "before_cursor_execute", pause_after_asset)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            pending = pool.submit(service.commit, prepared)
            assert commit_paused.wait(5)

            def write():
                writer_started.set()
                return original.asset(pg_engine, seeded, "1.4.2", asset_id=imported.asset_id)

            writer = pool.submit(write)
            assert writer_started.wait(5)
            release.set()
            receipt = pending.result(timeout=10)
            newer = writer.result(timeout=10)
        assert receipt.asset_snapshot_id != newer.snapshot.snapshot_id
        assert service.read(receipt.assessment_id).freshness == "stale"
    finally:
        release.set()
        event.remove(pg_engine, "before_cursor_execute", pause_after_asset)
