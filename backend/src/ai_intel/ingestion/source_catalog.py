"""服务端固定公开来源与有界请求；类别、内容范围和采集阶段分别表达。"""

from __future__ import annotations

import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import urlencode
from uuid import NAMESPACE_URL, uuid5

from pydantic import JsonValue

from ai_intel.domain.enums import SourceCategory

SourceKind = Literal[
    "nvd_ollama",
    "vllm_vendor",
    "osv_ollama",
    "avid_community",
    "ollama_releases",
    "trailofbits_blog",
    "arxiv_security",
    "nist_ai_rmf",
    "cac_generative_ai",
]


class SourceCatalogError(ValueError):
    """来源或游标不属于服务端允许的公开采集范围。"""


@dataclass(frozen=True)
class CatalogSource:
    """固定身份不随别名、入口页、内容版本或抓取状态变化。"""

    source_id: str
    name: str
    category: SourceCategory
    base_origin: str
    content_scope: str


@dataclass(frozen=True)
class CatalogRequest:
    """只允许来源适配器构建请求，原始游标不作为URL或任意POST正文。"""

    method: Literal["GET", "POST"]
    url: str
    json_body: dict[str, JsonValue] | None = None


def _source(
    key: str, name: str, category: SourceCategory, origin: str, content_scope: str
) -> CatalogSource:
    return CatalogSource(
        str(uuid5(NAMESPACE_URL, "dianzi:source:" + key.replace("_", "-"))),
        name,
        category,
        origin,
        content_scope,
    )


CATALOG_SOURCES: dict[SourceKind, CatalogSource] = {
    "nvd_ollama": _source(
        "nvd_ollama",
        "NVD Ollama keyword window",
        SourceCategory.STRUCTURED_VULNERABILITY,
        "https://services.nvd.nist.gov",
        "product_vulnerability",
    ),
    "vllm_vendor": _source(
        "vllm_vendor",
        "vLLM repository security advisories",
        SourceCategory.VENDOR_ADVISORY,
        "https://api.github.com",
        "vendor_advisory",
    ),
    "osv_ollama": _source(
        "osv_ollama",
        "OSV Ollama Go package",
        SourceCategory.STRUCTURED_VULNERABILITY,
        "https://api.osv.dev",
        "package_vulnerability",
    ),
    "avid_community": _source(
        "avid_community",
        "AVID AI vulnerability database",
        SourceCategory.SECURITY_COMMUNITY,
        "https://api.github.com",
        "community_report",
    ),
    "ollama_releases": _source(
        "ollama_releases",
        "Ollama official repository releases",
        SourceCategory.CODE_REPOSITORY,
        "https://api.github.com",
        "release_metadata_not_confirmed_vulnerability",
    ),
    "trailofbits_blog": _source(
        "trailofbits_blog",
        "Trail of Bits security research",
        SourceCategory.TECHNICAL_BLOG,
        "https://blog.trailofbits.com",
        "research_article",
    ),
    "arxiv_security": _source(
        "arxiv_security",
        "arXiv AI security research",
        SourceCategory.ACADEMIC_PAPER,
        "https://export.arxiv.org",
        "paper_metadata_full_text_separate",
    ),
    "nist_ai_rmf": _source(
        "nist_ai_rmf",
        "NIST AI RMF 1.0",
        SourceCategory.TECHNICAL_STANDARD,
        "https://nvlpubs.nist.gov",
        "voluntary_framework",
    ),
    "cac_generative_ai": _source(
        "cac_generative_ai",
        "CAC generative AI service measures",
        SourceCategory.POLICY_REGULATION,
        "https://www.cac.gov.cn",
        "official_policy_no_applicability_assessment",
    ),
}

HEX_SHA = re.compile(r"[0-9a-f]{40}\Z")


def parse_source_timestamp(value: object) -> datetime | None:
    """只有来源显式给出时区的时间可进入时延分母，日期精度原值另存。"""
    if value is None:
        return None
    if not isinstance(value, str) or len(value) > 64:
        raise SourceCatalogError("invalid source timestamp")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        raise SourceCatalogError("invalid source timestamp") from None
    return parsed.astimezone(UTC) if parsed.utcoffset() is not None else None


