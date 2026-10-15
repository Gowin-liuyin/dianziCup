"""真实 AVID 0.2 记录转社区文章；外部引用只保留元数据，不获取或执行。"""

from __future__ import annotations

import ipaddress
import re
from datetime import date
from urllib.parse import urlsplit

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.sources.repository import (
    CommunityArticle,
    RepositoryFetchError,
    normalize_community_article,
)

MAX_AVID_BYTES = 2 * 1024 * 1024
AVID_IDENTIFIER = re.compile(r"AVID-[0-9]{4}-V[0-9]{3,6}")
CVE_IDENTIFIER = re.compile(r"CVE-[0-9]{4}-[0-9]{4,}")
GHSA_IDENTIFIER = re.compile(r"GHSA-[23456789cfghjmpqrvwx]{4}(?:-[23456789cfghjmpqrvwx]{4}){2}")


def _description(value: object, field_name: str, *, required: bool) -> str | None:
    if value is None and not required:
        return None
    if not isinstance(value, dict):
        raise RepositoryFetchError(f"{field_name} must be a language/value object")
    language = value.get("lang")
    text = value.get("value")
    if not isinstance(language, str) or not language:
        raise RepositoryFetchError(f"{field_name}.lang must be nonempty text")
    if not isinstance(text, str) or (required and not text.strip()):
        raise RepositoryFetchError(f"{field_name}.value must be text")
    if field_name == "problemtype.description" and len(text) > 4096:
        raise RepositoryFetchError("AVID title exceeds text limit")
    return text


def _reference_identifier(value: object) -> str | None:
    if not isinstance(value, str) or len(value) > 4096:
        raise RepositoryFetchError("AVID reference URL must be bounded text")
    try:
        parts = urlsplit(value)
        host = parts.hostname or ""
        if (
            not value.isascii()
            or parts.scheme not in ("https", "http")
            or not host
            or parts.username is not None
            or parts.password is not None
            or parts.port not in (None, 80, 443)
            or any(ord(character) <= 32 or ord(character) == 127 for character in value)
            or "\\" in value
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
        ):
            raise ValueError("unsafe URL")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            address = None
        if address is not None and not address.is_global:
            raise ValueError("nonpublic literal address")
    except ValueError:
        raise RepositoryFetchError("AVID reference URL is not public HTTP metadata") from None
    if parts.query or parts.fragment:
        return None
    if host == "nvd.nist.gov" and parts.path.startswith("/vuln/detail/"):
        identifier = parts.path.removeprefix("/vuln/detail/")
        return identifier if CVE_IDENTIFIER.fullmatch(identifier) else None
    if host == "github.com" and parts.path.startswith("/advisories/"):
        identifier = parts.path.removeprefix("/advisories/")
        return identifier if GHSA_IDENTIFIER.fullmatch(identifier) else None
    if host == "avidml.org" and parts.path.startswith("/database/"):
        identifier = parts.path.removeprefix("/database/")
        return identifier if AVID_IDENTIFIER.fullmatch(identifier) else None
    return None


def normalize_avid_vulnerability(payload: bytes) -> CommunityArticle:
    """只接受已实测 AVID 0.2 正文；未知版本/目录/坏引用拒绝，原始字节由调用方保存。"""
    try:
        document = strict_json_object(payload, MAX_AVID_BYTES)
    except (ValueError, UnicodeError, RecursionError):
        raise RepositoryFetchError("invalid AVID JSON record") from None
    if document.get("data_type") != "AVID" or document.get("data_version") != "0.2":
        raise RepositoryFetchError("unsupported AVID record type or schema version")
    metadata = document.get("metadata")
    if not isinstance(metadata, dict):
        raise RepositoryFetchError("AVID metadata must be an object")
    identifier = metadata.get("vuln_id")
    if not isinstance(identifier, str) or not AVID_IDENTIFIER.fullmatch(identifier):
        raise RepositoryFetchError("AVID record lacks a stable vulnerability identifier")
    problem_type = document.get("problemtype")
    if not isinstance(problem_type, dict):
        raise RepositoryFetchError("AVID problemtype must be an object")
    title = _description(problem_type.get("description"), "problemtype.description", required=True)
    body = _description(document.get("description"), "description", required=False)
    for field in ("published_date", "last_modified_date"):
        value = document.get(field)
        if value is not None:
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise RepositoryFetchError(f"AVID {field} must be a date-only value")
            try:
                date.fromisoformat(value)
            except ValueError:
                raise RepositoryFetchError(f"AVID {field} is invalid") from None
    raw_references = document.get("references", [])
    if not isinstance(raw_references, list) or len(raw_references) > 128:
        raise RepositoryFetchError("AVID references must be a bounded array")
    references: list[str] = []
    for reference in raw_references:
        if not isinstance(reference, dict):
            raise RepositoryFetchError("AVID reference must be an object")
        for field in ("type", "label"):
            if not isinstance(reference.get(field), str):
                raise RepositoryFetchError(f"AVID reference {field} must be text")
        related_identifier = _reference_identifier(reference.get("url"))
        if related_identifier is not None and related_identifier not in references:
            references.append(related_identifier)
    return normalize_community_article(
        {
            "article_id": identifier,
            "title": title,
            "body": body,
            "referenced_advisory_ids": references,
        }
    )
