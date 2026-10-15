"""Persist two approved public source pages through the shared PG knowledge services."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal
from urllib.parse import parse_qsl, urlsplit
from uuid import NAMESPACE_URL, UUID, uuid5

from sqlalchemy import func, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from ai_intel.domain.access import (
    MANAGE_PUBLIC_SOURCES,
    READ_PUBLIC,
    AccessScope,
    PermissionDeniedError,
    Role,
)
from ai_intel.domain.enums import (
    ClaimOrigin,
    ClaimStatus,
    ConditionValue,
    DimensionStatus,
    FreshnessStatus,
)
from ai_intel.domain.records import ClaimRecord, ScoreValue
from ai_intel.domain.values import Identifier, VisibilityScope
from ai_intel.enrichment.persistence import DimensionRepository, DimensionSubmission
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.ingestion.parsing.parsers import parse_json_document
from ai_intel.ingestion.parsing.text_blocks import ParseOutcome, TextBlock
from ai_intel.ingestion.sources.nvd import normalize_nvd_page, normalize_nvd_record
from ai_intel.ingestion.sources.vendor_advisories import normalize_vendor_advisory
from ai_intel.knowledge.event_linking import EventIdentifier, EventRepository, EventSubmission
from ai_intel.knowledge.models import (
    document_revisions,
    documents,
    fetch_attempts,
    text_blocks,
)
from ai_intel.knowledge.persistence import ClaimSubmission, EvidenceLink, KnowledgeRepository
from ai_intel.knowledge.persistence_models import claims, event_documents, events
from ai_intel.knowledge.revisions import (
    add_text_block,
    attach_evidence_span,
    record_fetch_attempt,
    register_response_content,
    save_document_revision,
)

MAX_RESPONSE_BYTES = 5 * 1024 * 1024
PUBLIC_SCOPE = VisibilityScope(visibility="public")
SOURCE_DEFINITIONS = {
    "nvd_ollama": (
        str(uuid5(NAMESPACE_URL, "dianzi:source:nvd-ollama")),
        "NVD Ollama keyword window",
        "structured_vulnerability",
        "https://services.nvd.nist.gov",
    ),
    "vllm_vendor": (
        str(uuid5(NAMESPACE_URL, "dianzi:source:vllm-vendor")),
        "vLLM repository security advisories",
        "vendor_advisory",
        "https://api.github.com",
    ),
}


class SourceDocumentError(ValueError):
    """A source page cannot be safely published; callers must preserve failure state."""


@dataclass(frozen=True)
class SourceResponse:
    """A fixed-endpoint response; observed_at is the gateway receipt time."""

    source_kind: Literal["nvd_ollama", "vllm_vendor"]
    body: bytes
    request_url: str
    observed_at: datetime


@dataclass(frozen=True)
class SavedSourceResponse:
    """Database identities in the caller's transaction, which is not yet committed here."""

    source_id: str
    revision_ids: tuple[str, ...]
    event_ids: tuple[str, ...]
    response_content_hash: str
    new_revision_count: int


@dataclass(frozen=True)
class _SourceFact:
    predicate: str
    value: str | ScoreValue
    json_pointer: str


@dataclass(frozen=True)
class _PreparedDocument:
    record_id: str
    title: str
    canonical_uri: str
    source_published_at: datetime | None
    source_modified_at: datetime | None
    external_ids: tuple[tuple[Literal["cve", "ghsa"], str], ...]
    payload: bytes
    source_json_pointer: str
    parsed: ParseOutcome
    facts: tuple[_SourceFact, ...]


def _aware_time(value: datetime) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise SourceDocumentError("source observation and ingestion time must be timezone aware")
    return value.astimezone(UTC)


