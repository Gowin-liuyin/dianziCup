"""Replay frozen sanitized samples locally; no live connector or credentials are used."""

from datetime import datetime, UTC, timedelta, timezone
import hashlib
import json
from pathlib import Path
from uuid import uuid4

from sqlalchemy import create_engine

from ai_intel.assets.aggregate_observations import AggregateObservation
from ai_intel.assets.aggregate_repository import AggregateServerPolicy, PostgresAggregateRepository
from ai_intel.assets.aggregate_service import AggregateService
from ai_intel.domain.access import AccessScope, Role
from prepare_pg import DATABASE_NAME, test_connection

class NoWireConnector:
    def collect(self, query_id, *, retrieved_at=None):
        raise AssertionError("offline replay must not collect")

run = Path(__file__).parent
root = run.parents[2]
author_run = root / "reports/runs/recovery_r08_aggregate_persistence_20261016"
source = author_run / "replayed_safe_observations.json"
raw = source.read_bytes()
observations = [AggregateObservation.model_validate_json(json.dumps(value)) for value in json.loads(raw)]
assert len(observations) == 4
engine = create_engine(test_connection().set(database=DATABASE_NAME), hide_parameters=True)
repository = PostgresAggregateRepository(engine)
scope = AccessScope.for_authenticated_user("reviewer", "review-safe-replay", Role.SYSTEM_ADMIN)
policy = AggregateServerPolicy("offline-review-" + uuid4().hex, "live", False)
service = AggregateService(repository, {"hunter": NoWireConnector(), "quake": NoWireConnector()}, policy)
now = datetime.now(UTC)
results = []
try:
    for observation in observations:
        stored = repository.save_observation(observation, scope, policy, recorded_at=now)
        current = service.read_current_provider_aggregate(observation.provider, observation.query_id, scope, now=now)
        assert current.status == "available" and current.freshness == "unknown" and current.value == observation.value
        assert current.observation_id == stored.observation_id and current.actual_fee_status == "unknown"
        results.append({"provider": observation.provider, "query_id": observation.query_id,
            "service_count": current.value.service_count, "retrieved_at": observation.retrieved_at.isoformat(),
            "observed_at": None, "freshness": current.freshness, "observation_id": str(stored.observation_id),
            "payload_sha256": stored.payload_sha256, "actual_fee": "unknown"})
finally:
    engine.dispose()
receipt = {"replayed_at": now.astimezone(timezone(timedelta(hours=8))).isoformat(),
    "source": str(source.relative_to(root)), "source_raw_sha256": hashlib.sha256(raw).hexdigest(),
    "author_provenance": json.loads((author_run / "safe_samples_replay.json").read_text(encoding="utf-8")),
    "samples": results, "provider_wire_requests": 0, "model_requests": 0, "account_requests": 0,
    "live_validation": "not_run", "scope": "historical sanitized offline replay into review-only PostgreSQL"}
(run / "safe_samples_replay.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
print("4 frozen safe samples replayed into review PostgreSQL; all freshness unknown; zero wire calls.")
