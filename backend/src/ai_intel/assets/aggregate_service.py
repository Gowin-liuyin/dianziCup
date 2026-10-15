"""One bounded provider call per child; the two-provider convenience entry is sequential (40s)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from threading import BoundedSemaphore, Lock
from typing import Literal, Protocol
from uuid import UUID

from ai_intel.assets.aggregate_observations import (
    AggregateErrorCode,
    AggregateObservation,
    AggregateOutcome,
    AggregateProvider,
    AggregateQueryId,
    aggregate_freshness,
    require_query_id,
    retrieval_time,
)
from ai_intel.assets.aggregate_repository import (
    AggregatePersistenceError,
    AggregateServerPolicy,
    StoredAggregate,
    aggregate_call_key,
    aggregate_scope_key,
    canonical_observation,
)
from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    WRITE_ASSET,
    AccessScope,
    PermissionDeniedError,
)
from ai_intel.domain.enrichment_values import ExposureAggregateValue

ServiceErrorCode = (
    AggregateErrorCode | Literal["persistence_failed", "adapter_failed", "adapter_contract_invalid"]
)
CacheStatus = Literal[
    "not_configured", "bypassed_fixture", "miss", "verified", "written", "invalid", "failed"
]
ServiceReason = Literal[
    "missing_product_query",
    "collection_not_authorized",
    "collection_in_progress",
    "no_observation",
    "stale",
    "future_retrieval",
    "provider_result",
    "persistence_failed",
    "adapter_failed",
    "adapter_contract_invalid",
]


class AggregateConnector(Protocol):
    """Production implementations use the existing allowlisted gateway deadline of 20 seconds."""

    def collect(
        self, query_id: AggregateQueryId, *, retrieved_at: datetime | None = None
    ) -> AggregateObservation: ...


class AggregateRepository(Protocol):
    def save_observation(
        self,
        observation: AggregateObservation,
        scope: AccessScope,
        policy: AggregateServerPolicy,
        *,
        recorded_at: datetime,
        observation_id: UUID | None = None,
    ) -> StoredAggregate: ...

    def read_latest(
        self,
        provider: AggregateProvider,
        query_id: AggregateQueryId,
        scope: AccessScope,
        policy: AggregateServerPolicy,
        *,
        now: datetime,
        available_only: bool = False,
    ) -> StoredAggregate | None: ...


class SafeAggregateCache(Protocol):
    """Server caches store safe persisted totals without credentials or wire bodies."""

    def get(self, identity: str) -> str | None: ...

    def set(self, identity: str, payload: str, ttl_seconds: int) -> None: ...


@dataclass(frozen=True)
class AggregateProviderResult:
    provider: AggregateProvider
    query_id: AggregateQueryId | None
    status: AggregateOutcome
    reason: ServiceReason
    value: ExposureAggregateValue | None = None
    error_code: ServiceErrorCode | None = None
    freshness: Literal["current", "stale", "unknown"] = "unknown"
    observation_id: UUID | None = None
    payload_sha256: str | None = None
    cache_identity: str | None = None
    cache_status: CacheStatus = "not_configured"
    previous_available: StoredAggregate | None = None
    actual_fee_status: Literal["unknown"] = "unknown"


def safe_cache_payload(stored: StoredAggregate) -> str:
    observation = stored.observation
    if observation.value is None or observation.data_mode != "live":
        raise ValueError("cache requires a persisted live available total")
    return json.dumps(
        {
            "schema_version": "r08-safe-cache-1",
            "observation_id": str(stored.observation_id),
            "payload_sha256": stored.payload_sha256,
            "provider": observation.provider,
            "query_id": observation.query_id,
            "query_version": observation.query_version,
            "data_mode": observation.data_mode,
            "service_count": observation.value.service_count,
            "retrieved_at": observation.retrieved_at.isoformat(),
            "observed_at": observation.value.observed_at.isoformat()
            if observation.value.observed_at
            else None,
        },
        sort_keys=True,
        separators=(",", ":"),
    )


class AggregateService:
    """A bounded in-process flight suppresses simultaneous calls without any external-call DB lock.

    Separate processes may each make one paid call. This is not an exactly-once paid-call guarantee.
    Live connectors must honor the existing gateway's 20-second deadline; no arbitrary callback is
    sandboxed or forcibly terminated here. Product convenience calls have a 40-second wire ceiling.
    """

    def __init__(
        self,
        repository: AggregateRepository,
        connectors: dict[AggregateProvider, AggregateConnector],
        server_policy: AggregateServerPolicy,
        *,
        safe_cache: SafeAggregateCache | None = None,
    ) -> None:
        if not 1 <= len(connectors) <= 2 or any(
            provider not in ("hunter", "quake") for provider in connectors
        ):
            raise ValueError("aggregate service requires one or two fixed providers")
        self.repository = repository
        self.connectors = dict(connectors)
        self.server_policy = server_policy
        self.safe_cache = safe_cache
        self._flight_guard = Lock()
        self._in_flight: set[str] = set()
        self._capacity = BoundedSemaphore(4)

    def _cache(self, stored: StoredAggregate, now: datetime, *, write: bool) -> CacheStatus:
        if self.server_policy.data_mode == "fixture":
            return "bypassed_fixture"
        if self.safe_cache is None:
            return "not_configured"
        value = stored.observation.value
        if value is None or aggregate_freshness(value, now) == "stale":
            return "not_configured"
        expected = safe_cache_payload(stored)
        try:
            if write:
                remaining = min(
                    86400 - int((now - value.retrieved_at).total_seconds()),
                    86400 - int((now - value.observed_at).total_seconds())
                    if value.observed_at
                    else 86400,
                )
                if remaining <= 0:
                    return "not_configured"
                self.safe_cache.set(stored.cache_identity, expected, remaining)
                return "written"
            cached = self.safe_cache.get(stored.cache_identity)
            if cached is None:
                return "miss"
            if type(cached) is not str or len(cached) > 4096:
                return "invalid"
            return "verified" if cached == expected else "invalid"
        except Exception:
            return "failed"

    def _result(
        self,
        stored: StoredAggregate,
        scope: AccessScope,
        now: datetime,
        *,
        write_cache: bool = False,
    ) -> AggregateProviderResult:
        observation = stored.observation
        previous = None
        value = observation.value
        reason: ServiceReason = "provider_result"
        freshness: Literal["current", "stale", "unknown"] = "unknown"
        status = observation.outcome
        cache_status: CacheStatus = (
            "bypassed_fixture" if observation.data_mode == "fixture" else "not_configured"
        )
        if observation.retrieved_at > now:
            value, status, reason = None, "unknown", "future_retrieval"
        elif value is not None:
            freshness = aggregate_freshness(value, now)
            if freshness == "stale":
                previous = stored
                value, status, reason = None, "unknown", "stale"
            else:
                cache_status = self._cache(stored, now, write=write_cache)
        else:
            previous = self.repository.read_latest(
                observation.provider,
                observation.query_id,
                scope,
                self.server_policy,
                now=now,
                available_only=True,
            )
        return AggregateProviderResult(
            observation.provider,
            observation.query_id,
            status,
            reason,
            value,
            observation.error_code,
            freshness,
            stored.observation_id,
            stored.payload_sha256,
            stored.cache_identity,
            cache_status,
            previous,
        )

    def read_current_provider_aggregate(
        self,
        provider: AggregateProvider,
        query_id: AggregateQueryId | None,
        scope: AccessScope,
        *,
        now: datetime | None = None,
    ) -> AggregateProviderResult:
        evaluated_at = retrieval_time(now)
        aggregate_scope_key(scope, self.server_policy)
        if provider not in self.connectors:
            raise ValueError("provider is not configured in this service")
        if query_id is None:
            return AggregateProviderResult(provider, None, "unknown", "missing_product_query")
        require_query_id(query_id)
        try:
            stored = self.repository.read_latest(
                provider, query_id, scope, self.server_policy, now=evaluated_at
            )
            if stored is None:
                return AggregateProviderResult(provider, query_id, "unknown", "no_observation")
            return self._result(stored, scope, evaluated_at)
        except AggregatePersistenceError:
            return AggregateProviderResult(
                provider, query_id, "failed", "persistence_failed", error_code="persistence_failed"
            )

    def collect_provider_aggregate_observation(
        self,
        provider: AggregateProvider,
        query_id: AggregateQueryId | None,
        scope: AccessScope,
        *,
        now: datetime | None = None,
    ) -> AggregateProviderResult:
        evaluated_at = retrieval_time(now)
        existing = self.read_current_provider_aggregate(provider, query_id, scope, now=evaluated_at)
        if query_id is None or (
            existing.status == "failed" and existing.error_code == "persistence_failed"
        ):
            return existing
        if not self.server_policy.collection_authorized:
            return AggregateProviderResult(
                provider, query_id, "unauthorized", "collection_not_authorized"
            )
        try:
            scope.requires(
                MANAGE_PUBLIC_SOURCES if self.server_policy.visibility == "public" else WRITE_ASSET
            )
        except PermissionDeniedError:
            return AggregateProviderResult(
                provider, query_id, "unauthorized", "collection_not_authorized"
            )
        if existing.status == "available":
            return existing
        scope_key = aggregate_scope_key(scope, self.server_policy)
        key = hashlib.sha256(
            (aggregate_call_key(provider, query_id, self.server_policy) + scope_key).encode()
        ).hexdigest()
        with self._flight_guard:
            if key in self._in_flight or not self._capacity.acquire(blocking=False):
                return AggregateProviderResult(
                    provider, query_id, "rate_limited", "collection_in_progress"
                )
            self._in_flight.add(key)
        try:
            current = self.read_current_provider_aggregate(
                provider, query_id, scope, now=evaluated_at
            )
            if (
                current.observation_id != existing.observation_id
                or current.error_code == "persistence_failed"
            ):
                return current
            try:
                connector = self.connectors[provider]
                observation = (
                    connector.collect(query_id, retrieved_at=evaluated_at)
                    if self.server_policy.data_mode == "fixture"
                    else connector.collect(query_id)
                )
                canonical_observation(observation)
                if (
                    observation.provider != provider
                    or observation.query_id != query_id
                    or observation.data_mode != self.server_policy.data_mode
                ):
                    raise ValueError("adapter identity mismatch")
            except (ValueError, TypeError, AttributeError):
                observation = AggregateObservation(
                    provider=provider,
                    query_id=query_id,
                    retrieved_at=evaluated_at if now is not None else retrieval_time(None),
                    outcome="failed",
                    error_code="invalid_response",
                    data_mode=self.server_policy.data_mode,
                )
            except Exception:
                observation = AggregateObservation(
                    provider=provider,
                    query_id=query_id,
                    retrieved_at=evaluated_at if now is not None else retrieval_time(None),
                    outcome="failed",
                    error_code="network_error",
                    data_mode=self.server_policy.data_mode,
                )
            completed_at = evaluated_at if now is not None else retrieval_time(None)
            try:
                stored = self.repository.save_observation(
                    observation, scope, self.server_policy, recorded_at=completed_at
                )
                return self._result(stored, scope, completed_at, write_cache=True)
            except AggregatePersistenceError:
                return AggregateProviderResult(
                    provider,
                    query_id,
                    "failed",
                    "persistence_failed",
                    error_code="persistence_failed",
                )
        finally:
            with self._flight_guard:
                self._in_flight.remove(key)
                self._capacity.release()

    def collect_product_aggregate_observations(
        self, query_id: AggregateQueryId | None, scope: AccessScope, *, now: datetime | None = None
    ) -> tuple[AggregateProviderResult, ...]:
        """Two sequential 20-second calls maximum; R07 may schedule two provider children."""
        return tuple(
            self.collect_provider_aggregate_observation(provider, query_id, scope, now=now)
            for provider in self.connectors
        )