def _request_parameters(response: SourceResponse) -> dict[str, str]:
    if response.source_kind not in SOURCE_DEFINITIONS:
        raise SourceDocumentError("unsupported source kind")
    if (
        not isinstance(response.request_url, str)
        or len(response.request_url) > 2000
        or response.request_url != response.request_url.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in response.request_url)
    ):
        raise SourceDocumentError("invalid source request URL")
    try:
        parts = urlsplit(response.request_url)
        pairs = parse_qsl(parts.query, strict_parsing=True, keep_blank_values=True, errors="strict")
    except (ValueError, UnicodeError):
        raise SourceDocumentError("invalid source request URL") from None
    parameters = dict(pairs)
    if parts.fragment or len(parameters) != len(pairs):
        raise SourceDocumentError("invalid source request URL")
    if response.source_kind == "nvd_ollama":
        base = "https://services.nvd.nist.gov/rest/json/cves/2.0"
        allowed = {"keywordSearch", "resultsPerPage", "startIndex"}
        fixed = parameters.get("keywordSearch") == "ollama"
        count_key, position_key, minimum = "resultsPerPage", "startIndex", 0
    else:
        base = "https://api.github.com/repos/vllm-project/vllm/security-advisories"
        allowed = {"per_page", "state", "page"}
        fixed = parameters.get("state") == "published"
        count_key, position_key, minimum = "per_page", "page", 1
    if (
        f"{parts.scheme}://{parts.netloc}{parts.path}" != base
        or set(parameters) != allowed
        or not fixed
    ):
        raise SourceDocumentError("source request URL is outside approved scope")
    for key in (count_key, position_key):
        number = parameters[key]
        if not number.isascii() or not number.isdigit() or len(number) > 18:
            raise SourceDocumentError("invalid source request URL pagination")
    if not 1 <= int(parameters[count_key]) <= 100 or int(parameters[position_key]) < minimum:
        raise SourceDocumentError("invalid source request URL pagination")
    return parameters


def _skip_space(content: str, offset: int) -> int:
    while offset < len(content) and content[offset] in " \t\r\n":
        offset += 1
    return offset


def _array_members(content: str, offset: int) -> tuple[tuple[object, bytes], ...]:
    """Locate members of an already validated JSON array using the standard decoder."""
    decoder = json.JSONDecoder()
    position = _skip_space(content, offset + 1)
    members: list[tuple[object, bytes]] = []
    while content[position] != "]":
        value, end = decoder.raw_decode(content, position)
        members.append((value, content[position:end].encode("utf-8")))
        position = _skip_space(content, end)
        if content[position] == ",":
            position = _skip_space(content, position + 1)
    return tuple(members)


def _nvd_members(content: str) -> tuple[tuple[object, bytes], ...]:
    decoder = json.JSONDecoder()
    position = _skip_space(content, _skip_space(content, 0) + 1)
    while content[position] != "}":
        key, end = decoder.raw_decode(content, position)
        start = _skip_space(content, _skip_space(content, end) + 1)
        if key == "vulnerabilities":
            return _array_members(content, start)
        _, end = decoder.raw_decode(content, start)
        position = _skip_space(content, end)
        if content[position] == ",":
            position = _skip_space(content, position + 1)
    raise SourceDocumentError("NVD response has no vulnerabilities array")


def _source_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value).astimezone(UTC) if value is not None else None


def _prepare_documents(response: SourceResponse) -> tuple[_PreparedDocument, ...]:
    parameters = _request_parameters(response)
    if not isinstance(response.body, bytes) or len(response.body) > MAX_RESPONSE_BYTES:
        raise SourceDocumentError("source response byte limit exceeded")
    validated = parse_json_document(response.body)
    if validated.status != "parsed":
        raise SourceDocumentError("source response is not strict JSON2")
    content = response.body.decode("utf-8")
    payload: object = json.loads(content)
    try:
        if response.source_kind == "nvd_ollama":
            if not isinstance(payload, dict):
                raise SourceDocumentError("NVD response must be an object")
            page = normalize_nvd_page(payload)
            if page.start_index != int(parameters["startIndex"]):
                raise SourceDocumentError("NVD response offset differs from request")
            members = _nvd_members(content)
            maximum = int(parameters["resultsPerPage"])
        else:
            if not isinstance(payload, list):
                raise SourceDocumentError("vendor response must be an array")
            members = _array_members(content, _skip_space(content, 0))
            maximum = int(parameters["per_page"])
        if len(members) > min(maximum, 100):
            raise SourceDocumentError("source response exceeds page limit")
        prepared: list[_PreparedDocument] = []
        record_ids: set[str] = set()
        for index, (member, raw_bytes) in enumerate(members):
            if not isinstance(member, dict):
                raise SourceDocumentError("source member must be an object")
            parsed = parse_json_document(raw_bytes)
            if parsed.status != "parsed":
                raise SourceDocumentError("source member cannot be parsed")
            document = _prepare_member(response.source_kind, index, member, raw_bytes, parsed)
            if document.record_id in record_ids:
                raise SourceDocumentError("duplicate record in source response")
            if len(document.title) > 500 or any(
                len(fact.json_pointer) > 500 for fact in document.facts
            ):
                raise SourceDocumentError("source member exceeds publication field limits")
            record_ids.add(document.record_id)
            prepared.append(document)
        return tuple(prepared)
    except SourceDocumentError:
        raise
    except (ValueError, TypeError, KeyError, IndexError):
        raise SourceDocumentError("source response member violates source contract") from None


