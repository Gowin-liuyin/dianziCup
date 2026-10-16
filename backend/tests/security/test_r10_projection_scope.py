"""Synthetic driver boundary probes; real graph filtering is tested separately."""

from uuid import UUID, uuid4

import pytest

from ai_intel.domain.access import AccessScope, PermissionDeniedError, Role
from ai_intel.infrastructure.neo4j_projection import Neo4jProjectionStore
from ai_intel.knowledge.graph_projection import partition_for_scope


class FailingSession:
    def __init__(self):
        self.closed = False

    def begin_transaction(self, **_kwargs):
        raise ConnectionError("synthetic connection acquisition failure")

    def close(self):
        self.closed = True


class FixtureDriver:
    def __init__(self):
        self.acquired = FailingSession()
        self.calls = 0

    def session(self, **_kwargs):
        self.calls += 1
        return self.acquired


def test_failed_transaction_acquisition_closes_session_and_propagates():
    driver = FixtureDriver()
    with pytest.raises(ConnectionError):
        Neo4jProjectionStore(driver).initialize_schema()
    assert driver.acquired.closed


@pytest.mark.parametrize(
    "max_hops,seeds,relations",
    [
        (True, (UUID(int=1),), ("same_event",)),
        (3, (UUID(int=1),), ("same_event",)),
        (1, ("MATCH(n)",), ("same_event",)),
        (1, (), ("same_event",)),
        (1, (UUID(int=1),), ("invented",)),
    ],
)
def test_arbitrary_request_is_rejected_before_driver(max_hops, seeds, relations):
    driver = FixtureDriver()
    scope = AccessScope.for_authenticated_user("fixture", "owner", Role.VIEWER)
    with pytest.raises(ValueError):
        Neo4jProjectionStore(driver).find_candidates(
            scope, "r10-test", uuid4(), seeds, relations, max_hops
        )
    assert driver.calls == 0


def test_viewer_and_no_permission_scope_do_not_acquire_private_graph():
    viewer = AccessScope.for_authenticated_user("viewer", "owner", Role.VIEWER)
    analyst = AccessScope.for_authenticated_user("analyst", "owner", Role.ANALYST)
    assert partition_for_scope(viewer) == "public"
    assert partition_for_scope(analyst) == "tenant:owner"
    with pytest.raises(PermissionDeniedError):
        partition_for_scope(AccessScope("invalid", "owner", Role.ANALYST))
