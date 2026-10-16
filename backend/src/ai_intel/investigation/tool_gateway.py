"""Request-local bounded gateway; durable investigation state remains the caller's PG job."""

from __future__ import annotations

import hashlib
import json
import math
import time
from collections.abc import Callable
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import RLock, get_ident
from typing import Literal, Protocol
from uuid import UUID, uuid4

from pydantic import Field, ValidationError
from sqlalchemy import event, select
from sqlalchemy.engine import Connection, ExecutionContext
from sqlalchemy.engine.interfaces import DBAPICursor
from sqlalchemy.exc import DBAPIError, SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.api.auth_state import lock_authenticated_scope
from ai_intel.api.authentication import Principal, SessionExpiredError
from ai_intel.api.knowledge_contracts import DataMode, EvidenceResponse
from ai_intel.api.knowledge_read_service import KnowledgeProjectionError, KnowledgeReadService
from ai_intel.assessment.version_ranges import VersionComparison, compare_versions
from ai_intel.domain.access import (
    READ_PUBLIC,
    AccessScope,
    CrossTenantAccessError,
    PermissionDeniedError,
    Role,
)
from ai_intel.domain.enums import ToolStatus
from ai_intel.investigation.capabilities import (
    POLICY_VERSION,
    ROLE_CAPABILITIES,
    TOOL_SPECS,
    AgentRole,
)
from ai_intel.investigation.tool_contracts import (
    CompareVersionsCall,
    ReadEvidenceArguments,
    ReadEvidenceCall,
    SearchedScope,
    ToolCall,
    ToolInput,
    ToolName,
    ToolResult,
    ToolUsage,
    UnconfiguredCall,
    parse_tool_call,
)
from ai_intel.knowledge.evidence_graph import EvidenceGraphReadService, GraphSnapshotChangedError
from ai_intel.knowledge.models import document_revisions, documents
from ai_intel.knowledge.models import evidence as evidence_table


class BudgetLimits(ToolInput):
    max_calls: int = Field(strict=True, ge=1, le=8)
    max_concurrent_calls: int = Field(strict=True, ge=1, le=4)
    max_request_bytes: int = Field(strict=True, ge=1, le=65536)
    max_total_input_bytes: int = Field(strict=True, ge=1, le=524288)
    max_result_bytes: int = Field(strict=True, ge=1024, le=1048576)
    max_total_output_bytes: int = Field(strict=True, ge=1024, le=8388608)
    deadline_monotonic: float = Field(gt=0, allow_inf_nan=False)


class GatewayStoppedError(RuntimeError):
    """No result envelope fits the remaining bytes; callers must stop this invocation."""


class ToolNotConfiguredError(RuntimeError):
    """The server did not provide a safe executor; there is no synthetic fallback."""


@dataclass(frozen=True)
class EvidenceRead:
    evidence: EvidenceResponse
    current_supported: bool


class EvidenceReader(Protocol):
    @property
    def data_mode(self) -> DataMode: ...

    def read_evidence(
        self,
        principal: Principal,
        scope: AccessScope,
        arguments: ReadEvidenceArguments,
        deadline_monotonic: float,
    ) -> EvidenceRead: ...