def _prepare_member(
    kind: str, index: int, member: dict[str, object], raw: bytes, parsed: ParseOutcome
) -> _PreparedDocument:
    facts: list[_SourceFact] = []
    if kind == "nvd_ollama":
        nvd = normalize_nvd_record(member)
        cve = member["cve"]
        if not isinstance(cve, dict):
            raise SourceDocumentError("NVD cve member must be an object")
        for ordinal, description in enumerate(cve.get("descriptions", [])):
            if (
                isinstance(description, dict)
                and description.get("lang") == "en"
                and description.get("value") == nvd.description
                and nvd.description
            ):
                facts.append(
                    _SourceFact(
                        "source_excerpt",
                        nvd.description[:2000],
                        f"/cve/descriptions/{ordinal}/value",
                    )
                )
                break
        for metric in nvd.metrics:
            if metric.authority is not None:
                facts.append(
                    _SourceFact(
                        "cvss_score",
                        ScoreValue(
                            score=metric.score, authority=metric.authority, vector=metric.vector
                        ),
                        metric.json_pointer,
                    )
                )
        if nvd.status is not None:
            facts.append(_SourceFact("source_status", nvd.status, "/cve/vulnStatus"))
        return _PreparedDocument(
            nvd.cve_id,
            nvd.cve_id,
            f"https://nvd.nist.gov/vuln/detail/{nvd.cve_id}",
            _source_time(nvd.published_at),
            _source_time(nvd.last_modified_at),
            (("cve", nvd.cve_id),),
            raw,
            f"/vulnerabilities/{index}",
            parsed,
            tuple(facts),
        )
    vendor = normalize_vendor_advisory(member, repository="vllm-project/vllm")
    excerpt = vendor.description if vendor.description is not None else vendor.title
    path = "/description" if vendor.description is not None else "/summary"
    facts.append(_SourceFact("source_excerpt", excerpt[:2000], path))
    if vendor.withdrawn_at is not None:
        withdrawn = member.get("withdrawn_at")
        if not isinstance(withdrawn, str):
            raise SourceDocumentError("withdrawal lacks original source timestamp")
        facts.append(_SourceFact("source_withdrawn_at", withdrawn, "/withdrawn_at"))
    for ordinal, vulnerability in enumerate(vendor.vulnerabilities):
        if vulnerability.package_name is not None:
            facts.append(
                _SourceFact(
                    "affected_product",
                    vulnerability.package_name,
                    f"/vulnerabilities/{ordinal}/package/name",
                )
            )
    identifiers: list[tuple[Literal["cve", "ghsa"], str]] = [("ghsa", vendor.ghsa_id)]
    if vendor.cve_id is not None:
        identifiers.append(("cve", vendor.cve_id))
    return _PreparedDocument(
        vendor.ghsa_id,
        vendor.title,
        vendor.canonical_uri,
        _source_time(vendor.published_at),
        _source_time(vendor.updated_at),
        tuple(identifiers),
        raw,
        f"/{index}",
        parsed,
        tuple(facts),
    )


def _require_public_administrator(scope: AccessScope) -> None:
    scope.requires(MANAGE_PUBLIC_SOURCES)
    scope.requires(READ_PUBLIC)
    if scope.role != Role.SYSTEM_ADMIN or scope.tenant_id is not None:
        raise PermissionDeniedError("public source administration required")


