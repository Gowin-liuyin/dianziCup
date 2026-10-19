"""共享 RSS/Atom 发现与 canonical URI 归一; 各源解析/修订规则独立。"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

FEED_CONNECTOR_VERSION = "feed-1.0.0"
TRACKING_QUERY_KEYS = {
    "utm_source",
    "utm_medium",
    "utm_campaign",
    "utm_content",
    "utm_term",
    "fbclid",
    "gclid",
}


class FeedParseError(RuntimeError):
    """源结构改变或字段缺失: 进入复核, 不存空白成功。"""


@dataclass(frozen=True)
class FeedEntry:
    """发现条目: canonical URI 归一但保留改变内容的 query 参数。"""

    source_record_id: str
    canonical_uri: str
    title: str
    published_at: str | None
    modified_at: str | None
    body_text: str | None
    content_hash_sha256: str
    missing_fields: tuple[str, ...] = field(default_factory=tuple)


def canonicalize_uri(raw_uri: str) -> str:
    """归一 URI: 仅剔除跟踪参数, 保留会改变内容的 query 参数。"""
    parts = urlsplit(raw_uri)
    kept_pairs = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if key.lower() not in TRACKING_QUERY_KEYS
    ]
    normalized_query = urlencode(sorted(kept_pairs))
    return urlunsplit((parts.scheme, parts.netloc.lower(), parts.path, normalized_query, ""))


def normalize_feed_entry(payload: dict[str, object], source_record_id_prefix: str) -> FeedEntry:
    """归一单条 RSS/Atom 条目; 缺时间明确记 missing 不猜。"""
    link = payload.get("link")
    title = payload.get("title")
    if not isinstance(link, str) or not isinstance(title, str):
        raise FeedParseError("feed entry missing link or title; structure may have changed")
    canonical_uri = canonicalize_uri(link)
    record_id = (
        source_record_id_prefix
        + ":"
        + hashlib.sha256(canonical_uri.encode("utf-8")).hexdigest()[:16]
    )
    missing: list[str] = []
    published_at = payload.get("published")
    modified_at = payload.get("modified")
    body_text = payload.get("body")
    if published_at is None:
        missing.append("published")
    if modified_at is None:
        missing.append("modified")
    if body_text is None:
        missing.append("body")
    body_string = str(body_text) if body_text is not None else ""
    content_hash = hashlib.sha256(body_string.encode("utf-8")).hexdigest()
    return FeedEntry(
        source_record_id=record_id,
        canonical_uri=canonical_uri,
        title=title,
        published_at=str(published_at) if published_at is not None else None,
        modified_at=str(modified_at) if modified_at is not None else None,
        body_text=str(body_text) if body_text is not None else None,
        content_hash_sha256=content_hash,
        missing_fields=tuple(missing),
    )


NAVIGATION_MARKERS = ("nav", "menu", "footer", "sidebar", "breadcrumb")


def is_material_content_change(old_blocks: list[str], new_blocks: list[str]) -> bool:
    """修订识别: 仅导航/页脚类区块变化视为非实质变更。"""
    old_substantive = [
        block
        for block in old_blocks
        if not any(marker in block.lower() for marker in NAVIGATION_MARKERS)
    ]
    new_substantive = [
        block
        for block in new_blocks
        if not any(marker in block.lower() for marker in NAVIGATION_MARKERS)
    ]
    return old_substantive != new_substantive


def merge_duplicate_entries(entries: list[FeedEntry]) -> list[FeedEntry]:
    """同 canonical URI 多跟踪链接归为同一文档, 不误删关键参数。"""
    merged: dict[str, FeedEntry] = {}
    for entry in entries:
        merged.setdefault(entry.canonical_uri, entry)
    return list(merged.values())
