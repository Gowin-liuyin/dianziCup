"""Fixed parameterized Neo4j transactions; no raw-query tool or stored private text."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from typing import Protocol
from uuid import UUID

from ai_intel.domain.access import AccessScope
from ai_intel.knowledge.evidence_graph import RELATION_TYPES, RelationType
from ai_intel.knowledge.graph_projection import (
    GraphCandidate,
    GraphCandidateSet,
    GraphProjectionBatch,
    ProjectionDigestConflict,
    ProjectionReceipt,
    encode_projection_batch,
    partition_for_scope,
    projection_apply_decision,
)


class Neo4jResultPort(Protocol):
    def single(self) -> Mapping[str, object] | None: ...
    def data(self) -> list[dict[str, object]]: ...
    def consume(self) -> object: ...


class Neo4jTransactionPort(Protocol):
    def run(self, query: str, parameters: dict[str, object]) -> Neo4jResultPort: ...
    def commit(self) -> None: ...
    def rollback(self) -> None: ...
    def close(self) -> None: ...


class Neo4jSessionPort(Protocol):
    def begin_transaction(self, *, timeout: float) -> Neo4jTransactionPort: ...
    def close(self) -> None: ...


class Neo4jDriverPort(Protocol):
    def session(self, *, database: str) -> Neo4jSessionPort: ...


SLOT_LOCK = """
MERGE (slot:ProjectionSlot {projection_key:$slot_key})
ON CREATE SET slot.sequence=0, slot.payload_sha256='', slot.active=false,
              slot.namespace=$namespace, slot.partition_key=$partition_key,
              slot.generation_id=$generation_id, slot.event_id=$event_id
SET slot.lock_counter=coalesce(slot.lock_counter,0)+1
RETURN slot.sequence AS sequence, slot.payload_sha256 AS payload_sha256
"""
WRITE_NODES = """
UNWIND $nodes AS item
MERGE (node:IntelNode {projection_key:item.projection_key})
SET node.node_id=item.node_id, node.kind=item.kind, node.visibility=item.visibility,
    node.tenant_id=item.tenant_id, node.namespace=$namespace,
    node.partition_key=$partition_key, node.generation_id=$generation_id
RETURN count(node) AS count
"""
WRITE_EDGES = """
UNWIND $edges AS item
MATCH (subject:IntelNode {projection_key:item.subject_key})
MATCH (target:IntelNode {projection_key:item.object_key})
MERGE (subject)-[edge:INTEL_RELATION {projection_key:item.projection_key}]->(target)
SET edge.edge_id=item.edge_id, edge.relation_type=item.relation_type,
    edge.visibility=item.visibility, edge.tenant_id=item.tenant_id,
    edge.source_revision_ids=item.source_revision_ids,
    edge.evidence_span_ids=item.evidence_span_ids,
    edge.supporting_claim_ids=item.supporting_claim_ids,
    edge.rule_version=$rule_version, edge.namespace=$namespace,
    edge.partition_key=$partition_key, edge.generation_id=$generation_id,
    edge.event_id=$event_id, edge.slot_key=$slot_key, edge.sequence=$sequence,
    edge.payload_sha256=$payload_sha256
RETURN count(edge) AS count
"""
COMMIT_SLOT = """
MATCH (slot:ProjectionSlot {projection_key:$slot_key})
SET slot.sequence=$sequence, slot.payload_sha256=$payload_sha256,
    slot.batch_id=$batch_id, slot.active=$active, slot.input_sha256=$input_sha256,
    slot.full_graph_sha256=$full_graph_sha256
