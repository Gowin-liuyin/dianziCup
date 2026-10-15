"""Boundary rejection is fail closed before any database or external client access."""

from datetime import UTC, datetime
from unittest.mock import Mock

import pytest
from pydantic import ValidationError

from ai_intel.domain.access import PermissionDeniedError
from ai_intel.enrichment.job_service import EnrichmentWorkflowError, _authenticated_scope
from ai_intel.enrichment.job_types import EnrichmentStepView


@pytest.mark.parametrize("session_hash", ["raw-token", "a" * 63, "A" * 64, "a" * 64 + "' OR TRUE"])
def test_untrusted_session_identity_is_rejected_before_query(session_hash):
    session = Mock()
    with pytest.raises(PermissionDeniedError):
        _authenticated_scope(session, session_hash, datetime.now(UTC))
    session.execute.assert_not_called()


def test_failure_response_cannot_embed_arbitrary_exception_or_credential():
    with pytest.raises(ValueError):
        EnrichmentWorkflowError("credential=synthetic-secret")
    with pytest.raises(ValidationError):
        EnrichmentStepView.model_validate({"status": "invented_success", "raw_prompt": "forbidden"})