def ensure_source_registration(
    session: Session,
    access_scope: AccessScope,
    source_kind: Literal["nvd_ollama", "vllm_vendor"],
    created_at: datetime,
) -> str:
    """Register one fixed public source for cursor leases; the caller owns commit."""
    _require_public_administrator(access_scope)
    created_at = _aware_time(created_at)
    if source_kind not in SOURCE_DEFINITIONS:
        raise SourceDocumentError("unsupported source kind")
    source_id, name, category, origin = SOURCE_DEFINITIONS[source_kind]
    session.execute(
        select(func.pg_advisory_xact_lock(func.hashtextextended("source:" + source_id, 0)))
    )
    session.execute(
        text(
            "INSERT INTO sources(source_id,name,category,base_origin,visibility,"
            "tenant_id,created_at) VALUES (:id,:name,:category,:origin,'public',NULL,:time) "
            "ON CONFLICT(source_id) DO NOTHING"
        ),
        {"id": source_id, "name": name, "category": category, "origin": origin, "time": created_at},
    )
    row = session.execute(
        text(
            "SELECT name,category,base_origin,visibility,tenant_id "
            "FROM sources WHERE source_id=:id FOR UPDATE"
        ),
        {"id": source_id},
    ).one()
    if tuple(row) != (name, category, origin, "public", None):
        raise SourceDocumentError("source identity or scope conflicts with registration")
    return source_id


def persist_source_response(
    session: Session,
    store: ContentStorage,
    access_scope: AccessScope,
    response: SourceResponse,
    *,
    ingested_at: datetime,
) -> SavedSourceResponse:
    """Persist a whole page in a savepoint; the caller alone commits the outer transaction."""
    _require_public_administrator(access_scope)
    observed_at, ingested_at = _aware_time(response.observed_at), _aware_time(ingested_at)
    if observed_at > ingested_at:
        raise SourceDocumentError("source observation time follows ingestion time")
    members = _prepare_documents(response)
    with session.begin_nested():
        source_id = ensure_source_registration(
            session, access_scope, response.source_kind, ingested_at
        )
        response_hash = register_response_content(
            session, store, response.body, ingested_at
        ).content_hash
        revision_ids: list[str] = []
        event_ids: list[str] = []
        new_count = 0
        for member in members:
            revision_id, event_id, reused = _persist_member(
                session,
                store,
                access_scope,
                source_id,
                member,
                response_hash,
                observed_at,
                ingested_at,
            )
            revision_ids.append(revision_id)
            event_ids.append(event_id)
            new_count += int(not reused)
        attempt = record_fetch_attempt(session, source_id, observed_at, "succeeded", 200)
        session.execute(
            update(fetch_attempts)
            .where(fetch_attempts.c.attempt_id == attempt)
            .values(response_content_hash=response_hash, final_url=response.request_url)
        )
        return SavedSourceResponse(
            source_id,
            tuple(revision_ids),
            tuple(dict.fromkeys(event_ids)),
            response_hash,
            new_count,
        )


