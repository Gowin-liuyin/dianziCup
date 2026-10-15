"""Closed publisher plans and bounded selection archives; no network or publication is performed."""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from xml.etree import ElementTree

from ai_intel.domain.enrichment_values import EpssSignalValue, KevSignalValue
from ai_intel.domain.enums import DocumentKind
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.catalog_documents import NormalizedSourceDocument
from ai_intel.ingestion.parsing.parsers import parse_json_document

PublicSignal = Literal["epss", "kev"]
CVE_PATTERN = re.compile(r"CVE-[0-9]{4}-[0-9]{4,19}")
CWE_PATTERN = re.compile(r"CWE-[1-9][0-9]{0,5}")
KEV_URI = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"
CWE_URI = "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip"
MAX_SIGNAL_BYTES = 8 * 1024 * 1024
MAX_CWE_XML_BYTES = 32 * 1024 * 1024
CWE_LICENSE_URI = "https://cwe.mitre.org/about/termsofuse.html"


class PublicSignalError(ValueError):
    """Fixed safe reason codes identify source failures without leaking response bodies."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True)
class PublicSignalRequest:
    signal: PublicSignal
    url: str
    allowed_domains: tuple[str, ...]
    max_response_bytes: int
    allowed_content_types: tuple[str, ...] = ("application/json",)
    timeout_seconds: float = 12.0
    method: Literal["GET"] = "GET"
    max_redirect_hops: int = 0


def require_cve_id(value: str) -> str:
    if not isinstance(value, str) or CVE_PATTERN.fullmatch(value) is None:
        raise PublicSignalError("invalid_cve_id")
    return value


def build_public_signal_request(signal: PublicSignal, cve_id: str) -> PublicSignalRequest:
    """Each EPSS request is a single exact CVE lookup; KEV always uses its fixed full catalog."""
    require_cve_id(cve_id)
    if signal == "epss":
        return PublicSignalRequest(
            signal,
            f"https://api.first.org/data/v1/epss?cve={cve_id}",
            ("api.first.org",),
            256 * 1024,
        )
    if signal == "kev":
        return PublicSignalRequest(signal, KEV_URI, ("www.cisa.gov",), MAX_SIGNAL_BYTES)
    raise PublicSignalError("unsupported_public_signal")


def _text(value: object, limit: int, code: str) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > limit:
        raise PublicSignalError(code)
    return value


def _date(value: object) -> date:
    if not isinstance(value, str) or re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value) is None:
        raise PublicSignalError("invalid_signal_date")
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise PublicSignalError("invalid_signal_date") from None


def _probability(value: object) -> float:
    if (
        isinstance(value, bool)
        or not isinstance(value, (str, float, int))
        or (
            isinstance(value, str)
            and (len(value) > 32 or re.fullmatch(r"(?:0|1)(?:\.[0-9]+)?", value) is None)
        )
    ):
        raise PublicSignalError("invalid_signal_probability")
    number = float(value)
    if not 0 <= number <= 1:
        raise PublicSignalError("invalid_signal_probability")
    return number


def epss_value(entry: dict[str, object]) -> EpssSignalValue:
    """FIRST API version is deliberately absent from the model_version field."""
    try:
        return EpssSignalValue(
            cve_id=require_cve_id(_text(entry.get("cve"), 28, "invalid_cve_id")),
            probability=_probability(entry.get("epss")),
            percentile=_probability(entry.get("percentile")),
            data_date=_date(entry.get("date")),
            model_version=None,
        )
    except ValueError:
        raise PublicSignalError("invalid_epss_record") from None


def kev_value(entry: dict[str, object], catalog_version: str) -> KevSignalValue:
    try:
        ransomware = entry.get("knownRansomwareCampaignUse", "Unknown")
        if not isinstance(ransomware, str) or ransomware not in {"Known", "Unknown"}:
            raise PublicSignalError("invalid_ransomware_status")
        due = entry.get("dueDate")
        return KevSignalValue(
            cve_id=require_cve_id(_text(entry.get("cveID"), 28, "invalid_cve_id")),
            catalog_version=catalog_version,
            date_added=_date(entry.get("dateAdded")),
            required_action=_text(entry.get("requiredAction"), 2000, "invalid_required_action"),
            due_date=_date(due) if due is not None else None,
            ransomware_use="known" if ransomware == "Known" else "unknown",
        )
    except ValueError:
        raise PublicSignalError("invalid_kev_record") from None


def _json(raw: bytes) -> dict[str, object]:
    try:
        return strict_json_object(raw, MAX_SIGNAL_BYTES, maximum_nodes=50000)
    except (ValueError, UnicodeError, RecursionError):
        raise PublicSignalError("invalid_signal_json") from None


def _catalog_release(value: object) -> datetime:
    text = _text(value, 40, "invalid_catalog_release")
    if re.fullmatch(
        r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
        r"(?:\.[0-9]{1,6})?(?:Z|[+-](?:[01][0-9]|2[0-3]):[0-5][0-9])",
        text,
    ) is None or text.endswith("-00:00"):
        raise PublicSignalError("invalid_catalog_release")
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        raise PublicSignalError("invalid_catalog_release") from None


def _validated_wire(
    signal: PublicSignal, payload: dict[str, object], cve_id: str
) -> tuple[list[dict[str, object]], str]:
    if signal == "epss":
        data, limit = payload.get("data"), payload.get("limit")
        if (
            payload.get("status") != "OK"
            or type(payload.get("status-code")) is not int
            or payload.get("status-code") != 200
            or payload.get("version") != "1.0"
            or type(payload.get("offset")) is not int
            or payload.get("offset") != 0
            or type(payload.get("total")) is not int
            or not isinstance(data, list)
            or payload.get("total") != len(data)
            or len(data) > 1
            or not isinstance(limit, int)
            or isinstance(limit, bool)
            or limit < len(data)
        ):
            raise PublicSignalError("incomplete_epss_lookup")
        if any(not isinstance(row, dict) or epss_value(row).cve_id != cve_id for row in data):
            raise PublicSignalError("cross_cve_epss_lookup")
        return data, "1.0"
    if signal != "kev":
        raise PublicSignalError("unsupported_public_signal")
    version = _text(payload.get("catalogVersion"), 200, "missing_catalog_version")
    _catalog_release(payload.get("dateReleased"))
    data = payload.get("vulnerabilities")
    if (
        type(payload.get("count")) is not int
        or not isinstance(data, list)
        or payload.get("count") != len(data)
        or len(data) > 10000
    ):
        raise PublicSignalError("incomplete_kev_catalog")
    identifiers: set[str] = set()
    for row in data:
        if not isinstance(row, dict):
            raise PublicSignalError("invalid_kev_record")
        value = kev_value(row, version)
        if value.cve_id in identifiers:
            raise PublicSignalError("duplicate_kev_cve")
        identifiers.add(value.cve_id)
    return data, version


def _normalized(
    payload: dict[str, object], record_id: str, uri: str, title: str, kind: DocumentKind
) -> NormalizedSourceDocument:
    body = json.dumps(payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()
    parsed = parse_json_document(body)
    if parsed.status != "parsed" or len(parsed.blocks) > 200:
        raise PublicSignalError("signal_selection_outside_block_limit")
    return NormalizedSourceDocument(
        source_record_id=record_id,
        kind=kind,
        title=title,
        canonical_uri=uri,
        payload=body,
        parsed=parsed,
        published_at=None,
        modified_at=None,
        metadata={
            "content_coverage": "metadata_only",
            "source_adapter_version": "public-signal-1",
            "source_response_sha256": str(payload["selection"]["source_response_sha256"])
            if isinstance(payload["selection"], dict)
            else "",
        },
    )


def select_public_signal_document(
    signal: PublicSignal, raw: bytes, cve_id: str
) -> NormalizedSourceDocument:
    """Validate the full response before archiving one selected record and its lookup scope."""
    require_cve_id(cve_id)
    request = build_public_signal_request(signal, cve_id)
    if len(raw) > request.max_response_bytes:
        raise PublicSignalError("signal_response_outside_limit")
    payload = _json(raw)
    rows, version = _validated_wire(signal, payload, cve_id)
    cve_field, rows_field = ("cve", "data") if signal == "epss" else ("cveID", "vulnerabilities")
    selected = [(index, row) for index, row in enumerate(rows) if row[cve_field] == cve_id]
    if signal == "epss":
        response: dict[str, object] = {
            "status": payload["status"],
            "status-code": payload["status-code"],
            "version": version,
            "data": [row for _, row in selected],
        }
    else:
        response = {
            "catalogVersion": version,
            "dateReleased": payload["dateReleased"],
            rows_field: [row for _, row in selected],
        }
    archive: dict[str, object] = {
        "schema_version": "public-signal-selection-1",
        "signal": signal,
        "selection": {
            "requested_cve_id": cve_id,
            "source_response_sha256": hashlib.sha256(raw).hexdigest(),
            "source_total_count": len(rows),
            "source_record_index": selected[0][0] if selected else None,
            "complete_response": True,
            "query_scope": "single_cve" if signal == "epss" else "complete_catalog",
        },
        "response": response,
    }
    return _normalized(
        archive,
        f"public-signal:{signal}:{cve_id}",
        request.url,
        f"{signal.upper()} · {cve_id}",
        DocumentKind.ADVISORY,
    )


def validate_selected_signal(
    signal: PublicSignal, payload: dict[str, object], cve_id: str
) -> tuple[dict[str, object] | None, str]:
    """The final publisher must also check selection hashes against its stored raw response."""
    selection, response = payload.get("selection"), payload.get("response")
    if (
        payload.get("schema_version") != "public-signal-selection-1"
        or payload.get("signal") != signal
        or not isinstance(selection, dict)
        or not isinstance(response, dict)
        or selection.get("requested_cve_id") != cve_id
        or selection.get("complete_response") is not True
        or selection.get("query_scope")
        != ("single_cve" if signal == "epss" else "complete_catalog")
        or not isinstance(selection.get("source_response_sha256"), str)
        or re.fullmatch(r"[0-9a-f]{64}", selection["source_response_sha256"]) is None
        or type(selection.get("source_total_count")) is not int
        or not 0 <= selection["source_total_count"] <= 10000
    ):
        raise PublicSignalError("invalid_signal_selection")
    rows = response.get("data" if signal == "epss" else "vulnerabilities")
    if not isinstance(rows, list) or len(rows) > 1:
        raise PublicSignalError("invalid_signal_selection")
    index = selection.get("source_record_index")
    if rows and (type(index) is not int or not 0 <= index < selection["source_total_count"]):
        raise PublicSignalError("invalid_signal_selection")
    if not rows and index is not None:
        raise PublicSignalError("invalid_signal_selection")
    if signal == "epss":
        if (
            response.get("status") != "OK"
            or type(response.get("status-code")) is not int
            or response.get("status-code") != 200
            or response.get("version") != "1.0"
            or selection["source_total_count"] != len(rows)
        ):
            raise PublicSignalError("invalid_epss_selection")
        version = "1.0"
    else:
        version = _text(response.get("catalogVersion"), 200, "missing_catalog_version")
        _catalog_release(response.get("dateReleased"))
    if not rows:
        return None, version
    row = rows[0]
    if not isinstance(row, dict):
        raise PublicSignalError("invalid_signal_record")
    value = epss_value(row) if signal == "epss" else kev_value(row, version)
    if value.cve_id != cve_id:
        raise PublicSignalError("cross_cve_signal_selection")
    return row, version


def select_cwe_catalog_document(raw: bytes, cwe_ids: tuple[str, ...]) -> NormalizedSourceDocument:
    """Read bounded official XML/ZIP in memory and explicitly archive selected weaknesses."""
    if (
        not 1 <= len(raw) <= MAX_SIGNAL_BYTES
        or not 1 <= len(cwe_ids) <= 20
        or len(set(cwe_ids)) != len(cwe_ids)
        or any(
            not isinstance(value, str) or CWE_PATTERN.fullmatch(value) is None for value in cwe_ids
        )
    ):
        raise PublicSignalError("invalid_cwe_catalog_input")
    xml = raw
    if raw.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.infolist()
                if len(members) != 1:
                    raise PublicSignalError("invalid_cwe_archive")
                member = members[0]
                if (
                    re.fullmatch(r"cwec[_a-zA-Z0-9.\-]*\.xml", member.filename) is None
                    or member.flag_bits & 1
                    or not 1 <= member.file_size <= MAX_CWE_XML_BYTES
                    or member.file_size > max(1, member.compress_size) * 200
                ):
                    raise PublicSignalError("invalid_cwe_archive")
                with archive.open(member) as stream:
                    xml = stream.read(MAX_CWE_XML_BYTES + 1)
        except (zipfile.BadZipFile, RuntimeError, OSError):
            raise PublicSignalError("invalid_cwe_archive") from None
    if len(xml) > MAX_CWE_XML_BYTES:
        raise PublicSignalError("cwe_xml_outside_limit")
    try:
        text = xml.decode("utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", text, re.IGNORECASE):
            raise PublicSignalError("unsafe_cwe_xml")
        depth, nodes = 0, 0
        root: ElementTree.Element | None = None
        parser = ElementTree.iterparse(io.StringIO(text), events=("start", "end"))
        for event, element in parser:
            if root is None:
                root = element
            depth += 1 if event == "start" else -1
            nodes += event == "start"
            if depth > 64 or nodes > 250000:
                raise PublicSignalError("cwe_xml_structure_outside_limit")
    except (UnicodeError, ElementTree.ParseError):
        raise PublicSignalError("invalid_cwe_xml") from None
    namespace = "{http://cwe.mitre.org/cwe-7}"
    if root is None or root.tag != namespace + "Weakness_Catalog":
        raise PublicSignalError("invalid_cwe_catalog_root")
    version = root.get("Version", "")
    if re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}", version) is None:
        raise PublicSignalError("missing_cwe_catalog_version")
    entries = root.findall(f"{namespace}Weaknesses/{namespace}Weakness")
    if not 1 <= len(entries) <= 5000:
        raise PublicSignalError("invalid_cwe_catalog_count")
    names: dict[str, str] = {}
    for entry in entries:
        cwe_id = "CWE-" + entry.get("ID", "")
        name = entry.get("Name", "")
        if CWE_PATTERN.fullmatch(cwe_id) is None or cwe_id in names:
            raise PublicSignalError("invalid_cwe_catalog_id")
        names[cwe_id] = _text(name, 200, "invalid_cwe_catalog_name")
    selection: dict[str, object] = {
        "schema_version": "cwe-selection-1",
        "taxonomy_version": version,
        "selection": {
            "source_response_sha256": hashlib.sha256(raw).hexdigest(),
            "source_xml_sha256": hashlib.sha256(xml).hexdigest(),
            "total_weaknesses": len(names),
            "requested_cwe_ids": list(cwe_ids),
            "complete_catalog": True,
        },
        "weaknesses": [
            {
                "cwe_id": key,
                "name": names[key],
                "source_locator": f"/Weakness_Catalog/Weaknesses/Weakness[@ID='{key[4:]}']",
            }
            for key in cwe_ids
            if key in names
        ],
        "missing_cwe_ids": [key for key in cwe_ids if key not in names],
        "copyright": "Copyright © 2006–2026, The MITRE Corporation.",
        "license_uri": CWE_LICENSE_URI,
        "license": (
            "CWE™ is free to use by any organization or individual for any research, development, "
            "and/or commercial purposes, per these CWE Terms of Use. Accordingly, The MITRE "
            "Corporation hereby grants you a non-exclusive, royalty-free license to use CWE for "
            "research, development, and commercial purposes. Any copy you make for such purposes "
            "is authorized on the condition that you reproduce MITRE’s copyright designation and "
            "this license in any such copy. CWE is a trademark of The MITRE Corporation."
        ),
    }
    return _normalized(
        selection,
        f"cwe:{version}:" + ",".join(cwe_ids),
        CWE_URI,
        f"CWE {version} · selected weaknesses",
        DocumentKind.STANDARD,
    )
