"""固定公开来源的分页任务；原文、游标、后续任务与完成状态同 PG 事务。"""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Literal
from urllib.parse import urlencode

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from ai_intel.domain.access import AccessScope, Role
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.infrastructure.network import (
    FetchResult,
    NetworkPolicy,
    NetworkPolicyViolation,
    NetworkRequestError,
    create_network_gateway,
)
from ai_intel.infrastructure.outbox import enqueue_job
from ai_intel.ingestion.cursor_repository import (
    PersistedPageEntry,
    SourceCursorRepository,
    make_page_key,
)
from ai_intel.ingestion.source_documents import (
    SourceDocumentError,
    SourceResponse,
    ensure_source_registration,
    persist_source_response,
)
from ai_intel.ingestion.sources.nvd import normalize_nvd_page
from ai_intel.knowledge.models import fetch_attempts, outbox_events
from ai_intel.workers.executor import (
    JobExecutionContext,
    JobExecutionError,
    JobExecutionResult,
    JobHandler,
)

SOURCE_JOB_TYPE = "collect_public_source_page"
SOURCE_PAGE_DELAY_SECONDS = 7
SourceKind = Literal["nvd_ollama", "vllm_vendor"]
SourceFetcher = Callable[[str], FetchResult]


class SourcePageRequest(BaseModel):
    """只允许服务端固定来源和有界观察轮次，不接受网络目标或租户。"""

    model_config = ConfigDict(extra="forbid", strict=True, hide_input_in_errors=True)
    source_kind: SourceKind
    stream_kind: Literal["live", "backfill"] = "backfill"
    window_end: AwareDatetime
    remaining_pages: int = Field(default=20, ge=1, le=20)


def source_page_url(source_kind: SourceKind, cursor: dict[str, JsonValue]) -> str:
    """游标仅是已校验整数位置，不能变成任意 URL 或修改固定查询。"""
    if source_kind not in {"nvd_ollama", "vllm_vendor"}:
        raise SourceDocumentError("unknown fixed source")
    key, initial = ("offset", 0) if source_kind == "nvd_ollama" else ("page", 1)
    position = cursor.get(key, initial)
    if set(cursor) - {key} or type(position) is not int or position < initial:
        raise SourceDocumentError("invalid fixed source cursor")
    if position > 1_000_000:
        raise SourceDocumentError("source cursor position limit exceeded")
    if source_kind == "nvd_ollama":
        parameters = {"keywordSearch": "ollama", "resultsPerPage": 20, "startIndex": position}
        return "https://services.nvd.nist.gov/rest/json/cves/2.0?" + urlencode(parameters)
    parameters = {"per_page": 10, "state": "published", "page": position}
    return "https://api.github.com/repos/vllm-project/vllm/security-advisories?" + urlencode(
        parameters
    )


def _next_position(
    source_kind: SourceKind, body: bytes, cursor: dict[str, JsonValue]
) -> dict[str, JsonValue]:
    """只在来源写服务已严格验证同一原始响应后读取分页元数据。"""
    payload: object = json.loads(body)
    if source_kind == "nvd_ollama":
        if not isinstance(payload, dict):
            raise SourceDocumentError("invalid NVD page")
        following = normalize_nvd_page(payload).next_start_index
        return {} if following is None else {"offset": following}
    if not isinstance(payload, list) or len(payload) > 10:
        raise SourceDocumentError("invalid vendor page")
    page = cursor.get("page", 1)
    if type(page) is not int:
        raise SourceDocumentError("invalid vendor cursor")
    return {"page": page + 1} if len(payload) == 10 else {}


def _http_failure(result: FetchResult) -> None:
    if result.status_code == 200:
        return
    if result.status_code in {401, 403}:
        raise JobExecutionError("source_auth_denied", blocked=True)
    if result.status_code == 429:
        retry_after = next(
            (
                value
                for name, value in result.redacted_headers.items()
                if name.casefold() == "retry-after"
            ),
            None,
        )
        delay = 30.0
        if retry_after is not None and retry_after.isdecimal():
            delay = min(300.0, max(7.0, float(retry_after)))
        raise JobExecutionError("source_rate_limited", retry_after_seconds=delay)
    if 400 <= result.status_code < 500:
        raise JobExecutionError("source_client_error", permanent=True)
    if result.status_code >= 500:
        raise JobExecutionError("source_server_error", retry_after_seconds=7)
    raise JobExecutionError("source_unexpected_status", permanent=True)


