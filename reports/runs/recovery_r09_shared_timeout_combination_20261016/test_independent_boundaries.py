"""复核者自拟fixture负例，只验证本地边界，不运行外部模型或PostgreSQL。"""

import hashlib
import pytest
from sqlalchemy import create_engine
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

from ai_intel.api.document_read_service import DocumentReadService
from ai_intel.api.document_read_service import sources
from ai_intel.domain.access import CrossTenantAccessError
from ai_intel.enrichment.card_extraction import CardExtractionFailure, extract_knowledge_card
from ai_intel.infrastructure.models.generation import GenerationLimits
from ai_intel.knowledge.models import document_revisions, documents
from r09_card_fixtures import PUBLIC_SCOPE, candidate_field, prepared_client, source_document


def test_non_bmp_unicode_saved_subspan_uses_global_offsets(monkeypatch):
    source = source_document(("🙂AAwrite. write.",))
    evidence = source.evidence[0].model_copy(update={"start_offset": 513, "end_offset": 529})
    source = source.model_copy(update={"evidence": (evidence,)})
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source, quote="write.")]})
    card = extract_knowledge_card(client, source, PUBLIC_SCOPE)
    citation = next(item for item in card.fields if item.field_name == "tool_permissions").proposed_values[0].citations[0]
    assert (citation.start_offset, citation.end_offset) == (516, 522)
    assert citation.quote_text == "write."
    assert citation.quote_sha256 == hashlib.sha256(b"write.").hexdigest()
    assert citation.source_span_sha256 == hashlib.sha256("🙂AAwrite. write.".encode()).hexdigest()
    assert len(calls) == 1


def test_semantically_false_value_stays_unverified_candidate(monkeypatch):
    source = source_document(("Read-only tools cannot write files.",))
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source, value="Read-only tools always write files.")]})
    card = extract_knowledge_card(client, source, PUBLIC_SCOPE)
    field = next(item for item in card.fields if item.field_name == "tool_permissions")
    assert field.status == "candidate"
    assert field.semantic_support == "unverified"
    assert field.proposed_values[0].origin == "model_hypothesis"
    assert card.verification_level == "unknown"
    assert card.confirmation_status == "awaiting_review"
    assert len(calls) == 1


def test_one_bad_field_rejects_whole_output_without_partial_success(monkeypatch):
    source = source_document(("Only write tools can change files.",))
    fields = [candidate_field(source), candidate_field(source, name="conclusion", quote="This text is absent.")]
    client, calls = prepared_client(monkeypatch, {"fields": fields})
    with pytest.raises(CardExtractionFailure, match="card_quote_invalid") as caught:
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert len(calls) == 1
    assert len(caught.value.attempts) == 1
    assert caught.value.attempts[0].outcome == "succeeded"


def test_total_input_budget_stops_before_external_gateway(monkeypatch):
    source = source_document(tuple(f"Span {index} " + "边界" * 1000 for index in range(50)))
    client, calls = prepared_client(monkeypatch, {"fields": []})
    with pytest.raises(CardExtractionFailure, match="model_input_budget_exhausted") as caught:
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert calls == []
    assert caught.value.attempts == ()


def test_valid_large_source_rejected_without_false_success(monkeypatch):
    source = source_document(("A" * 17000,))
    client, calls = prepared_client(monkeypatch, {"fields": []})
    with pytest.raises(CardExtractionFailure, match="card_source_invalid"):
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert calls == []


@pytest.mark.parametrize("locator,page,pointer", [("pdf_page", 4, None), ("json_pointer", None, "/clauses/2")])
def test_precise_non_text_locator_is_retained(monkeypatch, locator, page, pointer):
    source = source_document(("Published on 2026-01-02; effect is conditional.",), kind="policy")
    evidence = source.evidence[0].model_copy(update={"locator_kind": locator, "page_number": page, "json_pointer": pointer})
    source = source.model_copy(update={"evidence": (evidence,)})
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source, name="published_at", value="2026-01-02")]})
    card = extract_knowledge_card(client, source, PUBLIC_SCOPE)
    field = next(item for item in card.fields if item.field_name == "published_at")
    citation = field.proposed_values[0].citations[0]
    assert (citation.locator_kind, citation.page_number, citation.json_pointer) == (locator, page, pointer)
    assert isinstance(field.proposed_values[0].value, str)
    assert next(item for item in card.fields if item.field_name == "effective_at").status == "unknown"
    assert len(calls) == 1


@pytest.mark.parametrize("locator,page,pointer", [("pdf_page", None, None), ("json_pointer", None, None)])
def test_missing_required_locator_stops_before_gateway(monkeypatch, locator, page, pointer):
    source = source_document()
    evidence = source.evidence[0].model_copy(update={"locator_kind": locator, "page_number": page, "json_pointer": pointer})
    source = source.model_copy(update={"evidence": (evidence,)})
    client, calls = prepared_client(monkeypatch, {"fields": []})
    with pytest.raises(CardExtractionFailure, match="card_source_invalid"):
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert calls == []


