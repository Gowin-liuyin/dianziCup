"""Fixed parameterized Neo4j transactions; no raw-query tool or stored private text."""

from __future__ import annotations

import asyncio
import builtins
import ctypes
import hashlib
import json
import os
import signal
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Coroutine, Iterator, Mapping
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Protocol, TypeVar
from uuid import UUID

from neo4j import AsyncDriver, AsyncResult, AsyncSession, AsyncTransaction

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
    def close(self) -> None: ...


OperationResult = TypeVar("OperationResult")
AddressInfo = tuple[
    socket.AddressFamily,
    socket.SocketKind,
    int,
    str,
    tuple[str, int] | tuple[str, int, int, int],
]
MAX_DNS_BYTES = 64 * 1024
MAX_DNS_ADDRESSES = 64
DNS_CLEANUP_SECONDS = 0.5
if sys.platform == "win32":
    _DNS_CREATION_FLAGS = subprocess.CREATE_NO_WINDOW
else:
    _DNS_CREATION_FLAGS = 0
_DNS_WORKER_CODE = """
import json, socket, sys
request = json.loads(sys.stdin.buffer.readline(4097))
host = bytes.fromhex(request['host_bytes']) if 'host_bytes' in request else request['host']
try:
    addresses = socket.getaddrinfo(host, request['port'], request['family'],
                                   request['type'], request['proto'], request['flags'])
    response = {'ok': True, 'addresses': addresses}
except (OSError, TypeError, ValueError, OverflowError, UnicodeError) as error:
    error_type = 'UnicodeError' if isinstance(error, UnicodeError) else type(error).__name__
    message = error.strerror if isinstance(error, OSError) else str(error)
    response = {'ok': False, 'error_type': error_type,
                'errno': getattr(error, 'errno', None), 'message': message}
sys.stdout.buffer.write(json.dumps(response, separators=(',', ':')).encode('utf-8'))
sys.stdout.buffer.flush()
"""


def _dns_process_birth(pid: int) -> int:
    if sys.platform != "win32":
        fields = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()
        return int(fields[19])
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.GetProcessTimes.argtypes = [wintypes.HANDLE] + [ctypes.c_void_p] * 4
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x1000, False, pid)
    if not handle:
        raise OSError("neo4j_dns_process_identity_unavailable")
    try:
        values = [ctypes.c_ulonglong() for _ in range(4)]
        if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in values)):
            raise OSError("neo4j_dns_process_identity_unavailable")
        return values[0].value
    finally:
        kernel.CloseHandle(handle)


def _unique_dns_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate DNS frame key")
        result[key] = value
    return result


def _reject_dns_constant(value: str) -> None:
    raise ValueError("invalid DNS frame constant")


def _decode_address_info(payload: bytes) -> list[AddressInfo]:
    if len(payload) > MAX_DNS_BYTES:
        raise OSError("neo4j_dns_output_capacity_exceeded")
    try:
        body = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique_dns_object,
            parse_constant=_reject_dns_constant,
        )
    except (ValueError, UnicodeError, RecursionError):
        raise OSError("neo4j_dns_output_invalid") from None
    if not isinstance(body, dict) or type(body.get("ok")) is not bool:
        raise OSError("neo4j_dns_output_invalid")
    if not body["ok"]:
        if set(body) != {"ok", "error_type", "errno", "message"}:
            raise OSError("neo4j_dns_output_invalid")
        errno, message = body["errno"], body["message"]
        if (errno is not None and type(errno) is not int) or not isinstance(message, str):
            raise OSError("neo4j_dns_output_invalid")
        error_type = body["error_type"]
        if error_type == "gaierror":
            raise socket.gaierror(errno, message)
        if error_type == "OSError":
            raise OSError(errno, message)
        exceptions: dict[str, type[Exception]] = {
            "TypeError": TypeError,
            "ValueError": ValueError,
            "OverflowError": OverflowError,
            "UnicodeError": UnicodeError,
        }
        if not isinstance(error_type, str) or error_type not in exceptions:
            raise OSError("neo4j_dns_output_invalid")
        raise exceptions[error_type](message)
    if set(body) != {"ok", "addresses"} or not isinstance(body["addresses"], list):
        raise OSError("neo4j_dns_output_invalid")
    if len(body["addresses"]) > MAX_DNS_ADDRESSES:
        raise OSError("neo4j_dns_output_capacity_exceeded")
    rows: list[AddressInfo] = []
    for row in body["addresses"]:
        if not isinstance(row, list) or len(row) != 5:
            raise OSError("neo4j_dns_output_invalid")
        family, socket_type, protocol, canonical_name, address = row
        if (
            any(type(value) is not int for value in (family, socket_type, protocol))
            or family not in {socket.AF_INET, socket.AF_INET6}
            or socket_type < 0
            or protocol < 0
            or not isinstance(canonical_name, str)
            or not isinstance(address, list)
            or len(address) != (2 if family == socket.AF_INET else 4)
        ):
            raise OSError("neo4j_dns_output_invalid")
        host, port = address[:2]
        if not isinstance(host, str) or type(port) is not int or not 0 <= port <= 65535:
            raise OSError("neo4j_dns_output_invalid")
        if family == socket.AF_INET:
            endpoint: tuple[str, int] | tuple[str, int, int, int] = (host, port)
        else:
            flow, scope = address[2:]
            if any(type(value) is not int or value < 0 for value in (flow, scope)):
                raise OSError("neo4j_dns_output_invalid")
            endpoint = (host, port, flow, scope)
        try:
            rows.append(
                (
                    socket.AddressFamily(family),
                    socket.SocketKind(socket_type),
                    protocol,
                    canonical_name,
                    endpoint,
                )
            )
        except ValueError:
            raise OSError("neo4j_dns_output_invalid") from None
    return rows


