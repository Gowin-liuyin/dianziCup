"""固定公开来源的分页任务；原文、游标、后续任务与完成状态同 PG 事务。"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from math import ceil
from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit

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
    validate_vendor_after,
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
VENDOR_ADVISORY_PATH = "/repos/vllm-project/vllm/security-advisories"
VENDOR_NUMERIC_ADVISORY_PATH = "/repositories/599547518/security-advisories"
VENDOR_LINK = re.compile(
    r'<([^<>\s]+)> *; *rel *= *(?:"([A-Za-z][A-Za-z0-9. -]*)"|([A-Za-z][A-Za-z0-9.-]*)) *',
    re.IGNORECASE,
)
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
    """重建固定来源 URL；GitHub 的不透明游标只作为查询值。"""
    if source_kind not in {"nvd_ollama", "vllm_vendor"}:
        raise SourceDocumentError("unknown fixed source")
    if source_kind == "nvd_ollama":
        position = cursor.get("offset", 0)
        if set(cursor) - {"offset"} or type(position) is not int or position < 0:
            raise SourceDocumentError("invalid fixed source cursor")
        if position > 1_000_000:
            raise SourceDocumentError("source cursor position limit exceeded")
        parameters = {"keywordSearch": "ollama", "resultsPerPage": 20, "startIndex": position}
        return "https://services.nvd.nist.gov/rest/json/cves/2.0?" + urlencode(parameters)
    vendor_parameters = {"per_page": "10", "state": "published"}
    if set(cursor) == {"page"} and type(cursor["page"]) is int:
        if cursor["page"] > 1:
            raise JobExecutionError("legacy_vendor_cursor_requires_restart", blocked=True)
        if cursor["page"] != 1:
            raise SourceDocumentError("invalid legacy vendor cursor")
    elif cursor:
        if (
            set(cursor) != {"cursor_version", "after"}
            or type(cursor["cursor_version"]) is not int
            or cursor["cursor_version"] != 2
        ):
            raise SourceDocumentError("invalid vendor cursor")
        vendor_parameters["after"] = validate_vendor_after(cursor["after"])
    return "https://api.github.com" + VENDOR_ADVISORY_PATH + "?" + urlencode(vendor_parameters)


def _vendor_next_after(headers: Mapping[str, str]) -> str | None:
    """只解析 GitHub 的有界 Link 形态，并拒绝被字典解析掩盖的重复 next。"""
    values = [value for name, value in headers.items() if name.casefold() == "link"]
    if not values:
        return None
    if len(values) != 1:
        raise SourceDocumentError("ambiguous vendor Link headers")
    value = values[0]
    if (
        not value
        or len(value) > 8192
        or not value.isascii()
        or any(ord(character) < 32 or ord(character) == 127 for character in value)
    ):
        raise SourceDocumentError("invalid vendor Link header")
    links = value.split(",")
    if len(links) > 16:
        raise SourceDocumentError("vendor Link count limit exceeded")
    next_uri: str | None = None
    for link in links:
        match = VENDOR_LINK.fullmatch(link.strip())
        if match is None:
            raise SourceDocumentError("malformed vendor Link")
        relations = (match[2] or match[3]).casefold().split()
        if "next" in relations:
            if next_uri is not None or relations.count("next") != 1:
                raise SourceDocumentError("duplicate vendor next Link")
            next_uri = match[1]
    if next_uri is None:
        return None
    try:
        parts = urlsplit(next_uri)
        allowed_origin = (
            parts.scheme == "https"
            and parts.hostname == "api.github.com"
            and parts.netloc.casefold() in {"api.github.com", "api.github.com:443"}
            and parts.port in {None, 443}
            and parts.username is None
            and parts.password is None
        )
        pairs = parse_qsl(parts.query, strict_parsing=True, keep_blank_values=True, errors="strict")
    except (ValueError, UnicodeError):
        raise SourceDocumentError("invalid vendor next Link URI") from None
    parameters = dict(pairs)
    if (
        not allowed_origin
        or parts.fragment
        or parts.path not in {VENDOR_ADVISORY_PATH, VENDOR_NUMERIC_ADVISORY_PATH}
        or len(pairs) != len(parameters)
        or set(parameters) != {"per_page", "state", "after"}
        or parameters["per_page"] != "10"
        or parameters["state"] != "published"
    ):
        raise SourceDocumentError("vendor next Link is outside approved scope")
    return validate_vendor_after(parameters["after"])


def _next_position(
    source_kind: SourceKind,
    body: bytes,
    cursor: dict[str, JsonValue],
    headers: Mapping[str, str] | None = None,
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
    after = _vendor_next_after(headers or {})
    if after is None:
        return {}
    if after == cursor.get("after"):
        raise SourceDocumentError("vendor next cursor did not advance")
    return {"cursor_version": 2, "after": after}


def _http_failure(
    result: FetchResult, *, clock: Callable[[], datetime] = lambda: datetime.now(UTC)
) -> None:
    """限流期限不可确认或超出任务重试合同上限时阻塞，不能截短上游等待。"""
    if result.status_code == 200:
        return
    if result.status_code == 401:
        raise JobExecutionError("source_auth_denied", blocked=True)
    if result.status_code in {403, 429}:
        if len(result.redacted_headers) > 128:
            raise JobExecutionError("source_rate_limited", blocked=True)
        headers: dict[str, str] = {}
        for name, value in result.redacted_headers.items():
            if len(name) > 128:
                raise JobExecutionError("source_rate_limited", blocked=True)
            field = name.casefold()
            if field not in {"retry-after", "x-ratelimit-remaining", "x-ratelimit-reset"}:
                continue
            if field in headers or len(value) > 128 or not value.isascii():
                raise JobExecutionError("source_rate_limited", blocked=True)
            headers[field] = value.strip(" \t")
        remaining = headers.get("x-ratelimit-remaining")
        if remaining is not None and re.fullmatch(r"[0-9]{1,20}", remaining) is None:
            raise JobExecutionError("source_rate_limited", blocked=True)
        primary_limit = remaining is not None and int(remaining) == 0
        retry_after = headers.get("retry-after")
        if result.status_code == 403 and not primary_limit and retry_after is None:
            raise JobExecutionError("source_auth_denied", blocked=True)
        now = clock()
        if now.tzinfo is None or now.utcoffset() is None:
            raise JobExecutionError("source_rate_limited", blocked=True)
        delay = 0.0
        if primary_limit:
            reset = headers.get("x-ratelimit-reset")
            if reset is None or re.fullmatch(r"[0-9]{1,20}", reset) is None:
                raise JobExecutionError("source_rate_limited", blocked=True)
            delay = max(delay, int(reset) - now.timestamp())
        if retry_after is not None:
            if re.fullmatch(r"[0-9]{1,20}", retry_after):
                delay = max(delay, int(retry_after))
            else:
                short_day = r"(?:Mon|Tue|Wed|Thu|Fri|Sat|Sun)"
                long_day = r"(?:Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)"
                month = r"(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)"
                time = r"[0-9]{2}:[0-9]{2}:[0-9]{2}"
                obsolete_date = rf"{long_day}, [0-9]{{2}}-{month}-[0-9]{{2}} {time} GMT"
                date_patterns = (
                    rf"{short_day}, [0-9]{{2}} {month} [0-9]{{4}} {time} GMT",
                    obsolete_date,
                    rf"{short_day} {month} (?: [0-9]|[0-9]{{2}}) {time} [0-9]{{4}}",
                )
                if not any(re.fullmatch(pattern, retry_after) for pattern in date_patterns):
                    raise JobExecutionError("source_rate_limited", blocked=True)
                try:
                    retry_at = parsedate_to_datetime(retry_after)
                    if retry_at.tzinfo is None:
                        retry_at = retry_at.replace(tzinfo=UTC)
                    if re.fullmatch(obsolete_date, retry_after):
                        upper_year = now.year + 50
                        year = upper_year - (upper_year - retry_at.year % 100) % 100
                        retry_at = retry_at.replace(year=year)
                    delay = max(delay, (retry_at - now).total_seconds())
                except (ValueError, OverflowError):
                    raise JobExecutionError("source_rate_limited", blocked=True) from None
        elif not primary_limit:
            delay = 30.0
        if delay > 300:
            raise JobExecutionError("source_rate_limited", blocked=True)
        raise JobExecutionError("source_rate_limited", retry_after_seconds=max(7, ceil(delay)))
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
            _http_failure(result, clock=clock)
            observed_at = clock()
            saved = persist_source_response(
                session,
                store,
                scope,
                SourceResponse(request.source_kind, result.body, url, observed_at),
                ingested_at=clock(),
            )
            following = _next_position(
                request.source_kind, result.body, lease.cursor_json, result.redacted_headers
            )
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