RETURN slot.sequence AS sequence
"""
CANDIDATES = """
UNWIND $seed_keys AS seed_key
MATCH (seed:IntelNode {projection_key:seed_key})
MATCH path=(seed)-[:INTEL_RELATION*1..2]-(target:IntelNode)
WHERE length(path) <= $max_hops AND all(edge IN relationships(path) WHERE
    edge.namespace=$namespace AND edge.partition_key=$partition_key
    AND edge.generation_id=$generation_id AND edge.relation_type IN $relation_types
    AND (edge.visibility='public' OR
         (edge.visibility='tenant' AND edge.tenant_id=$tenant_id))
    AND EXISTS { MATCH (slot:ProjectionSlot {projection_key:edge.slot_key})
                 WHERE slot.sequence IS :: INTEGER NOT NULL
                   AND edge.sequence IS :: INTEGER NOT NULL
                   AND slot.sequence=edge.sequence AND slot.sequence > 0
                   AND slot.active=true
                   AND slot.namespace=$namespace AND slot.partition_key=$partition_key
                   AND slot.generation_id=$generation_id AND slot.event_id=edge.event_id
                   AND slot.payload_sha256 IS :: STRING NOT NULL
                   AND slot.payload_sha256 =~ '^[0-9a-f]{64}$'
                   AND slot.payload_sha256=edge.payload_sha256 })
UNWIND relationships(path) AS relation
RETURN DISTINCT relation.edge_id AS edge_id, relation.event_id AS event_id,
       relation.sequence AS sequence, relation.payload_sha256 AS payload_sha256,
       relation.slot_key AS slot_key
