"""Append-only safe persistence keeps identity collisions and database failures typed."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.engine import Engine, RowMapping
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.assets.aggregate_observations import (
    LIMITATIONS,
    QUERY_VERSION,
    AggregateObservation,
    AggregateProvider,
    AggregateQueryId,
    require_query_id,
    retrieval_time,
)
from ai_intel.assets.aggregate_persistence_models import aggregate_observations
from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    READ_ASSET,
    READ_PUBLIC,
    WRITE_ASSET,
    AccessScope,
)


class AggregatePersistenceError(RuntimeError):
    """Database failure has no provider content or connection details in its public message."""


class AggregateIdentityCollision(AggregatePersistenceError):
    """A replay UUID cannot change either its payload or server authorization scope."""


@dataclass(frozen=True)
class AggregateServerPolicy:
    """Server composition sets authorization and mode; HTTP request bodies cannot construct it."""

    authorization_profile: str
    data_mode: Literal["live", "fixture"]
    collection_authorized: bool = False
    visibility: Literal["public", "tenant"] = "public"

    def __post_init__(self) -> None:
        if type(self.authorization_profile) is not str or not re.fullmatch(
            r"[a-z][a-z0-9_-]{0,63}", self.authorization_profile
        ):
            raise ValueError("authorization profile must be a bounded server identifier")
        if self.data_mode not in ("live", "fixture") or self.visibility not in ("public", "tenant"):
            raise ValueError("invalid aggregate server policy")
        if type(self.collection_authorized) is not bool:
            raise ValueError("collection authorization must be boolean")


@dataclass(frozen=True)
class StoredAggregate:
    observation_id: UUID
    observation: AggregateObservation
    payload_sha256: str
    call_key: str
    scope_key: str
    recorded_at: datetime
    fee_status: Literal["unknown"] = "unknown"

    @property
    def cache_identity(self) -> str:
        return hashlib.sha256(f"{self.call_key}:{self.scope_key}".encode()).hexdigest()


def aggregate_scope_key(scope: AccessScope, policy: AggregateServerPolicy) -> str:
    if policy.visibility == "public":
        scope.requires(READ_PUBLIC)
        return "public"
    scope.requires(READ_ASSET)
    if not scope.tenant_id or len(scope.tenant_id) > 128:
        raise ValueError("tenant aggregate requires an authenticated tenant")
    return f"tenant:{scope.tenant_id}"


def aggregate_call_key(
    provider: AggregateProvider, query_id: AggregateQueryId, policy: AggregateServerPolicy
) -> str:
    require_query_id(query_id)
    if provider not in ("hunter", "quake"):
        raise ValueError("unsupported aggregate provider")
    identity = (provider, query_id, QUERY_VERSION, policy.data_mode, policy.authorization_profile)
    return hashlib.sha256(json.dumps(identity, separators=(",", ":")).encode()).hexdigest()


def canonical_observation(observation: AggregateObservation) -> tuple[str, str]:
    if type(observation) is not AggregateObservation:
        raise ValueError("aggregate persistence requires the existing observation type")
    validated = AggregateObservation.model_validate(observation.model_dump())
    if validated.value is not None:
        if (
            validated.value.ttl_seconds != 86400
            or validated.value.query_version != QUERY_VERSION
            or validated.value.limitations != LIMITATIONS
        ):
            raise ValueError("persisted aggregate requires the frozen query version and TTL")
        if (
            validated.value.observed_at is not None
            and validated.value.observed_at > validated.retrieved_at
        ):
            raise ValueError("aggregate observation cannot follow retrieval")
    canonical = json.dumps(validated.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return canonical, hashlib.sha256(canonical.encode()).hexdigest()


def stored_aggregate(row: RowMapping) -> StoredAggregate:
    canonical = json.dumps(row["canonical_json"], sort_keys=True, separators=(",", ":"))
    observation = AggregateObservation.model_validate_json(canonical)
    _, digest = canonical_observation(observation)
    if (
        digest != row["payload_sha256"]
        or any(
            row[column] != getattr(observation, column)
            for column in (
                "schema_version",
                "provider",
                "query_id",
                "query_version",
                "retrieved_at",
                "outcome",
                "error_code",
                "data_mode",
            )
        )
        or row["observed_at"] != (observation.value.observed_at if observation.value else None)
        or row["fee_status"] != "unknown"
        or not (
            (
                row["visibility"] == "public"
                and row["tenant_id"] is None
                and row["scope_key"] == "public"
            )
            or (
                row["visibility"] == "tenant"
                and row["tenant_id"] is not None
                and row["scope_key"] == f"tenant:{row['tenant_id']}"
            )
        )
    ):
        raise AggregatePersistenceError("aggregate storage integrity failed")
    return StoredAggregate(
        row["observation_id"],
        observation,
        digest,
        row["call_key"],
        row["scope_key"],
        row["recorded_at"],
    )


class PostgresAggregateRepository:
    """Each operation owns a short transaction; no transaction survives into a provider call."""

    def __init__(self, engine: Engine) -> None:
        if engine.dialect.name != "postgresql":
            raise ValueError("aggregate persistence requires PostgreSQL")
        self.engine = engine

    def save_observation(
        self,
        observation: AggregateObservation,
        scope: AccessScope,
        policy: AggregateServerPolicy,
        *,
        recorded_at: datetime,
        observation_id: UUID | None = None,
    ) -> StoredAggregate:
        canonical, digest = canonical_observation(observation)
        if observation.data_mode != policy.data_mode:
            raise ValueError("aggregate observation mode must match server policy")
        scope_key = aggregate_scope_key(scope, policy)
        scope.requires(MANAGE_PUBLIC_SOURCES if policy.visibility == "public" else WRITE_ASSET)
        record_id = observation_id or uuid4()
        if type(record_id) is not UUID:
            raise ValueError("aggregate observation identity requires UUID")
        values = {
            "observation_id": record_id,
            "schema_version": observation.schema_version,
            "canonical_json": json.loads(canonical),
            "payload_sha256": digest,
            "call_key": aggregate_call_key(observation.provider, observation.query_id, policy),
            "provider": observation.provider,
            "query_id": observation.query_id,
            "query_version": observation.query_version,
            "retrieved_at": observation.retrieved_at,
            "observed_at": observation.value.observed_at if observation.value else None,
            "recorded_at": retrieval_time(recorded_at),
            "outcome": observation.outcome,
            "error_code": observation.error_code,
            "data_mode": observation.data_mode,
            "fee_status": "unknown",
            "visibility": policy.visibility,
            "tenant_id": scope.tenant_id if policy.visibility == "tenant" else None,
            "scope_key": scope_key,
        }
        try:
            with self.engine.begin() as connection:
                connection.execute(
                    insert(aggregate_observations)
                    .values(**values)
                    .on_conflict_do_nothing(index_elements=["observation_id"])
                )
                row = (
                    connection.execute(
                        select(aggregate_observations).where(
                            aggregate_observations.c.observation_id == record_id
                        )
                    )
                    .mappings()
                    .one()
                )
                if (
                    row["payload_sha256"] != digest
                    or row["canonical_json"] != json.loads(canonical)
                    or row["call_key"] != values["call_key"]
                    or row["scope_key"] != scope_key
                ):
                    raise AggregateIdentityCollision("aggregate observation identity collision")
                stored = stored_aggregate(row)
            return stored
        except SQLAlchemyError:
            raise AggregatePersistenceError("aggregate persistence failed") from None

    def read_latest(
        self,
        provider: AggregateProvider,
        query_id: AggregateQueryId,
        scope: AccessScope,
        policy: AggregateServerPolicy,
        *,
        now: datetime,
        available_only: bool = False,
    ) -> StoredAggregate | None:
        call_key = aggregate_call_key(provider, query_id, policy)
        scope_key = aggregate_scope_key(scope, policy)
        evaluated_at = retrieval_time(now)
        statement = select(aggregate_observations).where(
            aggregate_observations.c.call_key == call_key,
            aggregate_observations.c.scope_key == scope_key,
            aggregate_observations.c.retrieved_at <= evaluated_at,
        )
        if available_only:
            statement = statement.where(aggregate_observations.c.outcome == "available")
        statement = statement.order_by(
            aggregate_observations.c.retrieved_at.desc(),
            aggregate_observations.c.recorded_at.desc(),
            (aggregate_observations.c.outcome == "available").asc(),
            aggregate_observations.c.observation_id.desc(),
        ).limit(1)
        try:
            with self.engine.connect() as connection:
                row = connection.execute(statement).mappings().first()
                if row is None:
                    return None
                stored = stored_aggregate(row)
                scope.enforce_visible(row["visibility"], row["tenant_id"])
                if (
                    aggregate_call_key(
                        stored.observation.provider, stored.observation.query_id, policy
                    )
                    != call_key
                    or stored.observation.data_mode != policy.data_mode
                ):
                    raise AggregatePersistenceError("aggregate storage identity failed")
                return stored
        except (SQLAlchemyError, ValueError):
            raise AggregatePersistenceError("aggregate persistence read failed") from None