def _persist_member(
    session: Session,
    store: ContentStorage,
    scope: AccessScope,
    source_id: str,
    member: _PreparedDocument,
    response_hash: str,
    observed_at: datetime,
    ingested_at: datetime,
) -> tuple[str, str, bool]:
    document_id = str(uuid5(NAMESPACE_URL, f"dianzi:document:{source_id}:{member.record_id}"))
    candidate_event_id = str(uuid5(NAMESPACE_URL, f"dianzi:event:{source_id}:{member.record_id}"))
    session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(document_id, 0))))
    raw_hash = register_response_content(session, store, member.payload, ingested_at).content_hash
    session.execute(
        insert(documents)
        .values(
            document_id=document_id,
            source_id=source_id,
            kind="advisory",
            title=member.title,
            published_at=member.source_published_at,
            retrieved_at=observed_at,
            content_hash=raw_hash,
            visibility="public",
            tenant_id=None,
            schema_version=2,
        )
        .on_conflict_do_nothing(index_elements=[documents.c.document_id])
    )
    existing = (
        session.execute(
            select(documents).where(documents.c.document_id == document_id).with_for_update()
        )
        .mappings()
        .one()
    )
    if (existing["source_id"], existing["visibility"], existing["tenant_id"], existing["kind"]) != (
        source_id,
        "public",
        None,
        "advisory",
    ):
        raise SourceDocumentError("document identity or scope conflicts with source")
    saved = save_document_revision(
        session, store, document_id, member.payload, "public", None, ingested_at
    )
    if not saved.reused:
        prior_revisions = select(document_revisions.c.revision_id).where(
            document_revisions.c.document_id == document_id,
            document_revisions.c.revision_id != saved.revision_id,
        )
        session.execute(
            update(claims)
            .where(claims.c.source_revision_id.in_(prior_revisions))
            .values(is_current=False)
        )
        session.execute(
            update(event_documents)
            .where(event_documents.c.revision_id.in_(prior_revisions))
            .values(active=False)
        )
        session.execute(
            update(document_revisions)
            .where(document_revisions.c.revision_id == saved.revision_id)
            .values(
                canonical_uri=member.canonical_uri,
                source_published_at=member.source_published_at,
                source_modified_at=member.source_modified_at,
                first_observed_at=observed_at,
                ingested_at=ingested_at,
                parser_version=member.parsed.parser_version,
                normalizer_version=member.parsed.normalizer_version,
                parse_status=member.parsed.status,
                source_response_hash=response_hash,
                source_json_pointer=member.source_json_pointer,
            )
        )
        publication_key = f"source-revision:{saved.revision_id}"
        EventRepository(session, scope).publish_events(
            publication_key + ":event",
            PUBLIC_SCOPE,
            (
                EventSubmission(
                    event_id=Identifier(value=candidate_event_id),
                    event_type="vulnerability",
                    title=member.title,
                    scope=PUBLIC_SCOPE,
                    external_ids=tuple(
                        EventIdentifier(id_type=kind, id_value=value)
                        for kind, value in member.external_ids
                    ),
                    source_revision_ids=(Identifier(value=saved.revision_id),),
                ),
            ),
            ingested_at,
        )
    resolved_ids: tuple[str, ...] = tuple(
        session.scalars(
            select(event_documents.c.event_id).where(
                event_documents.c.revision_id == saved.revision_id,
                event_documents.c.active.is_(True),
            )
        )
    )
    if len(resolved_ids) != 1:
        raise SourceDocumentError("source revision lacks one resolved active event")
    event_id = str(resolved_ids[0])
    if not saved.reused:
        blocks: dict[str, tuple[str, TextBlock]] = {}
        for block in member.parsed.blocks:
            pointer = block.block_type.removeprefix("field:")
            block_id = add_text_block(
                session,
                saved.revision_id,
                block.ordinal,
                block.start_offset,
                block.end_offset,
                block.text,
            )
            session.execute(
                update(text_blocks)
                .where(text_blocks.c.block_id == block_id)
                .values(
                    block_type="json_field", page_number=block.page_number, json_pointer=pointer
                )
            )
            blocks[pointer] = (block_id, block)
        submissions = _fact_submissions(
            session,
            source_id,
            saved.revision_id,
            event_id,
            member.facts,
            blocks,
            observed_at,
            ingested_at,
        )
        if submissions:
            KnowledgeRepository(session, scope).publish(
                f"source-revision:{saved.revision_id}:facts",
                PUBLIC_SCOPE,
                submissions,
                created_at=ingested_at,
            )
        _publish_cvss(
            session,
            scope,
            source_id,
            saved.revision_id,
            event_id,
            submissions,
            observed_at,
            ingested_at,
        )
    return saved.revision_id, event_id, saved.reused