def test_expired_client_deadline_is_error_with_one_attempt(monkeypatch):
    source = source_document()
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source)]})
    client.limits = GenerationLimits(total_timeout_seconds=1.0)
    clock_values = iter((100.0, 103.0))
    monkeypatch.setattr("ai_intel.infrastructure.models.generation.time.monotonic", lambda: next(clock_values, 103.0))
    with pytest.raises(CardExtractionFailure) as caught:
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert caught.value.code in {"model_concurrency_timeout", "model_network_timeout"}
    assert len(calls) <= 1
    assert len(caught.value.attempts) <= 1


def test_post_dispatch_budget_expiry_keeps_fixed_error_and_attempt(monkeypatch):
    source = source_document()
    client, calls = prepared_client(monkeypatch, {"fields": [candidate_field(source)]})
    client.limits = GenerationLimits(total_timeout_seconds=1.0)
    clock_values = iter((100.0, 100.0, 103.0))
    monkeypatch.setattr("ai_intel.infrastructure.models.generation.time.monotonic", lambda: next(clock_values, 103.0))
    with pytest.raises(CardExtractionFailure, match="model_network_timeout") as caught:
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert len(calls) == 1
    assert len(caught.value.attempts) == 1
    assert caught.value.attempts[0].outcome == "model_network_timeout"


def test_loader_public_acl_contract_prevents_private_input_and_zero_call(monkeypatch):
    captured = []

    class EmptyRows:
        def mappings(self):
            return self

        def one_or_none(self):
            return None

    class InvisibleSession:
        def execute(self, query):
            captured.append(query)
            return EmptyRows()

    client, calls = prepared_client(monkeypatch, {"fields": []})
    loader = DocumentReadService(InvisibleSession(), PUBLIC_SCOPE, "fixture")
    with pytest.raises(CrossTenantAccessError):
        source = loader.document_detail(source_document().document.document_id)
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert calls == []
    sql = str(captured[0].compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}))
    for table in ("documents", "document_revisions", "sources"):
        assert f"{table}.visibility = 'public'" in sql
        assert f"{table}.tenant_id IS NULL" in sql
    assert "documents.kind != 'asset_inventory'" in sql


@pytest.mark.parametrize("private_table", ["documents", "document_revisions", "sources"])
def test_actual_sqlite_fixture_private_row_never_reaches_model(monkeypatch, private_table):
    engine = create_engine("sqlite:///:memory:")
    source = source_document()
    document_id = str(source.document.document_id)
    source_id = str(source.document.source_id)
    revision_id = str(source.document.revision_id)
    tables = (documents, document_revisions, sources)
    rows = {
        "documents": {"document_id": document_id, "source_id": source_id, "kind": "paper", "title": "Synthetic private ACL probe", "visibility": "public", "tenant_id": None},
        "document_revisions": {"revision_id": revision_id, "document_id": document_id, "is_current": 1, "visibility": "public", "tenant_id": None},
        "sources": {"source_id": source_id, "name": "Synthetic source", "category": "academic_paper", "visibility": "public", "tenant_id": None},
    }
    rows[private_table]["visibility"] = "tenant"
    rows[private_table]["tenant_id"] = PUBLIC_SCOPE.tenant_id
    with engine.begin() as connection:
        for table in tables:
            columns = ", ".join(f'"{column.name}" ' + ("INTEGER" if column.name in {"is_current", "revision_number"} else "TEXT") for column in table.columns)
            connection.exec_driver_sql(f'CREATE TABLE "{table.name}" ({columns})')
            row = rows[table.name]
            names = ", ".join(f'"{name}"' for name in row)
            parameters = ", ".join("?" for _ in row)
            connection.exec_driver_sql(f'INSERT INTO "{table.name}" ({names}) VALUES ({parameters})', tuple(row.values()))
    client, calls = prepared_client(monkeypatch, {"fields": []})
    try:
        with Session(engine) as session:
            loader = DocumentReadService(session, PUBLIC_SCOPE, "fixture")
            assert session.execute(loader._rows_query()).mappings().one()["document_id"] == document_id
            with pytest.raises(CrossTenantAccessError):
                loaded = loader.document_detail(source.document.document_id)
                extract_knowledge_card(client, loaded, PUBLIC_SCOPE)
        assert calls == []
    finally:
        engine.dispose()


@pytest.mark.parametrize("nested", ["field", "citation"])
def test_nested_model_privilege_injection_rejected(monkeypatch, nested):
    source = source_document()
    field = candidate_field(source)
    if nested == "field":
        field["semantic_support"] = "confirmed"
    else:
        field["citations"][0]["block_id"] = str(source.evidence[0].block_id)
    client, calls = prepared_client(monkeypatch, {"fields": [field]})
    with pytest.raises(CardExtractionFailure, match="model_format_invalid"):
        extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert len(calls) == 1
