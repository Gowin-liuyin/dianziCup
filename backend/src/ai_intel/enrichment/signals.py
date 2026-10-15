"""Extract four public signals with exact immutable field evidence and independent failures."""

from __future__ import annotations

import hashlib
import json
import re
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Literal
from urllib.parse import parse_qsl, urlsplit
from uuid import UUID

from ai_intel.domain.enrichment_values import (
    CvssSignalValue,
    EpssSignalValue,
    KevSignalValue,
    WeaknessValue,
)
from ai_intel.domain.enums import (
    ClaimOrigin,
    DimensionStatus,
    DocumentKind,
    SourceCategory,
)
from ai_intel.enrichment.contracts import (
    CandidateEvidence,
    DimensionAttempt,
    EnrichmentContext,
    EnrichmentDocument,
    EvidenceBoundCandidate,
)
from ai_intel.enrichment.signal_sources import (
    CWE_LICENSE_URI,
    CWE_PATTERN,
    CWE_URI,
    KEV_URI,
    PublicSignalError,
    epss_value,
    kev_value,
    validate_selected_signal,
)
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.sources.nvd import normalize_nvd_record
from ai_intel.ingestion.sources.vendor_advisories import (
    APPROVED_REPOSITORY,
    normalize_vendor_advisory,
)

SignalDimension = Literal["cvss", "epss", "kev", "cwe"]
StandardVersion = Literal["2.0", "3.0", "3.1", "4.0"]
PUBLIC_DIMENSIONS: tuple[SignalDimension, ...] = ("cvss", "epss", "kev", "cwe")


def _standard_version(value: str) -> StandardVersion:
    if value == "2.0":
        return "2.0"
    if value == "3.0":
        return "3.0"
    if value == "3.1":
        return "3.1"
    if value == "4.0":
        return "4.0"
    raise PublicSignalError("unsupported_cvss_standard_version")


@dataclass
class _CollectedDimension:
    candidates: list[EvidenceBoundCandidate] = field(default_factory=list)
    documents: list[EnrichmentDocument] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    missing: bool = True
    cvss_targets: dict[UUID, str] = field(default_factory=dict)


def _payload(document: EnrichmentDocument) -> dict[str, object]:
    if document.json_payload is None:
        raise PublicSignalError("structured_payload_missing")
    try:
        return strict_json_object(document.json_payload, 2 * 1024 * 1024, maximum_nodes=50000)
    except (ValueError, UnicodeError, RecursionError):
        raise PublicSignalError("invalid_structured_payload") from None


def _field_evidence(document: EnrichmentDocument, pointer: str, value: object) -> CandidateEvidence:
    """The canonical JSON leaf representation and its pointer must both identify one block."""
    text = (
        value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, allow_nan=False)
    )
    blocks = [block for block in document.blocks if block.json_pointer == pointer]
    prefix = pointer + ": "
    if len(blocks) != 1 or blocks[0].text != prefix + text or not text or len(text) > 2000:
        raise PublicSignalError("structured_evidence_mismatch")
    block = blocks[0]
    return CandidateEvidence(
        revision_id=document.revision_id,
        block_id=block.block_id,
        start_offset=len(prefix),
        end_offset=len(prefix) + len(text),
        quote_text=text,
        quote_sha256=hashlib.sha256(text.encode()).hexdigest(),
    )


def _evidence(
    document: EnrichmentDocument, fields: tuple[tuple[str, object], ...]
) -> tuple[CandidateEvidence, ...]:
    return tuple(_field_evidence(document, pointer, value) for pointer, value in fields)