class PostgresEvidenceReader:
    """Uses one already connected caller-owned connection, with auth and graph validity locks.

    Connection/pool acquisition belongs to the caller's overall budget. This executor never
    acquires a connection or accepts an active transaction. It performs no business writes;
    PostgreSQL READ ONLY cannot be used because the existing fences require FOR SHARE locks.
    """

    def __init__(self, connection: Connection, session_token: str, data_mode: DataMode) -> None:
        if connection.dialect.name != "postgresql" or not session_token:
            raise ValueError("authenticated connected PostgreSQL executor required")
        if data_mode not in {"live", "fixture"}:
            raise ValueError("explicit data mode required")
        self._connection = connection
        self._session_token = session_token
        self._data_mode = data_mode
        self._owner_thread = get_ident()

    @property
    def data_mode(self) -> DataMode:
        return self._data_mode

    @staticmethod
    def _evidence_parent_ids(
        session: Session, arguments: ReadEvidenceArguments
    ) -> tuple[str, str, str, str, str | None]:
        """Only identity for existing fences; the business reader still owns ACL and projection."""
        row = session.execute(
            select(
                documents.c.source_id,
                documents.c.document_id,
                document_revisions.c.revision_id,
                evidence_table.c.evidence_id,
                evidence_table.c.block_id,
            )
            .select_from(evidence_table.join(document_revisions).join(documents))
            .where(
                evidence_table.c.evidence_id == str(arguments.evidence_id),
                evidence_table.c.revision_id == str(arguments.revision_id),
            )
        ).one_or_none()
        if row is None:
            raise GraphSnapshotChangedError("evidence parent identity missing")
        identifiers: list[str] = []
        for value in row[:4]:
            if not isinstance(value, str):
                raise GraphSnapshotChangedError("evidence parent identity invalid")
            UUID(value)
            identifiers.append(value)
        block_id: object = row[4]
        if block_id is not None:
            if not isinstance(block_id, str):
                raise GraphSnapshotChangedError("evidence block identity invalid")
            UUID(block_id)
        return identifiers[0], identifiers[1], identifiers[2], identifiers[3], block_id

    def read_evidence(
        self,
        principal: Principal,
        scope: AccessScope,
        arguments: ReadEvidenceArguments,
        deadline_monotonic: float,
    ) -> EvidenceRead:
        connection = self._connection
        if (
            get_ident() != self._owner_thread
            or connection.closed
            or connection.invalidated
            or connection.in_transaction()
        ):
            raise ToolNotConfiguredError("connected executor unavailable")

        def bound_statement(
            connection: Connection,
            cursor: DBAPICursor,
            statement: str,
            parameters: object,
            context: ExecutionContext,
            executemany: bool,
        ) -> None:
            remaining = deadline_monotonic - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("tool deadline exhausted")
            milliseconds = max(1, math.floor(remaining * 1000))
            cursor.execute(f"SET LOCAL statement_timeout = '{milliseconds}ms'")
            cursor.execute(f"SET LOCAL lock_timeout = '{milliseconds}ms'")
            if not statement.lstrip().upper().startswith("SELECT"):
                raise ToolNotConfiguredError("read executor received a non-read statement")

        event.listen(connection, "before_cursor_execute", bound_statement)
        try:
            connection.execution_options(isolation_level="READ COMMITTED")
            with connection.begin(), Session(bind=connection) as session:
                expected = AccessScope.for_authenticated_user(
                    principal.user_id, principal.tenant_id, principal.role
                )
                authenticated = lock_authenticated_scope(
                    connection, self._session_token, datetime.now(UTC)
                )
                if authenticated != expected:
                    raise PermissionDeniedError("authenticated scope changed")
                graph_reader = EvidenceGraphReadService(session, scope)
                epochs = graph_reader.read_scope_epochs()
                candidate = graph_reader.event_graph(arguments.event_id)
                inputs = graph_reader.read_inputs
                input_digest = graph_reader.input_sha256
                if inputs is None:
                    raise GraphSnapshotChangedError("graph inputs missing")
                reader = KnowledgeReadService(session, scope, self._data_mode)
                candidate_evidence = reader.read_evidence(arguments.evidence_id)
                if candidate_evidence.revision_id != arguments.revision_id:
                    raise ValueError("evidence revision mismatch")
                identities = self._evidence_parent_ids(session, arguments)
                source_id, document_id, revision_id, evidence_id, block_id = identities
                inputs = replace(
                    inputs,
                    source_ids=tuple(sorted({*inputs.source_ids, source_id})),
                    document_ids=tuple(sorted({*inputs.document_ids, document_id})),
                    revision_ids=tuple(sorted({*inputs.revision_ids, revision_id})),
                    evidence_ids=tuple(sorted({*inputs.evidence_ids, evidence_id})),
                    block_ids=tuple(sorted({*inputs.block_ids, block_id}))
                    if block_id is not None
                    else inputs.block_ids,
                )
                graph_reader.lock_graph_inputs(arguments.event_id, inputs)
                if self._evidence_parent_ids(session, arguments) != identities:
                    raise GraphSnapshotChangedError("evidence parent identity changed")
                current = graph_reader.event_graph(arguments.event_id)
                if (
                    graph_reader.input_sha256 != input_digest
                    or candidate.content_sha256 != current.content_sha256
                    or graph_reader.read_scope_epochs(lock=True) != epochs
                ):
                    raise GraphSnapshotChangedError("graph inputs changed")
                evidence = reader.read_evidence(arguments.evidence_id)
                if evidence.revision_id != arguments.revision_id:
                    raise ValueError("evidence revision mismatch")
                supported = evidence.verified_at is not None and any(
                    arguments.evidence_id in edge.evidence_span_ids
                    and arguments.revision_id in edge.source_revision_ids
                    for edge in current.edges
                )
                if (
                    lock_authenticated_scope(connection, self._session_token, datetime.now(UTC))
                    != expected
                ):
                    raise PermissionDeniedError("authenticated scope changed")
                if time.monotonic() >= deadline_monotonic:
                    raise TimeoutError("tool deadline exhausted")
                return EvidenceRead(evidence, supported)
        finally:
            event.remove(connection, "before_cursor_execute", bound_statement)


