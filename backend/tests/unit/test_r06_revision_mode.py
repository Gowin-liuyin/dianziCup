"""Stored source provenance is independent of deployment and strict at live boundaries."""

import pytest

from ai_intel.knowledge.revision_mode import (
    MAX_REVISION_MODE_INPUTS,
    RevisionModeUnavailableError,
    classify_stored_revision_mode,
    homogeneous_revision_mode,
)


@pytest.mark.parametrize("mode", ("live", "fixture"))
def test_trusted_source_mode_is_returned_without_mutating_metadata(mode):
    metadata = {
        "data_mode": mode,
        "data_mode_policy_version": "trusted-source-runtime-v1",
        "title": "Original",
    }
    original = metadata.copy()
    assert classify_stored_revision_mode(metadata) == mode
    assert metadata == original


def test_legacy_explicit_fixture_can_only_remain_fixture():
    assert classify_stored_revision_mode({"data_mode": "fixture"}) == "fixture"


@pytest.mark.parametrize(
    "metadata",
    [
        None,
        {},
        [],
        "live",
        {"data_mode": None},
        {"data_mode": True},
        {"data_mode": "live"},
        {"data_mode": "unknown"},
        {"data_mode": "LIVE", "data_mode_policy_version": "trusted-source-runtime-v1"},
        {"data_mode": "fixture", "data_mode_policy_version": None},
        {"data_mode": "live", "data_mode_policy_version": "forged"},
        {"data_mode": "fixture", "data_mode_policy_version": "forged"},
        {"data_mode": "live", "data_mode_policy_version": True},
        {"data_mode": ["live"], "data_mode_policy_version": "trusted-source-runtime-v1"},
    ],
)
def test_unknown_unmarked_or_invalid_modes_cannot_be_successful(metadata):
    with pytest.raises(RevisionModeUnavailableError):
        classify_stored_revision_mode(metadata)


@pytest.mark.parametrize("configured", ("live", "fixture"))
def test_empty_set_is_only_the_configured_runtime_mode(configured):
    assert homogeneous_revision_mode((), configured) == configured


def test_public_homogeneous_fixture_does_not_inherit_live_deployment():
    metadata = ({"data_mode": "fixture"}, {"data_mode": "fixture"})
    assert homogeneous_revision_mode(metadata, "live", require_expected_mode=False) == "fixture"
    with pytest.raises(RevisionModeUnavailableError):
        homogeneous_revision_mode(metadata, "live")


@pytest.mark.parametrize("public", (False, True))
@pytest.mark.parametrize("ordered", (False, True))
def test_mixed_inputs_are_denied_in_either_order_even_for_public_reads(public, ordered):
    metadata = (
        {"data_mode": "fixture"},
        {"data_mode": "live", "data_mode_policy_version": "trusted-source-runtime-v1"},
    )
    if ordered:
        metadata = tuple(reversed(metadata))
    with pytest.raises(RevisionModeUnavailableError):
        homogeneous_revision_mode(metadata, "live", require_expected_mode=not public)


@pytest.mark.parametrize("configured", (None, True, "unknown"))
def test_expected_mode_itself_must_be_a_declared_mode(configured):
    with pytest.raises(ValueError):
        homogeneous_revision_mode((), configured)


@pytest.mark.parametrize("flag", (None, 0, 1, "false"))
def test_display_switch_cannot_coerce_other_types(flag):
    with pytest.raises(ValueError):
        homogeneous_revision_mode((), "live", require_expected_mode=flag)


def test_revision_count_is_bounded_before_any_metadata_classification():
    metadata = ({},) * (MAX_REVISION_MODE_INPUTS + 1)
    with pytest.raises(RevisionModeUnavailableError, match="source_mode_input_limit_exceeded"):
        homogeneous_revision_mode(metadata, "live")
