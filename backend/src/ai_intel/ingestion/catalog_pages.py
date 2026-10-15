"""固定来源响应转可追溯资料页；发现、原文、时间精度和风险结论分开。"""

from __future__ import annotations

import base64
import binascii
import hashlib
import json
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from html.parser import HTMLParser
from urllib.parse import parse_qsl, quote, urlsplit

from pydantic import JsonValue

from ai_intel.domain.enums import DocumentKind
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.catalog_documents import NormalizedSourceDocument
from ai_intel.ingestion.parsing.parsers import (
    parse_html_document,
    parse_json_document,
    parse_pdf_text_layer,
)
from ai_intel.ingestion.source_catalog import (
    HEX_SHA,
    SourceCatalogError,
    SourceKind,
    build_catalog_request,
    parse_source_timestamp,
)
from ai_intel.ingestion.sources.arxiv_atom import parse_arxiv_atom
from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.osv import normalize_osv_record
from ai_intel.ingestion.sources.trailofbits_rss import parse_trailofbits_rss


@dataclass(frozen=True)
class CatalogPage:
    documents: tuple[NormalizedSourceDocument, ...]
    next_cursor: dict[str, JsonValue]


@dataclass(frozen=True)
class AvidBlobSelection:
    """浮动目录先固定tree；正文再按Git blob身份读取并验证。"""

    tree_sha: str
    blob_sha: str
    path: str
    next_cursor: dict[str, JsonValue]


