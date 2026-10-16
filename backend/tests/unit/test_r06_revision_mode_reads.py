"""Product read boundaries over explicit SQL-result fixtures and unchanged diagnostic oracles."""

import importlib.util
from pathlib import Path
from unittest.mock import Mock
from uuid import UUID

import pytest
from sqlalchemy.dialects import postgresql

from ai_intel.api.document_read_service import DocumentFilters, DocumentReadService
from ai_intel.api.knowledge_read_service import EventFilters, KnowledgeReadService
from ai_intel.api.public_extension_reads import PublicReadUnavailable, classify_revision_mode
from ai_intel.knowledge.revision_mode import (
    MAX_REVISION_MODE_INPUTS,
    homogeneous_revision_mode,
)

ORIGINAL_PATH = (
    Path(__file__).resolve().parents[3]
    / "reports/runs/r06_revision_mode_read_fix_20261017/original_revision_mode_diagnostic.py"
)
original_spec = importlib.util.spec_from_file_location("original_mode_diagnostic", ORIGINAL_PATH)
if original_spec is None or original_spec.loader is None:
    raise ValueError("frozen diagnostic fixture cannot be loaded")
original = importlib.util.module_from_spec(original_spec)
original_spec.loader.exec_module(original)


class OriginalProjectionFixtures:
    """The old isolated summary mock acquires the new private tuple return, without new truth."""

    def __init__(self, monkeypatch, mode):
        self.monkeypatch = monkeypatch
        self.mode = mode

    def setattr(self, target, name, value):
        if name == "_summaries":
            callback = value

            def with_mode(*arguments):
                actual = homogeneous_revision_mode(
                    (original.revision_row(self.mode)["source_metadata"],),
                    "live",
                    require_expected_mode=False,
                )
                return callback(*arguments), actual

            value = with_mode
        self.monkeypatch.setattr(target, name, value)


@pytest.mark.parametrize(
    "operation",
    [
        "document_detail",
        "document_list",
        "document_revisions",
        "evidence",
        "event_list",
        "event_detail",
    ],
)
@pytest.mark.parametrize("mode", [None, "fixture", "live", "untrusted_live"])
def test_original_24_oracles_on_public_mode_configuration(operation, mode, monkeypatch):
    for reader_type in (DocumentReadService, KnowledgeReadService):
        constructor = reader_type.__init__

        def public_constructor(self, *arguments, _constructor=constructor, **options):
            options["require_expected_mode"] = False
            _constructor(self, *arguments, **options)

        monkeypatch.setattr(reader_type, "__init__", public_constructor)
    original.test_required_revision_mode_truthfulness(
        operation, mode, OriginalProjectionFixtures(monkeypatch, mode)
    )


@pytest.mark.parametrize("reader_type", (DocumentReadService, KnowledgeReadService))
def test_internal_reader_default_rejects_fixture_before_success_projection(reader_type):
    row = original.revision_row("fixture")
    reader = reader_type(Mock(), original.SCOPE, "live")
    with pytest.raises(ValueError, match="source_mode_does_not_match_consumer"):
        reader._revision_mode((row,))


@pytest.mark.parametrize(
    "metadata", ({"data_mode": "live"}, {"data_mode": "live", "data_mode_policy_version": "forged"})
)
def test_public_extension_requires_trusted_live_metadata(metadata):
    with pytest.raises(PublicReadUnavailable):
        classify_revision_mode(metadata, "live")


@pytest.mark.parametrize("mode", ("live", "fixture"))
def test_public_extension_same_expected_mode_reuses_shared_classifier(mode):
    assert (
        classify_revision_mode(
            {"data_mode": mode, "data_mode_policy_version": "trusted-source-runtime-v1"}, mode
        )
        == mode
    )


def test_event_list_uses_all_associated_revision_modes_before_returning_summary():
    event = {
        "event_id": original.IDENTIFIERS[4],
        "event_type": "vulnerability",
        "title": "Synthetic event",
        "first_seen_at": original.NOW,
        "status": "observed",
    }
    rows = [
        {**original.revision_row("live"), "event_id": event["event_id"]},
        {**original.revision_row("fixture"), "event_id": event["event_id"]},
    ]
    session = Mock()
    session.execute.side_effect = [
        original.sql_result([event]),
        original.EmptyRows(),
        original.sql_result(rows),
    ]
    with pytest.raises(ValueError, match="stored_source_modes_disagree"):
        KnowledgeReadService(
            session, original.SCOPE, "live", require_expected_mode=False
        ).list_events(EventFilters())
    query = session.execute.call_args.args[0].compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    assert "source_metadata" in str(query) and "LIMIT 2001" in str(query)


