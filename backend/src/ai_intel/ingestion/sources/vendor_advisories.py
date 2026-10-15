"""Normalize published advisories from the approved vLLM repository."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime

APPROVED_REPOSITORY = "vllm-project/vllm"
VENDOR_SCHEMA_VERSION = "github-repository-advisory:1"
GHSA_PATTERN = re.compile(r"GHSA(?:-[23456789cfghjmpqrvwx]{4}){3}")
CVE_PATTERN = re.compile(r"CVE-[0-9]{4}-[0-9]{4,}")
TIMESTAMP_PATTERN = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])"
)
MAX_VULNERABILITIES = 256
MAX_VULNERABLE_FUNCTIONS = 256
MAX_TEXT_BYTES = 1_000_000


class VendorAdvisoryError(ValueError):
    """The external advisory cannot safely satisfy the source contract."""


@dataclass(frozen=True)
class VendorVulnerability:
    """Retain source conditions; patched_version may itself be a version range."""

    package_ecosystem: str | None
    package_name: str | None
    affected_range: str | None
    patched_version: str | None
    vulnerable_functions: tuple[str, ...] = ()


@dataclass(frozen=True)
class VendorAdvisory:
    """Stable vendor identity with optional CVE and unjudged package conditions."""

    ghsa_id: str
    cve_id: str | None
    title: str
    description: str | None
    published_at: str | None
    updated_at: str | None
    withdrawn_at: str | None
    canonical_uri: str
    product: str
    vulnerabilities: tuple[VendorVulnerability, ...]
    source_schema_version: str = VENDOR_SCHEMA_VERSION


def normalize_vendor_advisory(payload: dict[str, object], *, repository: str) -> VendorAdvisory:
    """Read one published repository advisory without fetching or evaluating it."""
    if repository != APPROVED_REPOSITORY:
        raise VendorAdvisoryError("unapproved vendor repository")
    ghsa_id = payload.get("ghsa_id")
    if not isinstance(ghsa_id, str) or GHSA_PATTERN.fullmatch(ghsa_id) is None:
        raise VendorAdvisoryError("invalid GHSA identifier")
    cve_id = payload.get("cve_id")
    if cve_id is not None and (
        not isinstance(cve_id, str) or CVE_PATTERN.fullmatch(cve_id) is None
    ):
        raise VendorAdvisoryError("invalid CVE identifier")
    canonical_uri = f"https://github.com/{repository}/security/advisories/{ghsa_id}"
    if payload.get("html_url") != canonical_uri:
        raise VendorAdvisoryError("advisory canonical URI does not match its repository and GHSA")
    if payload.get("state") != "published":
        raise VendorAdvisoryError("vendor advisory is not published")
    title = _text(payload.get("summary"), "summary", max_characters=10_000)
    if title is None:
        raise VendorAdvisoryError("advisory missing summary")
    description = _text(payload.get("description"), "description", max_characters=MAX_TEXT_BYTES)
    vulnerabilities = _vulnerabilities(payload.get("vulnerabilities"))
    total_text_bytes = len(title.encode("utf-8"))
    if description is not None:
        total_text_bytes += len(description.encode("utf-8"))
    for vulnerability in vulnerabilities:
        text_values = (
            vulnerability.package_ecosystem,
            vulnerability.package_name,
            vulnerability.affected_range,
            vulnerability.patched_version,
            *vulnerability.vulnerable_functions,
        )
        total_text_bytes += sum(len(value.encode("utf-8")) for value in text_values if value)
    if total_text_bytes > MAX_TEXT_BYTES:
        raise VendorAdvisoryError("vendor advisory exceeds text budget")
    return VendorAdvisory(
        ghsa_id=ghsa_id,
        cve_id=cve_id,
        title=title,
        description=description,
        published_at=_timestamp(payload.get("published_at")),
        updated_at=_timestamp(payload.get("updated_at")),
        withdrawn_at=_timestamp(payload.get("withdrawn_at")),
        canonical_uri=canonical_uri,
        product="vllm",
        vulnerabilities=vulnerabilities,
    )


def _text(value: object, field: str, *, max_characters: int = 10_000) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or not value.strip()
        or "\x00" in value
        or len(value) > max_characters
    ):
        raise VendorAdvisoryError(f"invalid vendor {field} text")
    try:
        value.encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise VendorAdvisoryError(f"invalid vendor {field} text") from error
    return value


def _timestamp(value: object) -> str | None:
    if value is None:
        return None
    if (
        not isinstance(value, str)
        or TIMESTAMP_PATTERN.fullmatch(value) is None
        or value.endswith("-00:00")
    ):
        raise VendorAdvisoryError("invalid vendor timestamp; explicit timezone required")
    try:
        timestamp = datetime.fromisoformat(value)
    except ValueError as error:
        raise VendorAdvisoryError("invalid vendor timestamp") from error
    return timestamp.astimezone(UTC).isoformat()


def _vulnerabilities(value: object) -> tuple[VendorVulnerability, ...]:
    if not isinstance(value, list) or len(value) > MAX_VULNERABILITIES:
        raise VendorAdvisoryError("invalid vendor vulnerabilities array")
    vulnerabilities: list[VendorVulnerability] = []
    for item in value:
        if not isinstance(item, dict):
            raise VendorAdvisoryError("invalid vendor vulnerability object")
        package = item.get("package")
        if package is None:
            package = {}
        if not isinstance(package, dict):
            raise VendorAdvisoryError("invalid vendor vulnerability package")
        functions = item.get("vulnerable_functions")
        if functions is None:
            functions = []
        if not isinstance(functions, list) or len(functions) > MAX_VULNERABLE_FUNCTIONS:
            raise VendorAdvisoryError("invalid vendor vulnerability functions")
        function_names: list[str] = []
        for function in functions:
            name = _text(function, "vulnerable function", max_characters=1_000)
            if name is None:
                raise VendorAdvisoryError("missing vendor vulnerable function name")
            function_names.append(name)
        vulnerabilities.append(
            VendorVulnerability(
                package_ecosystem=_optional_package_text(
                    package.get("ecosystem"), "package ecosystem"
                ),
                package_name=_optional_package_text(package.get("name"), "package name"),
                affected_range=_text(item.get("vulnerable_version_range"), "affected range"),
                patched_version=_text(item.get("patched_versions"), "patched versions"),
                vulnerable_functions=tuple(function_names),
            )
        )
    return tuple(vulnerabilities)


def _optional_package_text(value: object, field: str) -> str | None:
    """GitHub 允许未知 package 字段为空；保留原文，不从仓库名称补造归属。"""
    if isinstance(value, str) and len(value) <= 10_000 and not value.strip():
        return None
    return _text(value, field)