def _json_document(
    identifier: str,
    kind: DocumentKind,
    title: str,
    uri: str,
    fields: object,
    published: str | None,
    modified: str | None,
    metadata: dict[str, JsonValue],
    locator: str,
) -> NormalizedSourceDocument:
    payload = json.dumps(
        fields, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()
    return NormalizedSourceDocument(
        identifier,
        kind,
        title,
        uri,
        payload,
        parse_json_document(payload),
        parse_source_timestamp(published),
        parse_source_timestamp(modified),
        {**metadata, "source_adapter_version": "catalog-pages-1"},
        locator,
    )


def select_avid_blob(body: bytes, cursor: dict[str, JsonValue]) -> AvidBlobSelection | None:
    build_catalog_request("avid_community", cursor)
    tree = strict_json_object(body, 5 * 1024 * 1024, maximum_nodes=50000)
    tree_sha = tree.get("sha")
    if (
        not isinstance(tree_sha, str)
        or HEX_SHA.fullmatch(tree_sha) is None
        or tree.get("truncated") is not False
        or (cursor and cursor.get("tree_sha") != tree_sha)
    ):
        raise SourceCatalogError("AVID directory is truncated or changed from pinned tree")
    entries = tree.get("tree")
    if not isinstance(entries, list) or len(entries) > 5000:
        raise SourceCatalogError("AVID tree entries outside limit")
    candidates: list[tuple[str, str]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            raise SourceCatalogError("invalid AVID tree entry")
        path = entry.get("path")
        if not isinstance(path, str) or len(path) > 1000:
            raise SourceCatalogError("invalid AVID tree path")
        if re.fullmatch(r"vulnerabilities/([0-9]{4})/AVID-\1-V[0-9]{3,6}\.json", path):
            digest, size = entry.get("sha"), entry.get("size")
            if (
                entry.get("type") != "blob"
                or not isinstance(digest, str)
                or HEX_SHA.fullmatch(digest) is None
                or type(size) is not int
                or not 1 <= size <= 2 * 1024 * 1024
            ):
                raise SourceCatalogError("AVID vulnerability has invalid immutable blob")
            candidates.append((path, digest))
    candidates.sort(reverse=True)
    if len(candidates) > 2000 or len({path for path, _ in candidates}) != len(candidates):
        raise SourceCatalogError("AVID vulnerability identities ambiguous or outside limit")
    offset = cursor.get("record_offset", 0)
    if type(offset) is not int or offset < 0 or offset > len(candidates):
        raise SourceCatalogError("AVID record offset outside pinned tree")
    if not candidates and offset == 0:
        return None
    if offset == len(candidates):
        raise SourceCatalogError("AVID continuation points beyond last record")
    path, digest = candidates[offset]
    following: dict[str, JsonValue] = (
        {"tree_sha": tree_sha, "record_offset": offset + 1} if offset + 1 < len(candidates) else {}
    )
    return AvidBlobSelection(tree_sha, digest, path, following)


def normalize_avid_blob(selection: AvidBlobSelection, body: bytes) -> NormalizedSourceDocument:
    blob = strict_json_object(body, 3 * 1024 * 1024)
    content, size = blob.get("content"), blob.get("size")
    if (
        blob.get("sha") != selection.blob_sha
        or blob.get("encoding") != "base64"
        or not isinstance(content, str)
        or type(size) is not int
        or not 1 <= size <= 2 * 1024 * 1024
    ):
        raise SourceCatalogError("AVID blob envelope does not match fixed object")
    try:
        payload = base64.b64decode(content.replace("\n", "").replace("\r", ""), validate=True)
    except (ValueError, binascii.Error):
        raise SourceCatalogError("AVID blob has invalid base64 content") from None
    digest = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
    if len(payload) != size or digest != selection.blob_sha:
        raise SourceCatalogError("AVID decoded blob integrity failed")
    article = normalize_avid_vulnerability(payload)
    if selection.path.rsplit("/", 1)[-1] != article.article_id + ".json":
        raise SourceCatalogError("AVID blob record differs from selected path")
    raw = strict_json_object(payload, 2 * 1024 * 1024)
    published = raw.get("published_date")
    if published is not None and not isinstance(published, str):
        raise SourceCatalogError("AVID publication date is not text")
    return NormalizedSourceDocument(
        article.article_id,
        DocumentKind.ARTICLE,
        article.title,
        "https://api.github.com/repos/avidml/avid-db/git/blobs/" + selection.blob_sha,
        payload,
        parse_json_document(payload),
        None,
        None,
        {
            "source_adapter_version": "catalog-pages-1",
            "content_coverage": "full_text",
            "published_at_raw": published,
            "published_precision": "calendar_date" if published else "unknown",
            "referenced_advisory_ids": list(article.referenced_advisory_ids),
            "git_tree_sha": selection.tree_sha,
            "git_blob_sha": selection.blob_sha,
            "source_notes": [
                "已校验固定Git blob原文；仅日期精度，不推测UTC时区；社区记录不代表资产影响确认。"
            ],
        },
        selection.path,
    )


def _arxiv_page(body: bytes, cursor: dict[str, JsonValue]) -> CatalogPage:
    build_catalog_request("arxiv_security", cursor)
    page = parse_arxiv_atom(body)
    if "start" in cursor:
        expected_start = cursor["start"]
    else:
        page_number = cursor.get("page", 1)
        if type(page_number) is not int:
            raise SourceCatalogError("arXiv page is not an integer")
        expected_start = (page_number - 1) * 20
    if page.start_index != expected_start:
        raise SourceCatalogError("arXiv response differs from requested position")
    documents = []
    for index, record in enumerate(page.records):
        metadata: dict[str, JsonValue] = {
            "content_coverage": "abstract" if record.abstract else "metadata",
            "published_at_raw": record.published_at,
            "full_text_fetched": False,
            "version_label": record.version_label,
            "license_identifier": record.license_identifier,
            "withdrawal_notice_observed": record.withdrawn,
            "source_notes": [
                "本次采集论文标题、作者和摘要；未抓取论文全文，不据此判定资产受影响。"
            ],
        }
        documents.append(
            _json_document(
                record.paper_id,
                DocumentKind.PAPER,
                record.title,
                "https://arxiv.org/abs/"
                + record.paper_id.removeprefix("arxiv:")
                + record.version_label,
                {
                    "title": record.title,
                    "authors": record.authors,
                    "abstract": record.abstract,
                    "version": record.version_label,
                    "published": record.published_at,
                    "updated": record.modified_at,
                    "license": record.license_identifier,
                },
                record.published_at,
                record.modified_at,
                metadata,
                f"feed/entry[{index + 1}]",
            )
        )
    next_start = page.start_index + len(page.records)
    return CatalogPage(
        tuple(documents), {"start": next_start} if next_start < page.total_results else {}
    )


def _rss_page(body: bytes) -> CatalogPage:
    return CatalogPage(
        tuple(
            _json_document(
                record.source_record_id,
                DocumentKind.ARTICLE,
                record.title,
                record.canonical_uri,
                {
                    "title": record.title,
                    "description": record.body_text,
                    "published": record.published_at,
                    "canonical_uri": record.canonical_uri,
                },
                record.published_at,
                record.modified_at,
                {
                    "content_coverage": "feed_excerpt" if record.body_text else "metadata",
                    "published_at_raw": record.published_at,
                    "full_text_fetched": False,
                    "source_notes": ["RSS发现/摘要片段；未抓取文章正文，许可未核实。"],
                },
                f"rss/channel/item[{index + 1}]",
            )
            for index, record in enumerate(parse_trailofbits_rss(body))
        ),
        {},
    )


def _release_next(headers: Mapping[str, str], cursor: dict[str, JsonValue]) -> dict[str, JsonValue]:
    values = [value for name, value in headers.items() if name.casefold() == "link"]
    if not values:
        return {}
    if len(values) != 1 or len(values[0]) > 8192 or not values[0].isascii():
        raise SourceCatalogError("release pagination header invalid")
    following = None
    for link in values[0].split(","):
        match = re.fullmatch(r'\s*<([^<>\s]+)>\s*;\s*rel="([a-z ]+)"\s*', link)
        if match is None:
            raise SourceCatalogError("release pagination link invalid")
        if "next" not in match[2].split():
            continue
        if following is not None or match[2].split().count("next") != 1:
            raise SourceCatalogError("release has duplicate next pages")
        uri = urlsplit(match[1])
        pairs = parse_qsl(uri.query, strict_parsing=True)
        params = dict(pairs)
        expected = cursor.get("page", 1)
        if (
            uri.scheme != "https"
            or uri.netloc != "api.github.com"
            or uri.path not in {"/repos/ollama/ollama/releases", "/repositories/658928958/releases"}
            or uri.fragment
            or set(params) != {"per_page", "page"}
            or len(pairs) != 2
            or params["per_page"] != "20"
            or type(expected) is not int
            or params["page"] != str(expected + 1)
        ):
            raise SourceCatalogError("release continuation outside fixed repository position")
        following = expected + 1
    return {"page": following} if following is not None else {}


def _release_page(
    body: bytes, cursor: dict[str, JsonValue], headers: Mapping[str, str]
) -> CatalogPage:
    build_catalog_request("ollama_releases", cursor)
    records = parse_github_releases(body)
    raw = strict_json_object(b'{"items":' + body + b"}", 3 * 1024 * 1024)["items"]
    if not isinstance(raw, list):
        raise SourceCatalogError("release raw page unavailable")
    documents = []
    for index, (record, item) in enumerate(zip(records, raw, strict=True)):
        if not isinstance(item, dict) or not isinstance(item.get("html_url"), str):
            raise SourceCatalogError("release source URI unavailable")
        documents.append(
            _json_document(
                record.fixed_identifier,
                DocumentKind.REPOSITORY_RECORD,
                record.title,
                item["html_url"],
                item,
                record.published_at,
                None,
                {
                    "content_coverage": "metadata",
                    "published_at_raw": record.published_at,
                    "prerelease": item["prerelease"],
                    "draft": item["draft"],
                    "risk_status": "not_assessed",
                    "source_notes": [
                        "发布记录和原始说明；发布标签或安全词语不等于已确认漏洞/修复。"
                    ],
                },
                "/" + str(index),
            )
        )
    following = _release_next(headers, cursor)
    if following and len(documents) != 20:
        raise SourceCatalogError("release non-final page does not match requested page size")
    return CatalogPage(tuple(documents), following)


def _osv_page(body: bytes, cursor: dict[str, JsonValue]) -> CatalogPage:
    build_catalog_request("osv_ollama", cursor)
    raw = strict_json_object(body, 5 * 1024 * 1024, maximum_nodes=50000)
    records = raw.get("vulns", [])
    token = raw.get("next_page_token")
    if not isinstance(records, list) or len(records) > 100:
        raise SourceCatalogError("OSV query records outside page limit")
    if token is not None and (not isinstance(token, str) or not token):
        raise SourceCatalogError("OSV next page token invalid")
    following: dict[str, JsonValue] = {"page_token": token} if token else {}
    if following:
        build_catalog_request("osv_ollama", following)
        if token == cursor.get("page_token") or not records:
            raise SourceCatalogError("OSV continuation did not advance")
    documents = []
    for index, item in enumerate(records):
        if not isinstance(item, dict):
            raise SourceCatalogError("OSV record must be an object")
        record = normalize_osv_record(item)
        if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,255}", record.osv_id) is None:
            raise SourceCatalogError("OSV canonical identifier invalid")
        summary, published = item.get("summary", record.osv_id), item.get("published")
        if not isinstance(summary, str) or (
            published is not None and not isinstance(published, str)
        ):
            raise SourceCatalogError("OSV title or publication invalid")
        documents.append(
            _json_document(
                record.osv_id,
                DocumentKind.ADVISORY,
                summary,
                "https://api.osv.dev/v1/vulns/" + quote(record.osv_id, safe=""),
                item,
                published,
                record.modified_at,
                {
                    "content_coverage": "full_text",
                    "published_at_raw": published,
                    "aliases": list(record.aliases),
                    "related": list(record.related),
                    "upstream": list(record.upstream),
                    "withdrawn": record.withdrawn,
                    "source_notes": [
                        "结构化漏洞源原文；保留独立范围分支，不据此直接确认本地资产受影响。"
                    ],
                },
                "/vulns/" + str(index),
            )
        )
    return CatalogPage(tuple(documents), following)


class _PolicyMetadata(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self.values: dict[str, str] = {}
        self.main_depth = 0
        self.main_count = 0
        self.main_parts: list[str] = []
        self.info_depth = 0
        self.info_parts: list[str] = []

    def _append(self, value: str) -> None:
        if self.main_depth:
            self.main_parts.append(value)
        if self.info_depth:
            self.info_parts.append(value)

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        classes = (values.get("class") or "").split()
        if tag == "div":
            if self.main_depth:
                self.main_depth += 1
            elif "main-content" in classes:
                self.main_depth = 1
                self.main_count += 1
            if self.info_depth:
                self.info_depth += 1
            elif "info" in classes:
                self.info_depth = 1
            if max(self.main_depth, self.info_depth) > 64 or self.main_count > 1:
                raise SourceCatalogError("policy content containers outside bounds")
        start_tag = self.get_starttag_text()
        if start_tag is None:
            raise SourceCatalogError("policy start tag unavailable")
        self._append(start_tag)
        if tag == "meta" and values.get("name") in {"ArticleTitle", "PubDate"}:
            name, content = values["name"], values.get("content")
            if name is not None and content is not None:
                if name in self.values:
                    raise SourceCatalogError("policy metadata field repeated")
                self.values[name] = content

    def handle_endtag(self, tag: str) -> None:
        self._append("</" + tag + ">")
        if tag == "div":
            self.main_depth = max(0, self.main_depth - 1)
            self.info_depth = max(0, self.info_depth - 1)

    def handle_data(self, data: str) -> None:
        self._append(data)

    def handle_entityref(self, name: str) -> None:
        self._append("&" + name + ";")

    def handle_charref(self, name: str) -> None:
        self._append("&#" + name + ";")


def _policy_document(body: bytes) -> NormalizedSourceDocument:
    decoded = body.decode("utf-8", errors="strict")
    meta = _PolicyMetadata()
    meta.feed(decoded)
    meta.close()
    if meta.main_count != 1 or meta.main_depth:
        raise SourceCatalogError("policy main-content is missing or incomplete")
    parsed = parse_html_document("".join(meta.main_parts).encode())
    title = "生成式人工智能服务管理暂行办法"
    if title not in parsed.normalized_text:
        raise SourceCatalogError("policy response does not contain expected official title")
    ordinals = (
        "一",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
        "十三",
        "十四",
        "十五",
        "十六",
        "十七",
        "十八",
        "十九",
        "二十",
        "二十一",
        "二十二",
        "二十三",
        "二十四",
    )
    headings = []
    for block in parsed.blocks:
        match = re.match(r"^第([一二三四五六七八九十]+)条", block.text)
        if match:
            headings.append(match[1])
    if tuple(headings) != ordinals or "施行" not in parsed.normalized_text:
        raise SourceCatalogError("policy does not contain all original articles")
    published = meta.values.get("PubDate")
    precision = "unknown"
    if published is not None:
        date.fromisoformat(published)
        precision = "calendar_date"
    else:
        info = parse_html_document("".join(meta.info_parts).encode()).normalized_text
        visible = re.search(r"[0-9]{4}年[0-9]{2}月[0-9]{2}日\s+[0-9]{2}:[0-9]{2}", info)
        if visible:
            published = visible[0]
            datetime.strptime(published, "%Y年%m月%d日 %H:%M")
    return NormalizedSourceDocument(
        "cac:2023:generative-ai-service-measures",
        DocumentKind.POLICY,
        title,
        build_catalog_request("cac_generative_ai", {}).url,
        body,
        parsed,
        None,
        None,
        {
            "source_adapter_version": "catalog-pages-1",
            "content_coverage": "full_text",
            "published_at_raw": published,
            "published_precision": precision,
            "source_notes": [
                "仅呈现官方原文条款；未推测来源时区，不代表对任一资产适用性或合规结论。"
            ],
        },
    )


def _nist_document(body: bytes) -> NormalizedSourceDocument:
    parsed = parse_pdf_text_layer(body)
    if parsed.status not in {"parsed", "partial"} or not re.search(
        r"NIST\s*AI\s*100[.-]1", parsed.normalized_text
    ):
        raise SourceCatalogError("NIST PDF text or expected document identity unavailable")
    published = "January 2023" if re.search(r"January\s+2023", parsed.normalized_text) else None
    return NormalizedSourceDocument(
        "NIST.AI.100-1",
        DocumentKind.STANDARD,
        "Artificial Intelligence Risk Management Framework (AI RMF 1.0)",
        build_catalog_request("nist_ai_rmf", {}).url,
        body,
        parsed,
        None,
        None,
        {
            "source_adapter_version": "catalog-pages-1",
            "content_coverage": "full_text" if parsed.status == "parsed" else "unknown",
            "published_at_raw": published,
            "published_precision": "unknown",
            "parser_notes": list(parsed.notes),
            "source_notes": [
                *parsed.notes[:18],
                f"解析器共记录{len(parsed.notes)}条提示；原始提示完整保存在修订元数据。",
                "自愿性风险框架原文；未据此生成强制义务或合规判断。",
            ],
        },
    )


def normalize_catalog_page(
    source_kind: SourceKind,
    body: bytes,
    cursor: dict[str, JsonValue],
    headers: Mapping[str, str] | None = None,
) -> CatalogPage:
    """目录blob分阶段处理；其他坏页整页失败，不推进游标或以空页降级。"""
    if source_kind == "arxiv_security":
        return _arxiv_page(body, cursor)
    if source_kind == "trailofbits_blog":
        build_catalog_request(source_kind, cursor)
        return _rss_page(body)
    if source_kind == "ollama_releases":
        return _release_page(body, cursor, headers or {})
    if source_kind == "osv_ollama":
        return _osv_page(body, cursor)
    build_catalog_request(source_kind, cursor)
    if source_kind == "nist_ai_rmf":
        return CatalogPage((_nist_document(body),), {})
    if source_kind == "cac_generative_ai":
        return CatalogPage((_policy_document(body),), {})
    raise SourceCatalogError("source requires its existing or blob-specific normalizer")