def _publisher(document: EnrichmentDocument) -> str | None:
    uri = urlsplit(str(document.canonical_uri))
    if uri.scheme != "https" or uri.username or uri.password or uri.port not in {None, 443}:
        return None
    if (
        uri.hostname == "nvd.nist.gov"
        and uri.path.startswith("/vuln/detail/")
        and not uri.query
        and not uri.fragment
        and document.source_category == SourceCategory.STRUCTURED_VULNERABILITY
    ):
        return "nvd"
    if (
        uri.hostname == "github.com"
        and uri.path.startswith(f"/{APPROVED_REPOSITORY}/security/advisories/")
        and not uri.query
        and not uri.fragment
        and document.source_category == SourceCategory.VENDOR_ADVISORY
    ):
        return "vendor"
    if (
        uri.hostname == "api.first.org"
        and uri.path == "/data/v1/epss"
        and not uri.fragment
        and document.source_category == SourceCategory.STRUCTURED_VULNERABILITY
        and len(parse_qsl(uri.query, keep_blank_values=True)) == 1
        and parse_qsl(uri.query, keep_blank_values=True)[0][0] == "cve"
    ):
        return "epss"
    if str(document.canonical_uri) == KEV_URI and (
        document.source_category == SourceCategory.STRUCTURED_VULNERABILITY
    ):
        return "kev"
    if str(document.canonical_uri) == CWE_URI and (
        document.source_category == SourceCategory.TECHNICAL_STANDARD
        and document.document_kind == DocumentKind.STANDARD
    ):
        return "cwe"
    return None


def _validate_vector(version: str, vector: str) -> None:
    prefix = f"CVSS:{version}/"
    body = vector.removeprefix(prefix)
    if version != "2.0" and not vector.startswith(prefix):
        raise PublicSignalError("cvss_vector_version_mismatch")
    if version == "2.0" and vector.startswith("CVSS:") and not vector.startswith(prefix):
        raise PublicSignalError("cvss_vector_version_mismatch")
    tokens = body.split("/")
    keys = [part.split(":")[0] for part in tokens]
    required = {
        "2.0": {"AV", "AC", "Au", "C", "I", "A"},
        "3.0": {"AV", "AC", "PR", "UI", "S", "C", "I", "A"},
        "3.1": {"AV", "AC", "PR", "UI", "S", "C", "I", "A"},
        "4.0": {"AV", "AC", "AT", "PR", "UI", "VC", "VI", "VA", "SC", "SI", "SA"},
    }
    if (
        version not in required
        or len(keys) != len(set(keys))
        or not required[version] <= set(keys)
        or any(re.fullmatch(r"[A-Za-z]+:[A-Za-z0-9.]+", token) is None for token in tokens)
    ):
        raise PublicSignalError("invalid_cvss_vector")
    base_values = {
        "2.0": {"AV": "LAN", "AC": "HML", "Au": "MSN", "C": "NPC", "I": "NPC", "A": "NPC"},
        "3.0": {
            "AV": "NALP",
            "AC": "LH",
            "PR": "NLH",
            "UI": "NR",
            "S": "UC",
            "C": "HLN",
            "I": "HLN",
            "A": "HLN",
        },
        "3.1": {
            "AV": "NALP",
            "AC": "LH",
            "PR": "NLH",
            "UI": "NR",
            "S": "UC",
            "C": "HLN",
            "I": "HLN",
            "A": "HLN",
        },
        "4.0": {
            "AV": "NALP",
            "AC": "LH",
            "AT": "NP",
            "PR": "NLH",
            "UI": "NPA",
            "VC": "HLN",
            "VI": "HLN",
            "VA": "HLN",
            "SC": "HLN",
            "SI": "HLN",
            "SA": "HLN",
        },
    }
    pairs = dict(token.split(":") for token in tokens)
    if any(
        len(pairs[key]) != 1 or pairs[key] not in choices
        for key, choices in base_values[version].items()
    ):
        raise PublicSignalError("invalid_cvss_base_metric")