def test_event_with_no_visible_revision_is_not_an_empty_page():
    event = {
        "event_id": original.IDENTIFIERS[4],
        "event_type": "vulnerability",
        "title": "Synthetic event",
        "first_seen_at": original.NOW,
        "status": "observed",
    }
    session = Mock()
    session.execute.side_effect = [
        original.sql_result([event]),
        original.EmptyRows(),
        original.sql_result([]),
    ]
    with pytest.raises(ValueError, match="event_source_mode_unavailable"):
        KnowledgeReadService(
            session, original.SCOPE, "live", require_expected_mode=False
        ).list_events(EventFilters())


@pytest.mark.parametrize("reader_type", (DocumentReadService, KnowledgeReadService))
def test_true_empty_list_only_preserves_runtime_mode(reader_type):
    session = Mock()
    session.execute.return_value = original.sql_result([])
    reader = reader_type(session, original.SCOPE, "live")
    value = (
        reader.list_documents(DocumentFilters())
        if reader_type is DocumentReadService
        else reader.list_events(EventFilters())
    )
    assert value.items == () and value.data_mode == "live"


@pytest.mark.parametrize("mode", ("fixture", "live"))
def test_direct_evidence_sql_selects_its_own_revision_metadata(mode):
    row = {
        **original.revision_row(mode),
        "evidence_id": original.IDENTIFIERS[3],
        "block_id": None,
        "block_text": None,
        "verified_at": None,
        "quote": "synthetic",
        "coordinate_version": "legacy",
        "start_offset": 0,
        "end_offset": 9,
        "page_number": None,
        "json_pointer": None,
    }
    session = Mock()
    session.execute.return_value = original.sql_result([row])
    projected = KnowledgeReadService(
        session, original.SCOPE, "live", require_expected_mode=False
    ).read_evidence(UUID(row["evidence_id"]))
    assert projected.data_mode == mode
    query = session.execute.call_args.args[0].compile(
        dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True}
    )
    assert "document_revisions.source_metadata" in str(query)
    assert str(UUID(row["evidence_id"])) in str(query)


def test_history_limit_cannot_be_used_to_return_truncated_success():
    event = {"event_id": original.IDENTIFIERS[4]}
    session = Mock()
    session.execute.side_effect = [
        original.sql_result([event]),
        original.sql_result([original.revision_row("live")] * (MAX_REVISION_MODE_INPUTS + 1)),
    ]
    with pytest.raises(ValueError, match="source_mode_input_limit_exceeded"):
        KnowledgeReadService(
            session, original.SCOPE, "live", require_expected_mode=False
        ).event_detail(UUID(event["event_id"]))


def test_public_claim_assertion_on_other_visible_fixture_revision_blocks_whole_detail(monkeypatch):
    revision = original.revision_row("live")
    other = {**original.revision_row("fixture"), "revision_id": original.IDENTIFIERS[5]}
    event = {"event_id": original.IDENTIFIERS[4]}
    claim = {"claim_id": original.IDENTIFIERS[3], "source_revision_id": revision["revision_id"]}
    session = Mock()
    session.execute.side_effect = [
        original.sql_result([event]),
        original.sql_result([revision]),
        original.sql_result([claim]),
        [(claim["claim_id"], other["revision_id"])],
        original.sql_result([other]),
    ]
    reader = KnowledgeReadService(session, original.SCOPE, "live", require_expected_mode=False)
    monkeypatch.setattr(reader, "_evidence_rows", lambda **_: [])
    with pytest.raises(ValueError, match="stored_source_modes_disagree"):
        reader.event_detail(UUID(event["event_id"]))
    assertion_query = (
        session.execute.call_args_list[3]
        .args[0]
        .compile(dialect=postgresql.dialect(), compile_kwargs={"literal_binds": True})
    )
    assert "document_revisions.tenant_id IS NULL" in str(assertion_query)
    assert "sources.tenant_id IS NULL" in str(assertion_query)
