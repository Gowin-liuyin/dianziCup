"""Classify immutable source provenance without promoting deployment settings to facts."""

from ai_intel.api.knowledge_contracts import DataMode

MAX_REVISION_MODE_INPUTS = 2000
TRUSTED_SOURCE_MODE_POLICY = "trusted-source-runtime-v1"


class RevisionModeUnavailableError(ValueError):
    """A v2 response cannot represent missing, mixed or untrusted source modes."""


def classify_stored_revision_mode(metadata: object) -> DataMode:
    if not isinstance(metadata, dict):
        raise RevisionModeUnavailableError("stored_source_mode_unavailable")
    mode = metadata.get("data_mode")
    policy = metadata.get("data_mode_policy_version")
    if not isinstance(mode, str):
        raise RevisionModeUnavailableError("stored_source_mode_unavailable")
    if policy == TRUSTED_SOURCE_MODE_POLICY and mode == "live":
        return "live"
    if policy == TRUSTED_SOURCE_MODE_POLICY and mode == "fixture":
        return "fixture"
    if "data_mode_policy_version" not in metadata and mode == "fixture":
        return "fixture"
    raise RevisionModeUnavailableError("stored_source_mode_unavailable")


def homogeneous_revision_mode(
    metadata: tuple[object, ...],
    expected: DataMode,
    *,
    require_expected_mode: bool = True,
) -> DataMode:
    """Use one finite captured revision set; empty responses only describe runtime mode."""
    if (
        not isinstance(expected, str)
        or expected not in ("live", "fixture")
        or type(require_expected_mode) is not bool
    ):
        raise ValueError("invalid_source_mode_read_configuration")
    if len(metadata) > MAX_REVISION_MODE_INPUTS:
        raise RevisionModeUnavailableError("source_mode_input_limit_exceeded")
    actual: DataMode | None = None
    for item in metadata:
        candidate = classify_stored_revision_mode(item)
        if actual is not None and candidate != actual:
            raise RevisionModeUnavailableError("stored_source_modes_disagree")
        if require_expected_mode and candidate != expected:
            raise RevisionModeUnavailableError("source_mode_does_not_match_consumer")
        actual = candidate
    return actual if actual is not None else expected
