"""Workbench read DTOs may label data "live" only for trusted live provenance.

The single stored-provenance mapping behind every workbench read DTO is
``classify_stored_revision_mode``/``homogeneous_revision_mode``; these tests pin
its honesty contract: unknown, untrusted or fixture provenance is never emitted
as "live". Unknown provenance is refused fail-closed (HTTP 503 at the route
layer) rather than relabelled, which is the behaviour frozen by the 2026-10-17
r06 diagnostic oracle and the r18 public boundary tests. Emitting an explicit
"unknown" label instead would widen the published ``DataMode`` contract and is
recorded as a blocked change, not implemented here.
"""

from datetime import UTC, datetime
from unittest.mock import Mock
from uuid import UUID

import pytest
from pydantic import ValidationError

from ai_intel.api.document_contracts import DocumentListResponse
from ai_intel.api.document_read_service import DocumentReadService
from ai_intel.api.knowledge_contracts import EventListResponse
from ai_intel.api.knowledge_read_service import KnowledgeReadService
from ai_intel.domain.access import AccessScope, Role
from ai_intel.knowledge.revision_mode import (
    TRUSTED_SOURCE_MODE_POLICY,
    RevisionModeUnavailableError,
    classify_stored_revision_mode,
    homogeneous_revision_mode,
)

SCOPE = AccessScope.for_authenticated_user(str(UUID(int=9)), None, Role.VIEWER)
NOW = datetime(2026, 10, 24, tzinfo=UTC)


def trusted_metadata(mode: str) -> dict[str, str]:
    return {"data_mode": mode, "data_mode_policy_version": TRUSTED_SOURCE_MODE_POLICY}


def evidence_row(metadata: object) -> dict[str, object]:
    """A legacy-coordinate evidence SQL row whose provenance is fully controlled."""
    return {
        "evidence_id": str(UUID(int=3)),
        "revision_id": str(UUID(int=2)),
        "block_id": None,
        "block_text": None,
        "verified_at": None,
        "quote": "synthetic quote",
        "coordinate_version": "legacy",
        "start_offset": 0,
        "end_offset": 15,
        "page_number": None,
        "json_pointer": None,
        "block_start": 0,
        "canonical_uri": None,
        "source_published_at": None,
        "source_modified_at": None,
        "first_observed_at": NOW,
        "ingested_at": NOW,
        "source_metadata": metadata,
    }


@pytest.mark.parametrize("metadata", ({}, {"data_mode": None}, None))
def test_missing_stored_mode_is_refused_and_never_relabelled_live(metadata):
    with pytest.raises(RevisionModeUnavailableError, match="stored_source_mode_unavailable"):
        classify_stored_revision_mode(metadata)


@pytest.mark.parametrize(
    "metadata",
    (
        {"data_mode": "live"},
        {"data_mode": "live", "data_mode_policy_version": "forged-policy-v9"},
        {"data_mode": "bogus"},
        {"data_mode": "unknown"},
        {"data_mode": "LIVE", "data_mode_policy_version": TRUSTED_SOURCE_MODE_POLICY},
        {"data_mode": 2, "data_mode_policy_version": TRUSTED_SOURCE_MODE_POLICY},
    ),
)
def test_untrusted_or_unrepresentable_stored_mode_is_refused(metadata):
    with pytest.raises(RevisionModeUnavailableError, match="stored_source_mode_unavailable"):
        classify_stored_revision_mode(metadata)


def test_trusted_live_metadata_is_confirmed_live():
    assert classify_stored_revision_mode(trusted_metadata("live")) == "live"


@pytest.mark.parametrize(
    "metadata",
    (
        trusted_metadata("fixture"),
        {"data_mode": "fixture"},
    ),
)
def test_fixture_metadata_is_emitted_as_fixture(metadata):
    assert classify_stored_revision_mode(metadata) == "fixture"


def test_mixed_stored_modes_are_refused_instead_of_picking_one():
    with pytest.raises(RevisionModeUnavailableError, match="stored_source_modes_disagree"):
        homogeneous_revision_mode(
            (trusted_metadata("live"), trusted_metadata("fixture")),
            "live",
            require_expected_mode=False,
        )


def test_live_consumer_refuses_fixture_revisions_by_default():
    with pytest.raises(RevisionModeUnavailableError, match="source_mode_does_not_match_consumer"):
        homogeneous_revision_mode((trusted_metadata("fixture"),), "live")


def test_public_read_config_projects_fixture_revisions_as_fixture():
    assert (
        homogeneous_revision_mode(
            (trusted_metadata("fixture"),), "live", require_expected_mode=False
        )
        == "fixture"
    )


def test_truly_empty_revision_set_only_describes_runtime_mode():
    assert homogeneous_revision_mode((), "live") == "live"
    assert homogeneous_revision_mode((), "fixture") == "fixture"


@pytest.mark.parametrize(
    ("expected", "require_expected_mode"),
    (("unknown", True), ("unknown", False), ("live", "yes"), (None, True)),
)
def test_invalid_read_mode_configuration_is_rejected(expected, require_expected_mode):
    with pytest.raises(ValueError, match="invalid_source_mode_read_configuration"):
        homogeneous_revision_mode((), expected, require_expected_mode=require_expected_mode)


@pytest.mark.parametrize(
    ("metadata", "expected_mode"),
    (
        (trusted_metadata("fixture"), "fixture"),
        (trusted_metadata("live"), "live"),
    ),
)
def test_evidence_projection_emits_stored_provenance_mode(metadata, expected_mode):
    reader = KnowledgeReadService(Mock(), SCOPE, "live", require_expected_mode=False)
    projected = reader._evidence_projection(evidence_row(metadata))
    assert projected.data_mode == expected_mode


@pytest.mark.parametrize("metadata", ({}, {"data_mode": "bogus"}, {"data_mode": "live"}))
def test_evidence_projection_refuses_unknown_provenance_instead_of_live(metadata):
    reader = KnowledgeReadService(Mock(), SCOPE, "live", require_expected_mode=False)
    with pytest.raises(ValueError, match="stored_source_mode_unavailable"):
        reader._evidence_projection(evidence_row(metadata))


def test_document_read_mode_entry_follows_stored_metadata():
    reader = DocumentReadService(Mock(), SCOPE, "live", require_expected_mode=False)
    assert reader._revision_mode(({"source_metadata": trusted_metadata("fixture")},)) == "fixture"
    with pytest.raises(RevisionModeUnavailableError, match="stored_source_mode_unavailable"):
        reader._revision_mode(({"source_metadata": {}},))


@pytest.mark.parametrize("mode", ("unknown", None, "bogus", "LIVE"))
@pytest.mark.parametrize("response_type", (EventListResponse, DocumentListResponse))
def test_published_read_contracts_carry_no_unrepresentable_mode_label(response_type, mode):
    with pytest.raises(ValidationError):
        response_type(items=(), next_cursor=None, data_mode=mode)


@pytest.mark.xfail(
    strict=True,
    reason=(
        "Emitting an explicit 'unknown' label for legacy rows requires widening the "
        "published DataMode contract (Literal['live', 'fixture']) and contradicting the "
        "frozen r06/r18 fail-closed oracles; blocked pending a change order."
    ),
)
def test_emitting_unknown_label_for_legacy_rows_requires_contract_widening():
    assert classify_stored_revision_mode({}) == "unknown"
