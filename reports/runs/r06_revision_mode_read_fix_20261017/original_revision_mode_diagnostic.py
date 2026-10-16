"""Explicit SQL-result fixtures exercise unchanged product projection functions, not live IO."""

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import UUID

import pytest

from ai_intel.api.document_read_service import DocumentFilters, DocumentReadService
from ai_intel.api.knowledge_contracts import EventSummary
from ai_intel.api.knowledge_read_service import EventFilters, KnowledgeReadService
from ai_intel.domain.access import AccessScope, Role

IDENTIFIERS = [str(UUID(int=value)) for value in range(1, 7)]
NOW = datetime(2026, 10, 17, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user(str(UUID(int=9)), None, Role.VIEWER)


def revision_row(mode):
    metadata = {} if mode is None else {"data_mode": mode, "data_mode_policy_version": "trusted-source-runtime-v1"}
    if mode == "untrusted_live":
        metadata = {"data_mode": "live"}
    return {
        "document_id": IDENTIFIERS[0], "source_id": IDENTIFIERS[1], "revision_id": IDENTIFIERS[2],
        "source_name": "Synthetic fixture source", "source_category": "academic_paper",
        "kind": "paper", "current_title": "Synthetic paper", "source_metadata": metadata,
        "is_current": True, "canonical_uri": "https://example.org/paper", "revision_number": 1,
        "source_published_at": None, "source_modified_at": None, "first_observed_at": NOW,
        "ingested_at": NOW, "created_at": NOW, "parse_status": "parsed",
    }


def result(rows):
    return SimpleNamespace(mappings=lambda: SimpleNamespace(one_or_none=lambda: rows[0] if rows else None, first=lambda: rows[0] if rows else None, __iter__=lambda: iter(rows)), first=lambda: rows[0] if rows else None)


class MappingRows:
    def __init__(self, rows):
        self.rows = rows

    def __iter__(self):
        return iter(self.rows)

    def first(self):
        return self.rows[0] if self.rows else None

    def one_or_none(self):
        return self.first()


def sql_result(rows):
    return SimpleNamespace(mappings=lambda: MappingRows(rows), first=lambda: rows[0] if rows else None, __iter__=lambda: iter(rows))


class EmptyRows:
    def __iter__(self):
        return iter(())


def projected_mode(operation, mode, monkeypatch):
    row = revision_row(mode)
    session = Mock()
    if operation == "document_detail":
        session.execute.return_value = sql_result([row])
        monkeypatch.setattr(KnowledgeReadService, "read_public_revision_evidence", lambda *_: ((), 0))
        return DocumentReadService(session, SCOPE, "live").document_detail(UUID(row["document_id"])).data_mode
    if operation == "document_list":
        session.execute.return_value = sql_result([row])
        return DocumentReadService(session, SCOPE, "live").list_documents(DocumentFilters()).data_mode
    if operation == "document_revisions":
        session.execute.return_value = sql_result([row])
        return DocumentReadService(session, SCOPE, "live").list_revisions(UUID(row["document_id"])).data_mode
    reader = KnowledgeReadService(session, SCOPE, "live")
    if operation == "evidence":
        evidence = {**row, "evidence_id": IDENTIFIERS[3], "block_id": None, "block_text": None,
                    "verified_at": None, "quote": "Explicit synthetic quote", "coordinate_version": "legacy",
                    "start_offset": 0, "end_offset": 24, "page_number": None, "json_pointer": None}
        return reader._evidence_projection(evidence).data_mode
    event = {"event_id": IDENTIFIERS[4], "event_type": "vulnerability", "title": "Synthetic event", "first_seen_at": NOW, "status": "observed"}
    summary = EventSummary(**event, external_ids=(), primary_product_ids=(), source_count=1,
                           latest_revision_id=UUID(row["revision_id"]), freshness="unknown")
    monkeypatch.setattr(reader, "_summaries", lambda *_: {event["event_id"]: summary})
    if operation == "event_list":
        session.execute.return_value = sql_result([event])
        return reader.list_events(EventFilters()).data_mode
    monkeypatch.setattr(reader, "_dimensions", lambda *_: ())
    monkeypatch.setattr(reader, "_evidence_rows", lambda **_: [])
    session.execute.side_effect = [sql_result([event]), sql_result([row]), sql_result([]), EmptyRows(), EmptyRows()]
    return reader.event_detail(UUID(event["event_id"])).data_mode


@pytest.mark.parametrize("operation", ["document_detail", "document_list", "document_revisions", "evidence", "event_list", "event_detail"])
@pytest.mark.parametrize("mode", [None, "fixture", "live", "untrusted_live"])
def test_required_revision_mode_truthfulness(operation, mode, monkeypatch):
    if mode in (None, "untrusted_live"):
        with pytest.raises(ValueError):
            projected_mode(operation, mode, monkeypatch)
    else:
        assert projected_mode(operation, mode, monkeypatch) == mode
