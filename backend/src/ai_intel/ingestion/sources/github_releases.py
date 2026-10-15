"""固定 Ollama 公开发布记录归一；release 标识不等同于提交或漏洞。"""

from __future__ import annotations

import re
from urllib.parse import urlsplit

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.source_catalog import parse_source_timestamp
from ai_intel.ingestion.sources.repository import (
    RepositoryFetchError,
    RepositoryRecord,
    normalize_repository_record,
)

MAX_RELEASE_BYTES = 2 * 1024 * 1024
MAX_RELEASE_RECORDS = 100


def parse_github_releases(payload: bytes) -> tuple[RepositoryRecord, ...]:
    """处理固定仓库的一页实际 JSON；坏记录使整页显式失败，调用方保存原文。"""
    if not isinstance(payload, bytes) or not 1 <= len(payload) <= MAX_RELEASE_BYTES:
        raise RepositoryFetchError("release response outside byte limit")
    try:
        document = strict_json_object(b'{"releases":' + payload + b"}", MAX_RELEASE_BYTES + 13)
    except (ValueError, UnicodeError, RecursionError):
        raise RepositoryFetchError("invalid release JSON response") from None
    entries = document.get("releases")
    if set(document) != {"releases"} or not isinstance(entries, list):
        raise RepositoryFetchError("release response must be an array")
    if len(entries) > MAX_RELEASE_RECORDS:
        raise RepositoryFetchError("release page exceeds record limit")
    records: list[RepositoryRecord] = []
    identifiers: set[int] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise RepositoryFetchError("release entry must be an object")
        release_id = entry.get("id")
        if isinstance(release_id, bool) or not isinstance(release_id, int) or release_id <= 0:
            raise RepositoryFetchError("release id must be a positive integer")
        if release_id in identifiers:
            raise RepositoryFetchError("duplicate release id within page")
        identifiers.add(release_id)
        tag = entry.get("tag_name")
        name = entry.get("name")
        if not isinstance(tag, str) or not 1 <= len(tag) <= 256:
            raise RepositoryFetchError("release tag is missing or oversized")
        if name is not None and (not isinstance(name, str) or len(name) > 4096):
            raise RepositoryFetchError("release name must be bounded text when present")
        body = entry.get("body")
        if body is not None and not isinstance(body, str):
            raise RepositoryFetchError("release body must be text when present")
        if any(not isinstance(entry.get(field), bool) for field in ("draft", "prerelease")):
            raise RepositoryFetchError("release draft and prerelease must be booleans")
        target = entry.get("target_commitish")
        if target is not None and not isinstance(target, str):
            raise RepositoryFetchError("target_commitish must be text when present")
        html_url = entry.get("html_url")
        if not isinstance(html_url, str):
            raise RepositoryFetchError("release canonical URL is missing")
        try:
            parts = urlsplit(html_url)
            if (
                parts.scheme != "https"
                or parts.netloc != "github.com"
                or not parts.path.startswith("/ollama/ollama/releases/tag/")
                or not parts.path.removeprefix("/ollama/ollama/releases/tag/")
                or parts.query
                or parts.fragment
                or "\\" in html_url
                or any(ord(character) <= 32 for character in html_url)
            ):
                raise ValueError("URL outside fixed repository")
        except ValueError:
            raise RepositoryFetchError("release URL outside fixed Ollama repository") from None
        published = entry.get("published_at")
        if published is not None:
            if not isinstance(published, str):
                raise RepositoryFetchError("release published_at must be text or null")
            try:
                parse_source_timestamp(published)
                if (
                    "T" not in published
                    or re.search(r"(?:Z|[+-][0-9]{2}:[0-9]{2})$", published) is None
                ):
                    raise ValueError("timezone is missing")
            except ValueError:
                raise RepositoryFetchError("release published_at lacks a valid timezone") from None
        records.append(
            normalize_repository_record(
                {
                    "record_type": "release",
                    "fixed_identifier": f"github:ollama/ollama:release:{release_id}",
                    "published_at": published,
                    "title": name or tag,
                    "related_product": "ollama",
                }
            )
        )
    return tuple(records)
