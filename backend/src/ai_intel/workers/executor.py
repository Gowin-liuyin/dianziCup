"""固定handler默认原子提交；显式detached服务在释放job锁后执行。"""

from __future__ import annotations

import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import insert, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from ai_intel.knowledge.models import fetch_attempts
from ai_intel.workers.jobs import (
    JobLeaseLostError,
    JobPayloadUnavailableError,
    claim_job,
    complete_job,
    read_job_payload,
    require_job_lease,
    schedule_retry_or_fail,
    validate_job_result_fields,
)


def utc_now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class JobExecutionContext:
    job_id: str
    worker_id: str
    attempt_count: int
    tenant_id: str | None


@dataclass(frozen=True)
class JobExecutionResult:
    outcome: Literal["succeeded", "partial", "failed", "blocked"] = "succeeded"
    result_ref: str | None = None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if self.outcome not in {"succeeded", "partial", "failed", "blocked"}:
            raise ValueError("invalid handler outcome")
        validate_job_result_fields(self.result_ref, self.error_code)


class JobExecutionError(RuntimeError):
    """已分类的安全错误码，不携带上游凭据或未受控异常文本。"""

    def __init__(
        self,
        error_code: str,
        *,
        permanent: bool = False,
        blocked: bool = False,
        retry_after_seconds: float | None = None,
    ) -> None:
        if not re.fullmatch("[a-z][a-z0-9_]{0,99}", error_code):
            raise ValueError("invalid handler error code")
        if retry_after_seconds is not None and not 0 <= retry_after_seconds <= 300:
            raise ValueError("invalid Retry-After")
        super().__init__(error_code)
        self.error_code = error_code
        self.permanent = permanent
        self.blocked = blocked
        self.retry_after_seconds = retry_after_seconds


JobHandler = Callable[[Session, JobExecutionContext, bytes], JobExecutionResult]


@dataclass(frozen=True)
class DetachedJobHandler:
    """仅服务端registry显式构造；服务须自行鉴权、围栏与PG幂等。

    没有worker Session传入，外部IO前释放服务自己的锁；效果已提交而
    完成租约丢失时不会回滚效果，重放必须沿服务台账，不能重复付费。
    completion_guard仅在最终事务做有界校验，不执行外部IO或接管Session生命周期。
    """

    handler: Callable[[JobExecutionContext, bytes], JobExecutionResult]
    completion_guard: (
        Callable[[Session, JobExecutionContext, bytes, JobExecutionResult], None] | None
    ) = None


def execute_job(
    engine: Engine,
    job_id: str,
    worker_id: str,
    handlers: Mapping[str, JobHandler | DetachedJobHandler],
    *,
    clock: Callable[[], datetime] = utc_now,
) -> str:
    """短认领后按服务端类型执行；失败沿现有fresh事务有界重试。"""
    UUID(job_id)
    with Session(engine) as session, session.begin():
        claimed = claim_job(session, job_id, worker_id, clock())
    if claimed is None:
        return "not_claimed"
    attempt_count = claimed["attempt_count"]
    tenant_id = claimed["tenant_id"]
    if not isinstance(attempt_count, int) or (
        tenant_id is not None and not isinstance(tenant_id, str)
    ):
        raise RuntimeError("job row violates execution contract")
    context = JobExecutionContext(job_id, worker_id, attempt_count, tenant_id)
    failure: JobExecutionError
    try:
        with Session(engine) as session, session.begin():
            require_job_lease(session, job_id, worker_id, clock(), expected_attempt=attempt_count)
            handler = handlers.get(str(claimed["job_type"]))
            if handler is None:
                raise JobExecutionError("unsupported_job_type", blocked=True)
            payload = read_job_payload(session, job_id, tenant_id)
            if not isinstance(handler, DetachedJobHandler):
                result = handler(session, context, payload)
                complete_job(
                    session,
                    job_id,
                    worker_id,
                    result.outcome,
                    clock(),
                    expected_attempt=attempt_count,
                    result_ref=result.result_ref,
                    error_code=result.error_code,
                )
                return result.outcome
        result = handler.handler(context, payload)
        with Session(engine) as session, session.begin():
            require_job_lease(session, job_id, worker_id, clock(), expected_attempt=attempt_count)
            if handler.completion_guard is not None:
                handler.completion_guard(session, context, payload, result)
            complete_job(
                session,
                job_id,
                worker_id,
                result.outcome,
                clock(),
                expected_attempt=attempt_count,
                result_ref=result.result_ref,
                error_code=result.error_code,
            )
            return result.outcome
    except JobLeaseLostError:
        return "lease_lost"
    except JobPayloadUnavailableError as error:
        failure = JobExecutionError(str(error), blocked=True)
    except JobExecutionError as error:
        failure = error
    except ValidationError:
        failure = JobExecutionError("invalid_job_payload", blocked=True)
    except SQLAlchemyError:
        failure = JobExecutionError("database_operation_failed")
    except Exception:
        failure = JobExecutionError("handler_failed")
    try:
        with Session(engine) as session, session.begin():
            return schedule_retry_or_fail(
                session,
                job_id,
                worker_id,
                failure.permanent,
                clock(),
                expected_attempt=attempt_count,
                error_code=failure.error_code,
                blocked=failure.blocked,
                retry_after_seconds=failure.retry_after_seconds,
            )
    except JobLeaseLostError:
        return "lease_lost"


class SourceFetchFailure(BaseModel):
    """固定来源已观测失败的持久记录，不接受URL、SQL、租户或凭据。"""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    source_id: str = Field(min_length=1, max_length=200)
    observed_at: datetime
    http_status: int | None = Field(default=None, ge=400, le=599)


def record_source_fetch_failure(
    session: Session,
    context: JobExecutionContext,
    payload: bytes,
) -> JobExecutionResult:
    """真实PG效果供来源服务复用；来源范围只来自配置表和任务上下文。"""
    request = SourceFetchFailure.model_validate_json(payload)
    if request.observed_at.tzinfo is None or request.observed_at.utcoffset() is None:
        raise JobExecutionError("invalid_job_payload", blocked=True)
    source = (
        session.execute(
            text("SELECT source_id, tenant_id FROM sources WHERE source_id=:source_id"),
            {"source_id": request.source_id},
        )
        .mappings()
        .first()
    )
    if source is None or source["tenant_id"] != context.tenant_id:
        raise JobExecutionError("source_scope_denied", blocked=True)
    attempt_id = str(uuid5(NAMESPACE_URL, "ai-intel:fetch-failure:" + context.job_id))
    session.execute(
        insert(fetch_attempts).values(
            attempt_id=attempt_id,
            source_id=request.source_id,
            attempted_at=request.observed_at,
            outcome="auth_stopped" if request.http_status in {401, 403} else "failed",
            http_status=request.http_status,
            new_event_count=0,
        )
    )
    return JobExecutionResult(result_ref="pg:fetch_attempt:" + attempt_id)