class ToolGateway:
    """Finite local dispatch and redacted traces, without claiming durable budget/replay state.

    The server supplies Principal, AgentRole and limits. Only Assessor may read tenant evidence.
    Evidence-bearing reads revalidate ACL/facts; pure comparisons can reuse results. A failed
    key without evidence is terminal and cannot be retried by another role.
    """

    def __init__(
        self,
        principal: Principal,
        investigation_id: UUID,
        limits: BudgetLimits,
        *,
        evidence_reader: EvidenceReader | None = None,
        monotonic: Callable[[], float] = time.monotonic,
    ) -> None:
        if not isinstance(principal, Principal) or not isinstance(principal.role, Role):
            raise ValueError("server authenticated principal required")
        if not isinstance(investigation_id, UUID):
            raise ValueError("investigation UUID required")
        self._principal = principal
        self._investigation_id = investigation_id
        self._limits = limits
        self._reader = evidence_reader
        self._clock = monotonic
        self._lock = RLock()
        self._calls = 0
        self._active = 0
        self._input_bytes = 0
        self._output_bytes = 0
        self._reserved_output_bytes = 0
        self._inflight: set[str] = set()
        self._outcomes: dict[str, ToolResult] = {}
        self._runs: list[ToolResult] = []
        self._stopped = False

    @property
    def runs(self) -> tuple[ToolResult, ...]:
        with self._lock:
            return tuple(self._runs)

    @property
    def configured_tools(self) -> frozenset[ToolName]:
        return frozenset(
            {ToolName.COMPARE_VERSIONS}
            | ({ToolName.READ_EVIDENCE} if self._reader is not None else set())
        )

    def _scope(self, role: AgentRole) -> AccessScope:
        return AccessScope.for_authenticated_user(
            self._principal.user_id,
            self._principal.tenant_id if role == AgentRole.ASSESSOR else None,
            self._principal.role,
        )

    def _emit(self, result: ToolResult) -> ToolResult:
        with self._lock:
            for _ in range(4):
                size = len(result.model_dump_json().encode("utf-8"))
                if result.usage.result_bytes == size:
                    break
                result = result.model_copy(
                    update={"usage": result.usage.model_copy(update={"result_bytes": size})}
                )
            if size > self._limits.max_result_bytes and result.data is not None:
                return self._emit(
                    result.model_copy(
                        update={
                            "status": ToolStatus.PARTIAL,
                            "data": None,
                            "error_code": "output_limit",
                            "limitations": (
                                "完整工具数据超过输出上限；保留引用，不能据此否定事实。",
                            ),
                            "usage": result.usage.model_copy(update={"result_bytes": 0}),
                        }
                    )
                )
            if (
                size > self._limits.max_result_bytes
                or self._output_bytes + self._reserved_output_bytes + size
                > self._limits.max_total_output_bytes
            ):
                self._stopped = True
                raise GatewayStoppedError("output_budget_exhausted")
            self._output_bytes += size
            self._runs.append(result)
            return result

    def execute(self, agent_role: AgentRole, raw_call: bytes) -> ToolResult:
        request_bytes = len(raw_call) if type(raw_call) is bytes else 0
        raw_digest = (
            hashlib.sha256(raw_call[: self._limits.max_request_bytes]).hexdigest()
            if type(raw_call) is bytes
            else "0" * 64
        )
        result = ToolResult(
            tool_run_id=uuid4(),
            call_key=raw_digest,
            tool_name=None,
            status=ToolStatus.DENIED,
            data=None,
            evidence_ids=(),
            searched_scope=SearchedScope(goal_id=None, scope_kind="none"),
            observed_at=None,
            executed_at=datetime.now(UTC),
            retryable=False,
            error_code="invalid_tool_input",
            usage=ToolUsage(
                request_bytes=request_bytes, result_bytes=0, service_calls=0, cached=False
            ),
            is_synthetic=False,
            limitations=(),
        )
        with self._lock:
            if self._stopped:
                raise GatewayStoppedError("output_budget_exhausted")
            if type(raw_call) is not bytes or not isinstance(agent_role, AgentRole):
                return self._emit(result)
            if (
                request_bytes > self._limits.max_request_bytes
                or self._input_bytes + request_bytes > self._limits.max_total_input_bytes
            ):
                return self._emit(
                    result.model_copy(
                        update={
                            "status": ToolStatus.BUDGET_EXHAUSTED,
                            "error_code": "input_budget_exhausted",
                        }
                    )
                )
            self._input_bytes += request_bytes
        try:
            call = parse_tool_call(raw_call, self._limits.max_request_bytes)
        except (ValueError, UnicodeError, RecursionError):
            return self._emit(result)
        scope = self._scope(agent_role)
        key_payload = [
            str(self._investigation_id),
            self._principal.user_id,
            self._principal.tenant_id,
            self._principal.role.value,
            scope.tenant_id if isinstance(call, ReadEvidenceCall) else None,
            scope.permission_version,
            POLICY_VERSION,
            call.model_dump(mode="json"),
        ]
        call_key = hashlib.sha256(
            json.dumps(key_payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        scope_kind: Literal["local", "tenant", "public"]
        if isinstance(call, CompareVersionsCall):
            scope_kind = "local"
        elif scope.tenant_id:
            scope_kind = "tenant"
        else:
            scope_kind = "public"
        result = result.model_copy(
            update={
                "call_key": call_key,
                "tool_name": ToolName(call.tool_name),
                "searched_scope": SearchedScope(
                    goal_id=call.goal_id,
                    scope_kind=scope_kind,
                    event_id=call.arguments.event_id
                    if isinstance(call, ReadEvidenceCall)
                    else None,
                    revision_id=call.arguments.revision_id
                    if isinstance(call, ReadEvidenceCall)
                    else None,
                ),
            }
        )
        if result.tool_name not in ROLE_CAPABILITIES[agent_role].allowed_tools:
            return self._emit(result.model_copy(update={"error_code": "role_tool_denied"}))
        try:
            scope.requires(READ_PUBLIC)
        except PermissionDeniedError:
            return self._emit(result.model_copy(update={"error_code": "permission_denied"}))
        if isinstance(call, UnconfiguredCall) or result.tool_name not in self.configured_tools:
            return self._emit(
                result.model_copy(
                    update={
                        "status": ToolStatus.NOT_CONFIGURED,
                        "error_code": "tool_not_configured",
                    }
                )
            )
        with self._lock:
            if self._clock() >= self._limits.deadline_monotonic:
                return self._emit(
                    result.model_copy(
                        update={
                            "status": ToolStatus.BUDGET_EXHAUSTED,
                            "error_code": "deadline_exhausted",
                        }
                    )
                )
            previous = self._outcomes.get(call_key)
            if previous is not None and (
                isinstance(call, CompareVersionsCall)
                or (previous.data is None and not previous.evidence_ids)
            ):
                return self._emit(
                    previous.model_copy(
                        update={
                            "tool_run_id": result.tool_run_id,
                            "executed_at": result.executed_at,
                            "usage": result.usage.model_copy(update={"cached": True}),
                        }
                    )
                )
            reason = None
            if call_key in self._inflight:
                reason = "duplicate_inflight"
            elif self._calls >= self._limits.max_calls:
                reason = "call_budget_exhausted"
            elif self._active >= self._limits.max_concurrent_calls:
                reason = "concurrency_exhausted"
            if reason:
                return self._emit(
                    result.model_copy(
                        update={
                            "status": ToolStatus.PARTIAL
                            if reason == "duplicate_inflight"
                            else ToolStatus.BUDGET_EXHAUSTED,
                            "error_code": reason,
                        }
                    )
                )
            if (
                self._limits.max_total_output_bytes
                - self._output_bytes
                - self._reserved_output_bytes
                < self._limits.max_result_bytes
            ):
                self._stopped = True
                raise GatewayStoppedError("output_budget_exhausted")
            self._calls += 1
            self._active += 1
            self._reserved_output_bytes += self._limits.max_result_bytes
            self._inflight.add(call_key)
        reservation_held = True
        try:
            result = result.model_copy(
                update={
                    "usage": result.usage.model_copy(update={"service_calls": 1}),
                    "is_synthetic": isinstance(call, ReadEvidenceCall)
                    and self._reader is not None
                    and self._reader.data_mode == "fixture",
                }
            )
            call_deadline = min(
                self._limits.deadline_monotonic,
                self._clock() + TOOL_SPECS[ToolName(call.tool_name)].timeout_seconds,
            )
            try:
                result = self._dispatch(call, scope, result, call_deadline)
                if self._clock() >= call_deadline:
                    result = result.model_copy(
                        update={
                            "status": ToolStatus.BUDGET_EXHAUSTED,
                            "data": None,
                            "evidence_ids": (),
                            "observed_at": None,
                            "error_code": "deadline_exhausted",
                        }
                    )
            except (CrossTenantAccessError, PermissionDeniedError, SessionExpiredError):
                result = result.model_copy(
                    update={"status": ToolStatus.DENIED, "error_code": "resource_unavailable"}
                )
            except ToolNotConfiguredError:
                result = result.model_copy(
                    update={
                        "status": ToolStatus.NOT_CONFIGURED,
                        "error_code": "executor_unavailable",
                    }
                )
            except TimeoutError:
                result = result.model_copy(
                    update={
                        "status": ToolStatus.BUDGET_EXHAUSTED,
                        "error_code": "deadline_exhausted",
                    }
                )
            except GraphSnapshotChangedError:
                result = result.model_copy(
                    update={"status": ToolStatus.PARTIAL, "error_code": "graph_snapshot_changed"}
                )
            except (ValidationError, ValueError, KnowledgeProjectionError):
                result = result.model_copy(
                    update={"status": ToolStatus.FAILED, "error_code": "tool_output_invalid"}
                )
            except DBAPIError as database_error:
                sqlstate: object = getattr(database_error.orig, "sqlstate", None)
                timeout = isinstance(sqlstate, str) and sqlstate in {"57014", "55P03"}
                result = result.model_copy(
                    update={
                        "status": ToolStatus.BUDGET_EXHAUSTED if timeout else ToolStatus.FAILED,
                        "error_code": "deadline_exhausted" if timeout else "tool_database_failed",
                    }
                )
            except SQLAlchemyError:
                result = result.model_copy(
                    update={"status": ToolStatus.FAILED, "error_code": "tool_database_failed"}
                )
            except Exception:
                result = result.model_copy(
                    update={"status": ToolStatus.FAILED, "error_code": "tool_execution_failed"}
                )
            with self._lock:
                self._reserved_output_bytes -= self._limits.max_result_bytes
                reservation_held = False
                result = self._emit(result)
                self._outcomes[call_key] = result
                return result
        finally:
            with self._lock:
                if reservation_held:
                    self._reserved_output_bytes -= self._limits.max_result_bytes
                self._active -= 1
                self._inflight.remove(call_key)

    def _dispatch(
        self, call: ToolCall, scope: AccessScope, result: ToolResult, call_deadline: float
    ) -> ToolResult:
        if isinstance(call, CompareVersionsCall):
            arguments = call.arguments
            comparison: VersionComparison = compare_versions(
                arguments.left_version,
                arguments.right_version,
                scheme=arguments.scheme,
                ecosystem=arguments.ecosystem,
            )
            return result.model_copy(
                update={
                    "status": ToolStatus.SUCCEEDED
                    if comparison.status == "comparable"
                    else ToolStatus.PARTIAL,
                    "data": comparison,
                    "error_code": None if comparison.status == "comparable" else comparison.reason,
                    "limitations": ("版本排序只比较输入版本，不是资产适用性或修复结论。",),
                }
            )
        if not isinstance(call, ReadEvidenceCall) or self._reader is None:
            raise ToolNotConfiguredError("evidence reader missing")
        read = self._reader.read_evidence(self._principal, scope, call.arguments, call_deadline)
        if not isinstance(read, EvidenceRead) or type(read.current_supported) is not bool:
            raise ValueError("invalid typed evidence outcome")
        evidence = EvidenceResponse.model_validate(read.evidence.model_dump())
        if (
            evidence.span_id != call.arguments.evidence_id
            or evidence.revision_id != call.arguments.revision_id
        ):
            raise ValueError("evidence identity mismatch")
        supported = read.current_supported and evidence.verified_at is not None
        return result.model_copy(
            update={
                "status": ToolStatus.SUCCEEDED if supported else ToolStatus.PARTIAL,
                "data": evidence,
                "evidence_ids": (evidence.span_id,),
                "observed_at": evidence.first_observed_at,
                "is_synthetic": evidence.data_mode == "fixture",
                "error_code": None if supported else "evidence_not_current_supported",
                "limitations": ("引文存在不等于任意论断被支持；仅核验指定事件的当前支持关系。",)
                if supported
                else ("引文可读，但未取得指定事件的当前有效支持；不等于否定。",),
            }
        )