async def _resolve_address_info(request: bytes) -> list[AddressInfo]:
    if sys.platform != "win32":
        capability_handle = os.pidfd_open(os.getpid())
        os.close(capability_handle)
    environment = {
        key: os.environ[key] for key in ("SystemRoot", "WINDIR", "TEMP", "TMP") if key in os.environ
    }
    environment.update(PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-I",
        "-S",
        "-X",
        "utf8",
        "-u",
        "-c",
        _DNS_WORKER_CODE,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.DEVNULL,
        env=environment,
        limit=MAX_DNS_BYTES + 1,
        creationflags=_DNS_CREATION_FLAGS,
    )
    birth: int | None = None
    process_handle: int | None = None
    try:
        if sys.platform != "win32":
            process_handle = os.pidfd_open(process.pid)
        birth = _dns_process_birth(process.pid)
        if process.stdin is None or process.stdout is None:
            raise OSError("neo4j_dns_pipe_unavailable")
        process.stdin.write(request + b"\n")
        await process.stdin.drain()
        process.stdin.close()
        output = bytearray()
        while True:
            part = await process.stdout.read(min(4096, MAX_DNS_BYTES + 1 - len(output)))
            if not part:
                break
            output.extend(part)
            if len(output) > MAX_DNS_BYTES:
                raise OSError("neo4j_dns_output_capacity_exceeded")
        if await process.wait() != 0:
            raise OSError("neo4j_dns_worker_failed")
        return _decode_address_info(bytes(output))
    finally:
        try:
            if process.returncode is None:
                identity_failed = False
                if birth is not None:
                    try:
                        identity_failed = _dns_process_birth(process.pid) != birth
                    except OSError:
                        identity_failed = True
                with suppress(ProcessLookupError):
                    if sys.platform != "win32":
                        if process_handle is None:
                            raise OSError("neo4j_dns_process_handle_unavailable")
                        signal.pidfd_send_signal(process_handle, signal.SIGKILL)
                    else:
                        process.kill()
                if identity_failed:
                    raise OSError("neo4j_dns_process_identity_changed")
        finally:
            try:
                await asyncio.wait_for(process.wait(), timeout=DNS_CLEANUP_SECONDS)
            finally:
                if process_handle is not None:
                    os.close(process_handle)


class _DNSLoopMixin:
    """Keep DNS outside the default executor so cancelling IO also bounds Runner teardown."""

    dns_timeout: float
    dns_origin: tuple[str, int] | None
    dns_lock: asyncio.Lock

    async def getaddrinfo(
        self,
        host: str | bytes | None,
        port: bytes | str | int | None,
        *,
        family: int = 0,
        type: int = 0,
        proto: int = 0,
        flags: int = 0,
    ) -> list[AddressInfo]:
        origin_host = host.decode("ascii") if isinstance(host, bytes) else host
        if (
            builtins.type(port) is not int
            or self.dns_origin is None
            or (origin_host, port) != self.dns_origin
        ):
            raise OSError("neo4j_dns_origin_denied")
        request: dict[str, object] = {
            "port": port,
            "family": family,
            "type": type,
            "proto": proto,
            "flags": flags,
        }
        if isinstance(host, bytes):
            request["host_bytes"] = host.hex()
        else:
            request["host"] = host
        encoded = json.dumps(request, separators=(",", ":")).encode()
        if len(encoded) > 4096:
            raise OSError("neo4j_dns_input_capacity_exceeded")
        async with asyncio.timeout_at(time.monotonic() + self.dns_timeout), self.dns_lock:
            return await _resolve_address_info(encoded)


if sys.platform == "win32":

    class _ProjectionEventLoop(_DNSLoopMixin, asyncio.ProactorEventLoop):
        def __init__(self, timeout_seconds: float, dns_origin: tuple[str, int] | None) -> None:
            super().__init__()
            self.dns_timeout = timeout_seconds
            self.dns_origin = dns_origin
            self.dns_lock = asyncio.Lock()
else:

    class _ProjectionEventLoop(_DNSLoopMixin, asyncio.SelectorEventLoop):
        def __init__(self, timeout_seconds: float, dns_origin: tuple[str, int] | None) -> None:
            super().__init__()
            self.dns_timeout = timeout_seconds
            self.dns_origin = dns_origin
            self.dns_lock = asyncio.Lock()