def _nvd_cvss(
    context: EnrichmentContext, document: EnrichmentDocument, payload: dict[str, object]
) -> tuple[EvidenceBoundCandidate, ...]:
    record = normalize_nvd_record(payload)
    if record.cve_id not in context.external_cve_ids or str(document.canonical_uri) != (
        f"https://nvd.nist.gov/vuln/detail/{record.cve_id}"
    ):
        raise PublicSignalError("cross_cve_nvd_document")
    result: list[EvidenceBoundCandidate] = []
    for metric in record.metrics:
        if metric.authority is None or metric.version is None or metric.vector is None:
            raise PublicSignalError("cvss_qualifier_missing")
        _validate_vector(metric.version, metric.vector)
        if (
            metric.version
            != {
                "cvssMetricV2": "2.0",
                "cvssMetricV30": "3.0",
                "cvssMetricV31": "3.1",
                "cvssMetricV40": "4.0",
            }[metric.metric_name]
        ):
            raise PublicSignalError("cvss_metric_version_mismatch")
        metric_pointer = metric.json_pointer.removesuffix("/cvssData/baseScore")
        raw_cve = payload["cve"]
        if not isinstance(raw_cve, dict) or not isinstance(raw_cve.get("metrics"), dict):
            raise PublicSignalError("invalid_cvss_record")
        rows = raw_cve["metrics"][metric.metric_name]
        if not isinstance(rows, list):
            raise PublicSignalError("invalid_cvss_record")
        index = int(metric_pointer.rsplit("/", 1)[1])
        row = rows[index]
        if not isinstance(row, dict) or not isinstance(row.get("cvssData"), dict):
            raise PublicSignalError("invalid_cvss_record")
        score = row["cvssData"]["baseScore"]
        result.append(
            EvidenceBoundCandidate(
                dimension="cvss",
                value=CvssSignalValue(
                    standard_version=_standard_version(metric.version),
                    base_score=metric.score,
                    vector=metric.vector,
                    authority=metric.authority,
                    scored_at=None,
                ),
                evidence=_evidence(
                    document,
                    (
                        ("/cve/id", record.cve_id),
                        (metric_pointer + "/source", metric.authority),
                        (metric_pointer + "/cvssData/version", metric.version),
                        (metric_pointer + "/cvssData/vectorString", metric.vector),
                        (metric_pointer + "/cvssData/baseScore", score),
                    ),
                ),
                origin=ClaimOrigin.STRUCTURED_SOURCE,
                limitations=(
                    "Source-reported score and vector; not independently recomputed.",
                    "Scoring time is unknown; publication and modification times are distinct.",
                ),
            )
        )
    return tuple(result)


def _vendor_cvss(
    document: EnrichmentDocument, payload: dict[str, object]
) -> tuple[EvidenceBoundCandidate, ...]:
    metric = payload.get("cvss")
    if metric is None:
        return ()
    if not isinstance(metric, dict):
        raise PublicSignalError("invalid_vendor_cvss")
    score, vector = metric.get("score"), metric.get("vector_string")
    if score is None and vector is None:
        return ()
    publisher = payload.get("publisher")
    if not isinstance(publisher, dict) or not isinstance(publisher.get("login"), str):
        raise PublicSignalError("cvss_authority_missing")
    if (
        not isinstance(score, (int, float))
        or isinstance(score, bool)
        or not isinstance(vector, str)
    ):
        raise PublicSignalError("invalid_vendor_cvss")
    match = re.match(r"CVSS:(2\.0|3\.0|3\.1|4\.0)/", vector)
    if match is None:
        raise PublicSignalError("cvss_standard_version_missing")
    version = _standard_version(match.group(1))
    _validate_vector(version, vector)
    value = CvssSignalValue(
        standard_version=version,
        base_score=float(score),
        vector=vector,
        authority=publisher["login"],
        scored_at=None,
    )
    fields: list[tuple[str, object]] = [
        ("/cvss/score", score),
        ("/cvss/vector_string", vector),
        ("/publisher/login", publisher["login"]),
        ("/ghsa_id", payload["ghsa_id"]),
    ]
    if payload.get("cve_id") is not None:
        fields.append(("/cve_id", payload["cve_id"]))
    return (
        EvidenceBoundCandidate(
            dimension="cvss",
            value=value,
            evidence=_evidence(document, tuple(fields)),
            origin=ClaimOrigin.STRUCTURED_SOURCE,
            limitations=(
                "Source-reported score and vector; not independently recomputed.",
                "Scoring time is unknown; repository publisher identity is preserved.",
            ),
        ),
    )


