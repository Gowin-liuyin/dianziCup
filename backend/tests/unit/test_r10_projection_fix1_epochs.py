"""Explicit synthetic epoch boundary probes; no database or external service IO."""

import pytest
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService
from ai_intel.knowledge.graph_projection import ProjectionNotReady, _epochs


@pytest.mark.parametrize("epochs", [(), (("public", 0),), (("public", True),), (("public", -1),)])
def test_missing_or_invalid_authoritative_epoch_is_classified(monkeypatch, epochs):
    monkeypatch.setattr(EvidenceGraphReadService, "read_scope_epochs", lambda _self, **_kw: epochs)
    scope = AccessScope.for_authenticated_user("fixture", None, Role.VIEWER)
    with Session() as session, pytest.raises(ProjectionNotReady, match="epoch_unavailable"):
        _epochs(session, scope)


def test_unknown_epoch_io_is_not_classified_as_deterministic_state(monkeypatch):
    def unavailable(_self, **_kwargs):
        raise ConnectionError("isolated synthetic IO failure")

    monkeypatch.setattr(EvidenceGraphReadService, "read_scope_epochs", unavailable)
    scope = AccessScope.for_authenticated_user("fixture", None, Role.VIEWER)
    with Session() as session, pytest.raises(ConnectionError):
        _epochs(session, scope)
