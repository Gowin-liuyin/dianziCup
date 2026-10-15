"""社区/仓库连接器: release/commit/advisory 类型分立, 固定标识可追溯。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

REPO_CONNECTOR_VERSION = "repo-1.0.0"
COMMUNITY_CONNECTOR_VERSION = "community-1.0.0"


class RepositoryFetchError(RuntimeError):
    """仓库获取失败(404/转私有/权限): 历史证据不自动撤回。"""


class RepositoryAccessBlocked(RuntimeError):
    """接口无权限: blocked_live, 不退化成伪响应。"""


@dataclass(frozen=True)
class RepositoryRecord:
    """仓库记录: 类型分立(release/commit/security_advisory), commit SHA 固定标识。"""

    record_type: str
    fixed_identifier: str
    published_at: str | None
    title: str
    related_product: str
    metadata_only_link: str | None = None
    source_schema_version: str = REPO_CONNECTOR_VERSION


@dataclass(frozen=True)
class CommunityArticle:
    """社区文章: 多漏洞各自关联, 不并成一个漏洞。"""

    article_id: str
    title: str
    body_text: str | None
    referenced_advisory_ids: tuple[str, ...] = field(default_factory=tuple)
    source_schema_version: str = COMMUNITY_CONNECTOR_VERSION


def normalize_repository_record(payload: dict[str, object]) -> RepositoryRecord:
    """归一仓库记录; release 安全关键词≠已确认漏洞(仅 metadata 关联)。"""
    record_type = payload.get("record_type")
    fixed_identifier = payload.get("fixed_identifier")
    title = payload.get("title")
    related_product = payload.get("related_product")
    if record_type not in ("release", "commit", "security_advisory"):
        raise RepositoryFetchError("unknown repository record type")
    if not isinstance(fixed_identifier, str) or not fixed_identifier:
        raise RepositoryFetchError("record missing fixed identifier")
    if record_type == "commit" and not re.fullmatch(r"[0-9a-fA-F]{40}", fixed_identifier):
        raise RepositoryFetchError("commit records must pin a full 40-char SHA, not a floating ref")
    if not isinstance(title, str) or not isinstance(related_product, str):
        raise RepositoryFetchError("record missing title or related product")
    return RepositoryRecord(
        record_type=str(record_type),
        fixed_identifier=fixed_identifier,
        published_at=str(payload["published_at"])
        if payload.get("published_at") is not None
        else None,
        title=title,
        related_product=related_product,
        metadata_only_link=str(payload["poc_link"])
        if payload.get("poc_link") is not None
        else None,
    )


def normalize_community_article(payload: dict[str, object]) -> CommunityArticle:
    """归一社区文章; 多漏洞引用逐条保留为独立关联。"""
    article_id = payload.get("article_id")
    title = payload.get("title")
    if not isinstance(article_id, str) or not isinstance(title, str):
        raise RepositoryFetchError("community article missing id or title")
    raw_refs = payload.get("referenced_advisory_ids")
    if not isinstance(raw_refs, list):
        raw_refs = []
    references = tuple(
        str(item) for item in raw_refs if isinstance(raw_refs, list) and isinstance(item, str)
    )
    body = payload.get("body")
    return CommunityArticle(
        article_id=article_id,
        title=title,
        body_text=str(body) if body is not None else None,
        referenced_advisory_ids=references,
    )


def link_release_and_fix_commit(
    release: RepositoryRecord,
    commit: RepositoryRecord,
    product: str,
) -> tuple[RepositoryRecord, RepositoryRecord, str]:
    """release 与修复 commit 可关联但不合并成同文档; 返回关联键。"""
    if release.record_type != "release" or commit.record_type != "commit":
        raise RepositoryFetchError("link requires one release and one commit record")
    if release.related_product != product or commit.related_product != product:
        raise RepositoryFetchError("linking requires records of the same product")
    relation_key = f"{product}:{release.fixed_identifier}:{commit.fixed_identifier}"
    return release, commit, relation_key


def fetch_with_access_guard(fetch_once: object) -> dict[str, object]:
    """403/401 → blocked_live; 404/410 → 明确失败且历史证据保留由调用方不撤回。"""
    response = fetch_once()  # type: ignore[operator]
    if not isinstance(response, dict):
        raise RepositoryFetchError("unexpected response shape")
    status = response.get("status_code")
    if status in (401, 403):
        raise RepositoryAccessBlocked(f"repository access blocked: {status}")
    if status in (404, 410, 451):
        raise RepositoryFetchError(f"repository record unavailable: {status}")
    if status != 200:
        raise RepositoryFetchError(f"repository fetch failed: {status}")
    return response