def _weakness_fields(payload: dict[str, object], publisher: str) -> tuple[tuple[str, str], ...]:
    result: list[tuple[str, str]] = []
    unknown = False
    if publisher == "nvd":
        cve = payload.get("cve")
        if not isinstance(cve, dict):
            raise PublicSignalError("invalid_cwe_source")
        entries = cve.get("weaknesses", [])
        if not isinstance(entries, list):
            raise PublicSignalError("invalid_cwe_source")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("description"), list):
                raise PublicSignalError("invalid_cwe_source")
            for ordinal, description in enumerate(entry["description"]):
                if not isinstance(description, dict) or not isinstance(
                    description.get("value"), str
                ):
                    raise PublicSignalError("invalid_cwe_source")
                if description["value"] in {"NVD-CWE-noinfo", "NVD-CWE-Other"}:
                    unknown = True
                    continue
                result.append(
                    (f"/cve/weaknesses/{index}/description/{ordinal}/value", description["value"])
                )
    else:
        entries = payload.get("cwes", [])
        if not isinstance(entries, list):
            raise PublicSignalError("invalid_cwe_source")
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict) or not isinstance(entry.get("cwe_id"), str):
                raise PublicSignalError("invalid_cwe_source")
            result.append((f"/cwes/{index}/cwe_id", entry["cwe_id"]))
    if len(result) > 100 or any(
        CWE_PATTERN.fullmatch(identifier) is None for _, identifier in result
    ):
        raise PublicSignalError("invalid_cwe_source")
    if unknown and not result:
        raise PublicSignalError("cwe_source_unknown")
    return tuple(result)