def enqueue_source_page(
    session: Session,
    request: SourcePageRequest,
    created_at: datetime,
    *,
    idempotency_key: str | None = None,
    delay_seconds: int = 0,
) -> str:
    """仅保存 PG 任务与 outbox；调用方负责认证和事务提交。"""
    if created_at.tzinfo is None or request.window_end > created_at:
        raise ValueError("source observation window must not be in the future")
    if not 0 <= delay_seconds <= 300:
        raise ValueError("invalid source dispatch delay")
    job_id = enqueue_job(
        session,
        None,
        SOURCE_JOB_TYPE,
        request.model_dump_json().encode("utf-8"),
        created_at,
        idempotency_key=idempotency_key,
        max_attempts=3,
    )
    if delay_seconds:
        session.execute(
            update(outbox_events)
            .where(outbox_events.c.job_id == job_id, outbox_events.c.published_at.is_(None))
            .values(next_delivery_at=created_at + timedelta(seconds=delay_seconds))
        )
    return job_id


def build_source_page_handler(
    store: ContentStorage,
    *,
    dns_resolver: Literal["system", "cloudflare_doh"] = "system",
    fetcher: SourceFetcher | None = None,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> JobHandler:
    """worker 使用部署配置；只有测试显式注入 fetcher，不提供自动 fixture 后备。"""
    gateway = create_network_gateway(
        NetworkPolicy(
            allowed_domains=("services.nvd.nist.gov", "api.github.com"),
            allowed_content_types=("application/json",),
            total_timeout_seconds=12,
            dns_resolver=dns_resolver,
        ),
        max_concurrent_requests=1,
    )

    def fetch(url: str) -> FetchResult:
        return gateway.fetch(url, max_redirect_hops=0)

    read_page = fetcher or fetch

    def collect_page(
        session: Session, context: JobExecutionContext, payload: bytes
    ) -> JobExecutionResult:
        request = SourcePageRequest.model_validate_json(payload)
        if context.tenant_id is not None:
            raise JobExecutionError("source_scope_denied", blocked=True)
        scope = AccessScope.for_authenticated_user("source-worker", None, Role.SYSTEM_ADMIN)
        source_id = ensure_source_registration(session, scope, request.source_kind, clock())
        repository = SourceCursorRepository(session, scope, source_id, clock=clock)
        lease = repository.claim(
            stream_kind=request.stream_kind,
            lease_owner=context.job_id,
            window_start=None,
            window_end=request.window_end,
        )
        if lease is None:
            raise JobExecutionError("source_busy", retry_after_seconds=7)
        try:
            last_observed = session.scalar(
                select(func.max(fetch_attempts.c.attempted_at)).where(
                    fetch_attempts.c.source_id == source_id
                )
            )
            if last_observed is not None and clock() < last_observed + timedelta(seconds=7):
                raise JobExecutionError("source_poll_interval", retry_after_seconds=7)
            url = source_page_url(request.source_kind, lease.cursor_json)
            result = read_page(url)
            _http_failure(result)
            observed_at = clock()
            saved = persist_source_response(
                session,
                store,
                scope,
                SourceResponse(request.source_kind, result.body, url, observed_at),
                ingested_at=clock(),
            )
            following = _next_position(request.source_kind, result.body, lease.cursor_json)
            entries: tuple[dict[str, object], ...] = tuple(
                {
                    "entry_id": revision_id,
                    "source_id": source_id,
                    "visibility": "public",
                    "tenant_id": None,
                    "response_sha256": saved.response_content_hash,
                    "revision_id": revision_id,
                }
                for revision_id in saved.revision_ids
            )

            def persisted_entry(
                current_session: Session, entry: dict[str, object]
            ) -> PersistedPageEntry:
                revision_id = entry["revision_id"]
                if current_session is not session or not isinstance(revision_id, str):
                    raise SourceDocumentError("invalid persisted page reference")
                return PersistedPageEntry(revision_id=revision_id)

            repository.commit_page(
                lease,
                page_key=make_page_key(lease, lease.cursor_json),
                input_cursor=lease.cursor_json,
                output_cursor=following,
                entries=entries,
                persist_entry=persisted_entry,
                is_last_page=not following,
            )
            repository.release(lease)
            if following and request.remaining_pages == 1:
                return JobExecutionResult(
                    outcome="partial",
                    result_ref="pg:source:" + source_id,
                    error_code="source_page_limit_reached",
                )
            if following:
                continuation = request.model_copy(
                    update={
                        "window_end": lease.window_end,
                        "remaining_pages": request.remaining_pages - 1,
                    }
                )
                enqueue_source_page(
                    session,
                    continuation,
                    clock(),
                    idempotency_key="source-next-" + context.job_id,
                    delay_seconds=SOURCE_PAGE_DELAY_SECONDS,
                )
            return JobExecutionResult(result_ref="pg:source:" + source_id)
        except NetworkPolicyViolation:
            raise JobExecutionError("source_network_policy_denied", blocked=True) from None
        except NetworkRequestError as error:
            raise JobExecutionError(error.code, retry_after_seconds=7) from None
        except (SourceDocumentError, ValueError):
            raise JobExecutionError("source_response_invalid", blocked=True) from None

    return collect_page
