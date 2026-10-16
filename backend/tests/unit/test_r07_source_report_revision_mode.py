"""Source-report metadata belongs to both authority fences before any verified report."""

import time
from dataclasses import replace

import pytest
from tests.unit.test_r07_source_report_reader import read_case as read_case


def parents_with_mode(case, metadata):
    return tuple({**parent, "source_metadata": metadata} for parent in case.snapshot.parents)


@pytest.mark.parametrize(
    "metadata",
    ({}, {"data_mode": "live"}, {"data_mode": "fixture", "data_mode_policy_version": "forged"}),
)
def test_initial_untrusted_mode_never_reads_content_object(read_case, metadata):
    case = read_case
    case.snapshot = replace(case.snapshot, parents=parents_with_mode(case, metadata))
    with pytest.raises(ValueError, match="stored_source_mode_unavailable"):
        case.reader.read(case.request, time.monotonic() + 4)
    assert not case.store.mock_calls


def test_fixture_content_cannot_enter_live_source_report(read_case):
    case = read_case
    case.reader.data_mode = "live"
    with pytest.raises(ValueError, match="source_mode_does_not_match_consumer"):
        case.reader.read(case.request, time.monotonic() + 4)
    assert not case.store.mock_calls


def test_second_fence_changed_metadata_cannot_return_initial_verified_report(read_case):
    case = read_case
    original_hash = case.snapshot.fingerprint()
    case.current = replace(
        case.snapshot,
        parents=parents_with_mode(
            case, {"data_mode": "live", "data_mode_policy_version": "trusted-source-runtime-v1"}
        ),
    )
    with pytest.raises(ValueError, match="source_mode_does_not_match_consumer"):
        case.reader.read(case.request, time.monotonic() + 4)
    assert case.store.read_verified.called
    assert case.snapshot.fingerprint() == original_hash


def test_metadata_is_part_of_original_input_fingerprint(read_case):
    case = read_case
    changed = replace(case.snapshot, parents=parents_with_mode(case, {"data_mode": "fixture"}))
    assert changed.fingerprint() != case.snapshot.fingerprint()
