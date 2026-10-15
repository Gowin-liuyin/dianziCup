"""内部证据图的边界不访问外部来源，也不授予查询表达式能力。"""

from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService, GraphEdge


@pytest.mark.parametrize("limits", [(0, 1), (201, 1), (1, 0), (1, 401), (True, 1)])
def test_graph_rejects_unbounded_limits_before_query(limits):
    scope = AccessScope.for_authenticated_user("fixture-viewer", "fixture-tenant", Role.VIEWER)
    with Session() as session, pytest.raises(ValueError, match="bounds"):
        EvidenceGraphReadService(session, scope).event_graph(uuid4(), *limits)


def test_graph_requires_authenticated_public_read_permission():
    scope = AccessScope("fixture-denied", "fixture-tenant", Role.VIEWER)
    with Session() as session, pytest.raises(PermissionDeniedError):
        EvidenceGraphReadService(session, scope)


def test_effective_edge_cannot_claim_support_without_evidence_or_candidates():
    edge = {
        "id": uuid4(),
        "relation_type": "mapped_atlas",
        "subject_id": uuid4(),
        "object_id": uuid4(),
        "scope": {"visibility": "public"},
        "source_revision_ids": [uuid4()],
        "evidence_span_ids": [uuid4()],
        "supporting_claim_ids": [uuid4()],
        "rule_or_model_version": "r10-graph-1.2.0",
        "reason": "已核验机制",
        "status": "supported",
    }
    assert GraphEdge.model_validate(edge).status == "supported"
    for changed in ({"evidence_span_ids": []}, {"status": "confirmed"}, {"status": "unverified"}):
        with pytest.raises(ValidationError):
            GraphEdge.model_validate({**edge, **changed})