def _fact_submissions(
    session: Session,
    source_id: str,
    revision_id: str,
    event_id: str,
    facts: tuple[_SourceFact, ...],
    blocks: dict[str, tuple[str, TextBlock]],
    observed_at: datetime,
    ingested_at: datetime,
) -> tuple[ClaimSubmission, ...]:
    submissions: list[ClaimSubmission] = []
    for ordinal, fact in enumerate(facts):
        if fact.json_pointer not in blocks:
            raise SourceDocumentError("source fact lacks its JSON evidence field")
        block_id, block = blocks[fact.json_pointer]
        prefix = fact.json_pointer + ": "
        if not block.text.startswith(prefix):
            raise SourceDocumentError("source field text differs from JSON pointer")
        source_value = block.text[len(prefix) :]
        if isinstance(fact.value, ScoreValue):
            if json.loads(source_value) != fact.value.score:
                raise SourceDocumentError("source CVSS score differs from evidence")
            quote = source_value
        else:
            quote = fact.value
            if not source_value.startswith(quote) or (
                fact.predicate != "source_excerpt" and source_value != quote
            ):
                raise SourceDocumentError("source text fact differs from evidence")
        start = block.start_offset + len(prefix)
        evidence_id = attach_evidence_span(
            session,
            revision_id,
            start,
            start + len(quote),
            fact.json_pointer,
            quote,
            True,
            "public",
            None,
            ingested_at,
            block_id=block_id,
            verified_at=ingested_at,
        )
        links = [
            EvidenceLink(
                evidence_id=Identifier(value=evidence_id),
                support_kind="supports",
                validation_status="validated",
            )
        ]
        if isinstance(fact.value, ScoreValue):
            metric_path = fact.json_pointer.rsplit("/cvssData/", 1)[0]
            qualifiers = (
                (metric_path + "/source", fact.value.authority),
                (metric_path + "/cvssData/vectorString", fact.value.vector),
            )
            for pointer, expected in qualifiers:
                if expected is None:
                    continue
                if pointer not in blocks:
                    raise SourceDocumentError("CVSS qualifier lacks its source evidence")
                qualifier_id, qualifier = blocks[pointer]
                prefix = pointer + ": "
                if qualifier.text != prefix + expected:
                    raise SourceDocumentError("CVSS qualifier differs from source evidence")
                position = qualifier.start_offset + len(prefix)
                qualifier_evidence = attach_evidence_span(
                    session,
                    revision_id,
                    position,
                    position + len(expected),
                    pointer,
                    expected,
                    True,
                    "public",
                    None,
                    ingested_at,
                    block_id=qualifier_id,
                    verified_at=ingested_at,
                )
                links.append(
                    EvidenceLink(
                        evidence_id=Identifier(value=qualifier_evidence),
                        support_kind="supports",
                        validation_status="validated",
                    )
                )
        claim_id = str(
            uuid5(NAMESPACE_URL, f"source-fact:{revision_id}:{ordinal}:{fact.json_pointer}")
        )
        record = ClaimRecord(
            claim_id=Identifier(value=claim_id),
            subject=event_id,
            predicate=fact.predicate,
            object_value=fact.value,
            claim_status=ClaimStatus.SUPPORTED,
            claim_origin=ClaimOrigin.SOURCE_EXPLICIT
            if fact.predicate in {"source_status", "source_withdrawn_at"}
            else ClaimOrigin.STRUCTURED_SOURCE,
            condition_value=ConditionValue.TRUE,
            freshness=FreshnessStatus.CURRENT,
            asserted_at=ingested_at,
            observed_at=observed_at,
            scope=PUBLIC_SCOPE,
        )
        submissions.append(
            ClaimSubmission(
                record=record,
                source_id=Identifier(value=source_id),
                revision_id=Identifier(value=revision_id),
                json_path=fact.json_pointer,
                scoring_authority=fact.value.authority
                if isinstance(fact.value, ScoreValue)
                else "",
                evidence_links=tuple(links),
            )
        )
    return tuple(submissions)


def _publish_cvss(
    session: Session,
    scope: AccessScope,
    source_id: str,
    revision_id: str,
    event_id: str,
    submissions: tuple[ClaimSubmission, ...],
    observed_at: datetime,
    ingested_at: datetime,
) -> None:
    if source_id != SOURCE_DEFINITIONS["nvd_ollama"][0]:
        return
    scores = tuple(item for item in submissions if isinstance(item.record.object_value, ScoreValue))
    values_by_version: dict[str, set[tuple[float, str | None]]] = {}
    for item in scores:
        if isinstance(item.record.object_value, ScoreValue):
            metric_name = item.json_path.split("/")[3]
            values_by_version.setdefault(metric_name, set()).add(
                (item.record.object_value.score, item.record.object_value.vector)
            )
    status = (
        DimensionStatus.CONFLICT
        if any(len(values) > 1 for values in values_by_version.values())
        else (DimensionStatus.AVAILABLE if scores else DimensionStatus.PENDING)
    )
    version = session.scalar(select(events.c.business_version).where(events.c.event_id == event_id))
    if not isinstance(version, int) or version < 1:
        raise SourceDocumentError("event lacks its current business version")
    DimensionRepository(session, scope).publish(
        f"source-revision:{revision_id}",
        DimensionSubmission(
            event_id=UUID(event_id),
            dimension="cvss",
            status=status,
            expected_event_version=int(version),
            input_fingerprint=hashlib.sha256(revision_id.encode()).hexdigest(),
            claim_ids=tuple(UUID(item.record.claim_id.value) for item in scores),
            reference_ids=tuple(
                UUID(link.evidence_id.value) for item in scores for link in item.evidence_links
            ),
            source_ids=(UUID(source_id),),
            observed_at=observed_at,
            freshness=FreshnessStatus.CURRENT if scores else FreshnessStatus.UNKNOWN,
        ),
        ingested_at,
    )