def require_synchronous_projection_context() -> None:
    """A sync worker owns the loop; embedding the bridge in an active loop is unsupported."""
    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return
    raise RuntimeError("neo4j_projection_active_event_loop")


class _AsyncSessionBridge:
    def __init__(
        self, session: AsyncSession, runner: asyncio.Runner, timeout_seconds: float
    ) -> None:
        self.session = session
        self.runner = runner
        self.deadline = time.monotonic() + timeout_seconds
        self.owner_thread = threading.get_ident()

    def run(
        self, operation: Coroutine[object, object, OperationResult], *, cleanup: bool = False
    ) -> OperationResult:
        if threading.get_ident() != self.owner_thread:
            operation.close()
            raise RuntimeError("neo4j_projection_owner_thread_changed")
        try:
            require_synchronous_projection_context()
        except RuntimeError:
            operation.close()
            raise

        async def bounded() -> OperationResult:
            deadline = self.deadline
            if cleanup:
                deadline = max(deadline, time.monotonic() + 0.1)
            elif time.monotonic() >= deadline:
                operation.close()
                self.session.cancel()
                raise TimeoutError("neo4j_projection_deadline_exceeded")
            async with asyncio.timeout_at(deadline):
                try:
                    return await operation
                except asyncio.CancelledError:
                    self.session.cancel()
                    raise

        return self.runner.run(bounded())

    def begin_transaction(self, *, timeout: float) -> Neo4jTransactionPort:
        transaction = self.run(self.session.begin_transaction(timeout=timeout))
        return _AsyncTransactionBridge(transaction, self)

    def close(self) -> None:
        self.run(self.session.close(), cleanup=True)


class _AsyncResultBridge:
    def __init__(self, result: AsyncResult, session: _AsyncSessionBridge) -> None:
        self.result = result
        self.session = session

    def single(self) -> Mapping[str, object] | None:
        return self.session.run(self.result.single())

    def data(self) -> list[dict[str, object]]:
        return self.session.run(self.result.data())

    def consume(self) -> object:
        return self.session.run(self.result.consume())


class _AsyncTransactionBridge:
    def __init__(self, transaction: AsyncTransaction, session: _AsyncSessionBridge) -> None:
        self.transaction = transaction
        self.session = session

    def run(self, query: str, parameters: dict[str, object]) -> Neo4jResultPort:
        return _AsyncResultBridge(
            self.session.run(self.transaction.run(query, parameters)), self.session
        )

    def commit(self) -> None:
        self.session.run(self.transaction.commit())

    def rollback(self) -> None:
        self.session.run(self.transaction.rollback())

    def close(self) -> None:
        self.session.run(self.transaction.close(), cleanup=True)


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
    """Keep sync ports compatible; a factory-owned AsyncDriver uses one bounded owner loop."""

    def __init__(
        self,
        driver: Neo4jDriverPort | AsyncDriver,
        *,
        database: str = "neo4j",
        timeout_seconds: float = 3.0,
        dns_origin: tuple[str, int] | None = None,
    ) -> None:
        if database != "neo4j" or not 0 < timeout_seconds <= 10:
            raise ValueError("projection connection outside bounds")
        self.driver = driver
        self.database = database
        self.timeout_seconds = timeout_seconds
        self.owner_thread = threading.get_ident()
        self.runner: asyncio.Runner | None = None
        if isinstance(driver, AsyncDriver):
            require_synchronous_projection_context()

            def loop_factory() -> asyncio.AbstractEventLoop:
                loop = _ProjectionEventLoop(timeout_seconds, dns_origin)
                asyncio.set_event_loop(loop)
                return loop

            self.runner = asyncio.Runner(loop_factory=loop_factory)
        self.driver_closed = False

    def close_driver(self) -> None:
        """Factory-owned async cleanup stays on the same loop and never races live session work."""
        if threading.get_ident() != self.owner_thread:
            raise RuntimeError("neo4j_projection_owner_thread_changed")
        if self.driver_closed:
            return
        if not isinstance(self.driver, AsyncDriver):
            self.driver.close()
            self.driver_closed = True
            return
        require_synchronous_projection_context()
        if self.runner is None:
            raise RuntimeError("neo4j_projection_runner_unavailable")
        async_driver = self.driver

        async def close() -> None:
            async with asyncio.timeout(self.timeout_seconds):
                await async_driver.close()

        try:
            self.runner.run(close())
        finally:
            self.driver_closed = True
            try:
                self.runner.close()
            finally:
                asyncio.set_event_loop(None)

    @contextmanager
    def _transaction(self) -> Iterator[Neo4jTransactionPort]:
        if isinstance(self.driver, AsyncDriver):
            if threading.get_ident() != self.owner_thread:
                raise RuntimeError("neo4j_projection_owner_thread_changed")
            require_synchronous_projection_context()
            if self.runner is None or self.driver_closed:
                raise RuntimeError("neo4j_projection_runner_unavailable")
            session: Neo4jSessionPort = _AsyncSessionBridge(
                self.driver.session(database=self.database), self.runner, self.timeout_seconds
            )
        else:
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
            try:
                if transaction is not None:
                    transaction.close()
            finally:
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
