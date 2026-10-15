"""Replay the four already-authorized safe observations; no provider connector or key is used."""

from datetime import UTC, datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from sqlalchemy import create_engine

from prepare_pg import test_connection
from ai_intel.assets.aggregate_observations import AggregateObservation
from ai_intel.assets.aggregate_repository import AggregateServerPolicy, PostgresAggregateRepository
from ai_intel.assets.aggregate_service import AggregateService
from ai_intel.domain.access import AccessScope, Role

class NoWireConnector:
    def collect(self, query_id, *, retrieved_at=None):
        raise AssertionError("safe sample replay must never collect provider observations")

run_directory = Path(__file__).parent
source = Path("D:/dianzi/reports/runs/recovery_r08_aggregate_live_20261016/aggregate_receipt.json")
try:
    raw = source.read_bytes()
    source_document = json.loads(raw)
    observations = [AggregateObservation.model_validate_json(json.dumps(row["observation"]))
                    for row in source_document["observations"]]
    assert len(observations) == 4
    assert {(item.provider, item.query_id) for item in observations} == {
        ("hunter", "ollama"), ("hunter", "vllm"), ("quake", "ollama"), ("quake", "vllm")}
    assert all(item.data_mode == "live" and item.outcome == "available" for item in observations)
    engine = create_engine(test_connection(), hide_parameters=True)
    repository = PostgresAggregateRepository(engine)
    scope = AccessScope.for_authenticated_user("r08-replay-server", "r08-replay-tenant", Role.SYSTEM_ADMIN)
    policy = AggregateServerPolicy("reused-reviewed-live-20261016", "live", False)
    service = AggregateService(repository, {"hunter": NoWireConnector(), "quake": NoWireConnector()}, policy)
    now = datetime.now(UTC)
    results = []
    for observation in observations:
        stored = repository.save_observation(observation, scope, policy, recorded_at=now)
        current = service.read_current_provider_aggregate(observation.provider, observation.query_id, scope, now=now)
        assert current.status == "available" and current.freshness == "unknown"
        assert current.observation_id == stored.observation_id
        assert current.value == observation.value
        results.append({"observation_id": str(stored.observation_id), "payload_sha256": stored.payload_sha256,
            "provider": observation.provider, "query_id": observation.query_id,
            "service_count": current.value.service_count, "retrieved_at": observation.retrieved_at.isoformat(),
            "observed_at": None, "freshness": current.freshness, "actual_fee": "unknown"})
    engine.dispose()
    receipt = {"schema_version": "r08-safe-sample-replay-1", "replayed_at": now.astimezone(timezone(timedelta(hours=8))).isoformat(),
        "source_path": str(source), "source_sha256": hashlib.sha256(raw).hexdigest(),
        "source_connector_code_sha": source_document["code_sha"], "scope": "historical safe observations -> isolated PG -> read-only service; no live integration wire validation",
        "provider_wire_requests": 0, "account_requests": 0, "model_requests": 0,
        "replayed_observations": results}
    (run_directory / "safe_samples_replay.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8")
    (run_directory / "replayed_safe_observations.json").write_text(json.dumps([item.model_dump(mode="json") for item in observations], ensure_ascii=False, indent=2), encoding="utf-8")
    print("4 historical safe observations persisted and reread with unknown observation freshness; provider wire requests=0.")
except Exception:
    print("safe sample replay failed; no credentials or provider bodies emitted")
    raise SystemExit(2) from None