def _cwe_catalog(
    document: EnrichmentDocument,
) -> tuple[str, str, dict[str, tuple[str, int]]]:
    payload = _payload(document)
    version, selection, entries = (
        payload.get("taxonomy_version"),
        payload.get("selection"),
        payload.get("weaknesses"),
    )
    if (
        payload.get("schema_version") != "cwe-selection-1"
        or not isinstance(version, str)
        or re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}", version) is None
        or document.source_version != version
        or not isinstance(selection, dict)
        or selection.get("complete_catalog") is not True
        or type(selection.get("total_weaknesses")) is not int
        or not 1 <= selection["total_weaknesses"] <= 5000
        or not isinstance(entries, list)
        or len(entries) > 20
        or payload.get("license_uri") != CWE_LICENSE_URI
    ):
        raise PublicSignalError("invalid_cwe_selection")
    for key in ("source_response_sha256", "source_xml_sha256"):
        if (
            not isinstance(selection.get(key), str)
            or re.fullmatch(r"[0-9a-f]{64}", selection[key]) is None
        ):
            raise PublicSignalError("invalid_cwe_selection")
    requested = selection.get("requested_cwe_ids")
    missing = payload.get("missing_cwe_ids")
    if (
        not isinstance(requested, list)
        or not 1 <= len(requested) <= 20
        or any(
            not isinstance(value, str) or CWE_PATTERN.fullmatch(value) is None
            for value in requested
        )
        or len(set(requested)) != len(requested)
        or not isinstance(missing, list)
        or any(not isinstance(value, str) or value not in requested for value in missing)
    ):
        raise PublicSignalError("invalid_cwe_selection")
    names: dict[str, tuple[str, int]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise PublicSignalError("invalid_cwe_selection")
        identifier, name = entry.get("cwe_id"), entry.get("name")
        if (
            not isinstance(identifier, str)
            or identifier not in requested
            or identifier in names
            or not isinstance(name, str)
            or not 1 <= len(name) <= 200
            or not name.strip()
        ):
            raise PublicSignalError("invalid_cwe_selection")
        names[identifier] = name, index
    if set(names) & set(missing) or set(names) | set(missing) != set(requested):
        raise PublicSignalError("invalid_cwe_selection")
    return version, selection["source_xml_sha256"], names


def _cwe_candidates(
    document: EnrichmentDocument,
    payload: dict[str, object],
    publisher: str,
    catalogs: tuple[EnrichmentDocument, ...],
) -> tuple[EvidenceBoundCandidate, ...]:
    fields = _weakness_fields(payload, publisher)
    if not fields:
        return ()
    if not catalogs:
        raise PublicSignalError("cwe_catalog_missing")
    selections: dict[
        tuple[str, str], list[tuple[EnrichmentDocument, dict[str, tuple[str, int]]]]
    ] = defaultdict(list)
    for catalog in catalogs:
        version, xml_hash, names = _cwe_catalog(catalog)
        selections[(version, xml_hash)].append((catalog, names))
    requested_ids = {identifier for _, identifier in fields}
    result: list[EvidenceBoundCandidate] = []
    for (version, _), selected_catalogs in selections.items():
        verified_ids = {identifier for _, names in selected_catalogs for identifier in names}
        if not requested_ids <= verified_ids:
            continue
        for catalog, names in selected_catalogs:
            for pointer, identifier in fields:
                if identifier not in names:
                    continue
                name, index = names[identifier]
                catalog_evidence = _evidence(
                    catalog,
                    (
                        ("/taxonomy_version", version),
                        (f"/weaknesses/{index}/cwe_id", identifier),
                        (f"/weaknesses/{index}/name", name),
                    ),
                )
                result.append(
                    EvidenceBoundCandidate(
                        dimension="cwe",
                        value=WeaknessValue(cwe_id=identifier, taxonomy_version=version, name=name),
                        evidence=(
                            _field_evidence(document, pointer, identifier),
                            *catalog_evidence,
                        ),
                        origin=ClaimOrigin.STRUCTURED_SOURCE,
                        limitations=(
                            "Taxonomy identity is verified separately from event applicability.",
                        ),
                    )
                )
    if not result:
        raise PublicSignalError("cwe_identifier_not_verified")
    return tuple(result)


def _public_signal_candidates(
    context: EnrichmentContext, document: EnrichmentDocument, signal: Literal["epss", "kev"]
) -> tuple[EvidenceBoundCandidate, ...]:
    payload = _payload(document)
    selection = payload.get("selection")
    if (
        not isinstance(selection, dict)
        or selection.get("requested_cve_id") not in context.external_cve_ids
    ):
        raise PublicSignalError("unsupported_signal_cve")
    cve = selection["requested_cve_id"]
    if not isinstance(cve, str):
        raise PublicSignalError("unsupported_signal_cve")
    if signal == "epss" and parse_qsl(urlsplit(str(document.canonical_uri)).query) != [
        ("cve", cve)
    ]:
        raise PublicSignalError("cross_cve_epss_uri")
    row, version = validate_selected_signal(signal, payload, cve)
    if row is None:
        return ()
    if signal == "epss":
        value: EpssSignalValue | KevSignalValue = epss_value(row)
        fields = tuple(
            (f"/response/data/0/{key}", row[key]) for key in ("cve", "epss", "percentile", "date")
        )
    else:
        value = kev_value(row, version)
        fields = (
            ("/response/catalogVersion", version),
            *tuple(
                (f"/response/vulnerabilities/0/{key}", row[key])
                for key in (
                    "cveID",
                    "dateAdded",
                    "requiredAction",
                    "dueDate",
                    "knownRansomwareCampaignUse",
                )
                if key in row and row[key] is not None
            ),
        )
    return (
        EvidenceBoundCandidate(
            dimension=signal,
            value=value,
            evidence=_evidence(document, fields),
            origin=ClaimOrigin.STRUCTURED_SOURCE,
            limitations=("Public exploitation signals do not establish compromise of any asset.",),
        ),
    )


def _scope(candidate: EvidenceBoundCandidate, cvss_targets: dict[UUID, str]) -> tuple[str, ...]:
    value = candidate.value
    if isinstance(value, CvssSignalValue):
        target = cvss_targets[candidate.evidence[0].revision_id]
        return ("cvss", target, value.standard_version)
    if value.kind == "epss_signal":
        return ("epss", value.cve_id, str(value.data_date), str(value.model_version))
    if value.kind == "kev_signal":
        return ("kev", value.cve_id, value.catalog_version)
    if isinstance(value, WeaknessValue):
        return ("cwe", value.cwe_id, value.taxonomy_version)
    raise PublicSignalError("unexpected_signal_kind")


def _attempt(
    dimension: SignalDimension, collected: _CollectedDimension, applicable: bool
) -> DimensionAttempt:
    sources = tuple(dict.fromkeys(document.source_id for document in collected.documents))
    times = [
        document.observed_at for document in collected.documents if document.observed_at is not None
    ]
    values: dict[tuple[str, ...], set[str]] = defaultdict(set)
    unique: list[EvidenceBoundCandidate] = []
    seen: set[str] = set()
    for candidate in collected.candidates:
        identity = candidate.model_dump_json()
        if identity not in seen:
            unique.append(candidate)
            seen.add(identity)
        compared = candidate.value.model_dump_json()
        if isinstance(candidate.value, CvssSignalValue):
            compared = json.dumps((candidate.value.base_score, candidate.value.vector))
        values[_scope(candidate, collected.cvss_targets)].add(compared)
    if unique:
        status = (
            DimensionStatus.CONFLICT
            if any(len(group) > 1 for group in values.values())
            else DimensionStatus.AVAILABLE
        )
        error = "partial_signal_source_failure" if collected.errors else None
    elif collected.errors:
        error = collected.errors[0]
        status = (
            DimensionStatus.BLOCKED
            if error
            in {
                "cwe_catalog_missing",
                "cwe_identifier_not_verified",
                "cvss_qualifier_missing",
                "cvss_authority_missing",
                "structured_payload_missing",
            }
            else DimensionStatus.FAILED
        )
        if error == "cwe_source_unknown":
            status = DimensionStatus.PENDING
    elif not applicable:
        status, error = DimensionStatus.NOT_APPLICABLE, None
    elif (
        collected.missing
        and collected.documents
        and len(times) == len(collected.documents)
        and all(document.blocks_complete for document in collected.documents)
    ):
        status, error = DimensionStatus.NOT_FOUND, None
    else:
        status, error = DimensionStatus.PENDING, None
    versions = {
        document.source_version for document in collected.documents if document.source_version
    }
    return DimensionAttempt(
        dimension=dimension,
        status=status,
        candidates=tuple(unique),
        source_ids=sources,
        searched_at=min(times) if status == DimensionStatus.NOT_FOUND else None,
        observed_at=min(times) if times else None,
        error_code=error,
        source_version=next(iter(versions)) if len(versions) == 1 else None,
    )


def enrich_structured_fields(
    context: EnrichmentContext, documents: tuple[EnrichmentDocument, ...]
) -> tuple[DimensionAttempt, ...]:
    """Propose values; publication validates scope, current revisions and stored raw hashes."""
    if (
        not 1 <= len(documents) <= 20
        or len({document.revision_id for document in documents}) != len(documents)
        or any(document.revision_id not in context.revision_ids for document in documents)
    ):
        raise PublicSignalError("document_revision_outside_context")
    collected: dict[SignalDimension, _CollectedDimension] = {
        dimension: _CollectedDimension() for dimension in PUBLIC_DIMENSIONS
    }
    catalogs = tuple(document for document in documents if _publisher(document) == "cwe")
    applicable_cvss = bool(context.external_cve_ids) or any(
        document.document_kind == DocumentKind.ADVISORY for document in documents
    )
    applicable_cwe = applicable_cvss or any(
        document.document_kind in {DocumentKind.ARTICLE, DocumentKind.REPOSITORY_RECORD}
        for document in documents
    )
    for document in documents:
        publisher = _publisher(document)
        if publisher in {"epss", "kev"}:
            dimension: Literal["epss", "kev"] = "epss" if publisher == "epss" else "kev"
            result = collected[dimension]
            result.documents.append(document)
            try:
                candidates = _public_signal_candidates(context, document, dimension)
                result.candidates.extend(candidates)
                result.missing = result.missing and not candidates
            except ValueError as error:
                result.errors.append(
                    error.code if isinstance(error, PublicSignalError) else "invalid_signal_value"
                )
            continue
        if publisher not in {"nvd", "vendor"}:
            continue
        for signal in PUBLIC_DIMENSIONS:
            if signal not in {"cvss", "cwe"}:
                continue
            result = collected[signal]
            result.documents.append(document)
            try:
                payload = _payload(document)
                if publisher == "vendor":
                    vendor = normalize_vendor_advisory(payload, repository=APPROVED_REPOSITORY)
                    if str(document.canonical_uri) != vendor.canonical_uri or (
                        vendor.cve_id is not None and vendor.cve_id not in context.external_cve_ids
                    ):
                        raise PublicSignalError("cross_cve_vendor_document")
                    target = vendor.cve_id or vendor.ghsa_id
                else:
                    cve = payload.get("cve")
                    if not isinstance(cve, dict) or cve.get("id") not in context.external_cve_ids:
                        raise PublicSignalError("cross_cve_nvd_document")
                    if (
                        str(document.canonical_uri)
                        != f"https://nvd.nist.gov/vuln/detail/{cve['id']}"
                    ):
                        raise PublicSignalError("cross_cve_nvd_document")
                    target = cve["id"]
                if signal == "cvss":
                    candidates = (
                        _nvd_cvss(context, document, payload)
                        if publisher == "nvd"
                        else _vendor_cvss(document, payload)
                    )
                    result.cvss_targets[document.revision_id] = target
                else:
                    candidates = _cwe_candidates(document, payload, publisher, catalogs)
                    if candidates:
                        result.documents.extend(catalogs)
                result.candidates.extend(candidates)
                result.missing = result.missing and not candidates
                if publisher == "nvd" and not candidates:
                    raw_cve = payload.get("cve")
                    required = "metrics" if signal == "cvss" else "weaknesses"
                    result.missing = (
                        result.missing and isinstance(raw_cve, dict) and required in raw_cve
                    )
                elif publisher == "vendor" and not candidates:
                    required = "cvss" if signal == "cvss" else "cwes"
                    result.missing = result.missing and required in payload
            except ValueError as error:
                result.errors.append(
                    error.code
                    if isinstance(error, PublicSignalError)
                    else "invalid_structured_signal"
                )
    for result in collected.values():
        if len(result.candidates) > 100:
            result.candidates.clear()
            result.errors.append("signal_candidate_limit_exceeded")
    applicable_by_dimension: dict[SignalDimension, bool] = {
        "cvss": applicable_cvss,
        "epss": bool(context.external_cve_ids),
        "kev": bool(context.external_cve_ids),
        "cwe": applicable_cwe,
    }
    return tuple(
        _attempt(dimension, collected[dimension], applicable_by_dimension[dimension])
        for dimension in PUBLIC_DIMENSIONS
    )