def _page(cursor: Mapping[str, object], *, maximum: int) -> int:
    value = cursor.get("page", 1)
    if set(cursor) - {"page"} or type(value) is not int or not 1 <= value <= maximum:
        raise SourceCatalogError("invalid source page")
    return value


def build_catalog_request(source_kind: SourceKind, cursor: Mapping[str, object]) -> CatalogRequest:
    """来源固定域/路径/包名；分页只允许预定义的有界值。"""
    if source_kind not in CATALOG_SOURCES:
        raise SourceCatalogError("unknown public source")
    if source_kind == "ollama_releases":
        return CatalogRequest(
            "GET",
            "https://api.github.com/repos/ollama/ollama/releases?"
            + urlencode({"per_page": 20, "page": _page(cursor, maximum=100)}),
        )
    if source_kind == "osv_ollama":
        if set(cursor) - {"page_token"}:
            raise SourceCatalogError("invalid OSV cursor")
        body: dict[str, JsonValue] = {
            "package": {"ecosystem": "Go", "name": "github.com/ollama/ollama"}
        }
        if cursor:
            token = cursor.get("page_token")
            if (
                not isinstance(token, str)
                or not 1 <= len(token) <= 2048
                or not token.isascii()
                or any(ord(character) <= 32 or ord(character) == 127 for character in token)
            ):
                raise SourceCatalogError("invalid OSV page token")
            body["page_token"] = token
        return CatalogRequest("POST", "https://api.osv.dev/v1/query", body)
    if source_kind == "avid_community":
        if not cursor:
            return CatalogRequest(
                "GET", "https://api.github.com/repos/avidml/avid-db/git/trees/main?recursive=1"
            )
        if set(cursor) == {"tree_sha", "record_offset"}:
            tree_sha, offset = cursor["tree_sha"], cursor["record_offset"]
            if (
                not isinstance(tree_sha, str)
                or HEX_SHA.fullmatch(tree_sha) is None
                or type(offset) is not int
                or not 0 <= offset <= 2000
            ):
                raise SourceCatalogError("invalid AVID pinned tree position")
            return CatalogRequest(
                "GET",
                "https://api.github.com/repos/avidml/avid-db/git/trees/"
                + tree_sha
                + "?recursive=1",
            )
        sha = cursor.get("blob_sha")
        if (
            set(cursor) != {"blob_sha"}
            or not isinstance(sha, str)
            or HEX_SHA.fullmatch(sha) is None
        ):
            raise SourceCatalogError("invalid AVID immutable blob")
        return CatalogRequest("GET", "https://api.github.com/repos/avidml/avid-db/git/blobs/" + sha)
    if source_kind == "arxiv_security":
        if set(cursor) == {"start"}:
            start = cursor["start"]
            if type(start) is not int or not 0 <= start <= 20000:
                raise SourceCatalogError("invalid arXiv source position")
        else:
            start = (_page(cursor, maximum=100) - 1) * 20
        return CatalogRequest(
            "GET",
            "https://export.arxiv.org/api/query?"
            + urlencode(
                {
                    "search_query": 'all:"AI security"',
                    "start": start,
                    "max_results": 20,
                    "sortBy": "lastUpdatedDate",
                    "sortOrder": "descending",
                }
            ),
        )
    if cursor:
        raise SourceCatalogError("source endpoint does not accept a cursor")
    if source_kind == "trailofbits_blog":
        return CatalogRequest("GET", "https://blog.trailofbits.com/index.xml")
    if source_kind == "nist_ai_rmf":
        return CatalogRequest("GET", "https://nvlpubs.nist.gov/nistpubs/ai/NIST.AI.100-1.pdf")
    if source_kind == "cac_generative_ai":
        return CatalogRequest("GET", "https://www.cac.gov.cn/2023-07/13/c_1690898327029107.htm")
    raise SourceCatalogError("legacy source request must use its existing paging adapter")