ORDER BY event_id, edge_id LIMIT 401
"""


def projection_key(*values: object) -> str:
    return hashlib.sha256(
        json.dumps(values, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def _marker_integer(value: object) -> int:
    if type(value) is not int or value < 0:
        raise ProjectionDigestConflict("graph_projection_marker_invalid")
    return value


class Neo4jProjectionStore:
    """One explicit transaction per batch, no managed retry or PG side effect in callbacks."""

    def __init__(
        self, driver: Neo4jDriverPort, *, database: str = "neo4j", timeout_seconds: float = 3.0
    ) -> None:
        if database != "neo4j" or not 0 < timeout_seconds <= 10:
            raise ValueError("projection connection outside bounds")
        self.driver = driver
        self.database = database
        self.timeout_seconds = timeout_seconds

    @contextmanager
    def _transaction(self) -> Iterator[Neo4jTransactionPort]:
        session = self.driver.session(database=self.database)
        transaction: Neo4jTransactionPort | None = None
        try:
            transaction = session.begin_transaction(timeout=self.timeout_seconds)
            yield transaction
            transaction.commit()
        except Exception:
            if transaction is not None:
                transaction.rollback()
            raise
        finally:
            if transaction is not None:
                transaction.close()
            session.close()

    def initialize_schema(self) -> None:
        """Operator-only idempotent initialization for this isolated projection schema."""
        with self._transaction() as transaction:
            for query in (
                "CREATE CONSTRAINT intel_node_key IF NOT EXISTS FOR (n:IntelNode) "
                "REQUIRE n.projection_key IS UNIQUE",
                "CREATE CONSTRAINT projection_slot_key IF NOT EXISTS FOR (n:ProjectionSlot) "
                "REQUIRE n.projection_key IS UNIQUE",
            ):
                transaction.run(query, {}).consume()

    def apply_batch(self, batch: GraphProjectionBatch, digest: str) -> ProjectionReceipt:
        if encode_projection_batch(batch)[1] != digest:
            raise ProjectionDigestConflict("graph_projection_digest_conflict")
        slot_key = projection_key(
            batch.namespace, batch.partition_key, str(batch.generation_id), str(batch.event_id)
        )
        parameters: dict[str, object] = {
            "slot_key": slot_key,
            "namespace": batch.namespace,
            "partition_key": batch.partition_key,
            "generation_id": str(batch.generation_id),
            "event_id": str(batch.event_id),
            "sequence": batch.sequence,
            "payload_sha256": digest,
            "batch_id": str(batch.batch_id),
            "active": batch.kind == "snapshot",
            "input_sha256": batch.input_sha256,
            "full_graph_sha256": batch.full_graph_sha256,
            "rule_version": batch.rule_version,
        }
        with self._transaction() as transaction:
            marker = transaction.run(SLOT_LOCK, parameters).single()
            if marker is None or not isinstance(marker.get("payload_sha256"), str):
                raise ProjectionDigestConflict("graph_projection_marker_invalid")
            current = _marker_integer(marker["sequence"])
            stored_digest = str(marker["payload_sha256"])
            outcome = projection_apply_decision(current, batch.sequence, stored_digest, digest)
            if outcome == "applied":
                nodes: list[dict[str, object]] = [
                    {
                        "projection_key": projection_key(
                            batch.namespace,
                            batch.partition_key,
                            str(batch.generation_id),
                            str(node.id),
                        ),
                        "node_id": str(node.id),
                        "kind": node.kind,
                        "visibility": node.scope.visibility,
                        "tenant_id": node.scope.tenant_id,
                    }
                    for node in batch.nodes
                ]
                edges: list[dict[str, object]] = [
                    {
                        "projection_key": projection_key(slot_key, batch.sequence, str(edge.id)),
                        "subject_key": projection_key(
                            batch.namespace,
                            batch.partition_key,
                            str(batch.generation_id),
                            str(edge.subject_id),
                        ),
                        "object_key": projection_key(
                            batch.namespace,
                            batch.partition_key,
                            str(batch.generation_id),
                            str(edge.object_id),
                        ),
                        "edge_id": str(edge.id),
                        "relation_type": edge.relation_type,
                        "visibility": edge.scope.visibility,
                        "tenant_id": edge.scope.tenant_id,
                        "source_revision_ids": [str(value) for value in edge.source_revision_ids],
                        "evidence_span_ids": [str(value) for value in edge.evidence_span_ids],
                        "supporting_claim_ids": [str(value) for value in edge.supporting_claim_ids],
                    }
                    for edge in batch.edges
                ]
                for query, key, items in (
                    (WRITE_NODES, "nodes", nodes),
                    (WRITE_EDGES, "edges", edges),
                ):
                    record = transaction.run(query, {**parameters, key: items}).single()
                    if record is None or _marker_integer(record.get("count")) != len(items):
                        raise ProjectionDigestConflict("graph_projection_write_incomplete")
                record = transaction.run(COMMIT_SLOT, parameters).single()
                if record is None or _marker_integer(record.get("sequence")) != batch.sequence:
                    raise ProjectionDigestConflict("graph_projection_marker_invalid")
            return ProjectionReceipt(
                batch_id=batch.batch_id,
                sequence=batch.sequence,
                payload_sha256=digest,
                outcome=outcome,
            )

    def find_candidates(
        self,
        scope: AccessScope,
        namespace: str,
        generation_id: UUID,
        seed_node_ids: tuple[UUID, ...],
        relation_types: tuple[RelationType, ...],
        max_hops: int,
    ) -> GraphCandidateSet:
        partition = partition_for_scope(scope)
        if (
            type(max_hops) is not int
            or max_hops not in (1, 2)
            or not 1 <= len(seed_node_ids) <= 20
            or any(type(value) is not UUID for value in seed_node_ids)
            or not relation_types
            or any(value not in RELATION_TYPES for value in relation_types)
        ):
            raise ValueError("graph candidate request outside bounds")
        parameters: dict[str, object] = {
            "seed_keys": [
                projection_key(namespace, partition, str(generation_id), str(value))
                for value in seed_node_ids
            ],
            "namespace": namespace,
            "partition_key": partition,
            "generation_id": str(generation_id),
            "tenant_id": scope.tenant_id if partition != "public" else None,
            "relation_types": list(relation_types),
            "max_hops": max_hops,
        }
        with self._transaction() as transaction:
            records = transaction.run(CANDIDATES, parameters).data()
            candidates: list[GraphCandidate] = []
            for row in records[:400]:
                candidate = GraphCandidate.model_validate_json(
                    json.dumps(
                        {
                            key: row[key]
                            for key in ("edge_id", "event_id", "sequence", "payload_sha256")
                        }
                    )
                )
                if row["slot_key"] != projection_key(
                    namespace, partition, str(generation_id), str(candidate.event_id)
                ):
                    continue
                candidates.append(candidate)
            return GraphCandidateSet(candidates=tuple(candidates), truncated=len(records) > 400)
