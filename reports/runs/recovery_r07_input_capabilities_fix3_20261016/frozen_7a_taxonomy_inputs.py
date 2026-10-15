"""Parse pinned official taxonomies; database loading rechecks all parent permissions."""

from __future__ import annotations

import hashlib
import io
import math
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from typing import Literal
from urllib.parse import urlsplit
from uuid import UUID
from xml.etree import ElementTree

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_intel.api.document_read_service import sources
from ai_intel.domain.access import READ_PUBLIC, AccessScope
from ai_intel.domain.values import VisibilityScope
from ai_intel.enrichment.inputs import _require_input_scopes
from ai_intel.infrastructure.content_store import ContentStorage
from ai_intel.knowledge.models import content_objects, document_revisions, documents

MAX_CATALOGUE_BYTES = 8 * 1024 * 1024
MAX_ATLAS_BYTES = 2 * 1024 * 1024
MAX_CWE_XML_BYTES = 32 * 1024 * 1024
CWE_NAMESPACE = "{http://cwe.mitre.org/cwe-7}"


class TaxonomyInputError(ValueError):
    """Safe codes identify missing authority, corruption and unsupported formats separately."""


class CatalogueProvenance(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True, hide_input_in_errors=True)
    kind: Literal["cwe", "atlas"]
    canonical_uri: str = Field(min_length=1, max_length=2000)
    snapshot_version: str = Field(min_length=1, max_length=200)
    content_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    revision_id: UUID | None = None
    document_id: UUID | None = None
    source_id: UUID | None = None


@dataclass(frozen=True)
class TaxonomyEntry:
    identifier: str
    name: str
    source_locator: str
    identifier_quote: str | None = None
    start_offset: int | None = None
    end_offset: int | None = None


@dataclass(frozen=True)
class TaxonomyCatalogue:
    """An ID in the catalogue establishes taxonomy membership, never an event mapping."""

    provenance: CatalogueProvenance
    content_version: str
    format_version: str
    entries: tuple[TaxonomyEntry, ...]
    extracted_content_sha256: str

    @property
    def supported_ids(self) -> frozenset[str]:
        return frozenset(entry.identifier for entry in self.entries)


def _verify_raw(raw: bytes, provenance: CatalogueProvenance) -> None:
    if (
        type(raw) is not bytes
        or not 1 <= len(raw) <= MAX_CATALOGUE_BYTES
        or hashlib.sha256(raw).hexdigest() != provenance.content_sha256
    ):
        raise TaxonomyInputError("taxonomy_object_integrity_invalid")
    try:
        parsed = urlsplit(provenance.canonical_uri)
        port = parsed.port
    except ValueError:
        raise TaxonomyInputError("taxonomy_source_uri_invalid") from None
    if (
        parsed.scheme != "https"
        or parsed.username is not None
        or parsed.password is not None
        or port not in (None, 443)
        or parsed.query
        or parsed.fragment
    ):
        raise TaxonomyInputError("taxonomy_source_uri_invalid")
    if provenance.kind == "cwe":
        version = provenance.snapshot_version
        if (
            re.fullmatch(r"[0-9]{1,3}\.[0-9]{1,3}(?:\.[0-9]{1,3})?", version) is None
            or parsed.hostname != "cwe.mitre.org"
            or parsed.path
            not in {f"/data/xml/cwec_v{version}.xml.zip", f"/data/xml/cwec_v{version}.xml"}
        ):
            raise TaxonomyInputError("taxonomy_source_uri_invalid")
    else:
        if (
            len(raw) > MAX_ATLAS_BYTES
            or re.fullmatch(r"[0-9a-f]{40}", provenance.snapshot_version) is None
            or parsed.hostname != "raw.githubusercontent.com"
            or parsed.path
            not in {
                f"/{organization}/atlas-data/{provenance.snapshot_version}/dist/ATLAS.yaml"
                for organization in ("mitre", "mitre-atlas")
            }
        ):
            raise TaxonomyInputError("taxonomy_source_uri_invalid")


def parse_cwe_catalogue(raw: bytes, provenance: CatalogueProvenance) -> TaxonomyCatalogue:
    """Accept an exact versioned MITRE XML catalogue or its single-file bounded ZIP."""
    if provenance.kind != "cwe":
        raise TaxonomyInputError("taxonomy_kind_invalid")
    _verify_raw(raw, provenance)
    xml = raw
    if raw.startswith(b"PK"):
        try:
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                members = archive.infolist()
                if len(members) != 1:
                    raise TaxonomyInputError("taxonomy_archive_invalid")
                member = members[0]
                if (
                    re.fullmatch(r"cwec[_a-zA-Z0-9.\-]*\.xml", member.filename) is None
                    or member.flag_bits & 1
                    or not 1 <= member.file_size <= MAX_CWE_XML_BYTES
                    or member.file_size > max(1, member.compress_size) * 200
                ):
                    raise TaxonomyInputError("taxonomy_archive_invalid")
                with archive.open(member) as stream:
                    xml = stream.read(MAX_CWE_XML_BYTES + 1)
        except (zipfile.BadZipFile, RuntimeError, OSError):
            raise TaxonomyInputError("taxonomy_archive_invalid") from None
    if len(xml) > MAX_CWE_XML_BYTES:
        raise TaxonomyInputError("taxonomy_xml_budget_exceeded")
    try:
        decoded = xml.decode("utf-8-sig")
        if re.search(r"<!\s*(?:DOCTYPE|ENTITY)", decoded, re.IGNORECASE):
            raise TaxonomyInputError("taxonomy_xml_unsafe")
        depth = nodes = 0
        root: ElementTree.Element | None = None
        for event, element in ElementTree.iterparse(io.StringIO(decoded), events=("start", "end")):
            if root is None:
                root = element
            depth += 1 if event == "start" else -1
            nodes += event == "start"
            if depth > 64 or nodes > 250000:
                raise TaxonomyInputError("taxonomy_xml_budget_exceeded")
    except (UnicodeError, ElementTree.ParseError):
        raise TaxonomyInputError("taxonomy_xml_invalid") from None
    if root is None or root.tag != CWE_NAMESPACE + "Weakness_Catalog":
        raise TaxonomyInputError("taxonomy_cwe_root_invalid")
    version = root.get("Version")
    if version != provenance.snapshot_version:
        raise TaxonomyInputError("taxonomy_version_mismatch")
    entries = root.findall(f"{CWE_NAMESPACE}Weaknesses/{CWE_NAMESPACE}Weakness")
    result: list[TaxonomyEntry] = []
    identifiers: set[str] = set()
    for element in entries:
        identifier = "CWE-" + element.get("ID", "")
        name = element.get("Name", "")
        if (
            re.fullmatch(r"CWE-[1-9][0-9]{0,5}", identifier) is None
            or identifier in identifiers
            or not 1 <= len(name) <= 2000
            or "\0" in name
        ):
            raise TaxonomyInputError("taxonomy_entry_invalid")
        identifiers.add(identifier)
        result.append(
            TaxonomyEntry(
                identifier,
                name,
                f"/Weakness_Catalog/Weaknesses/Weakness[@ID='{identifier[4:]}']",
            )
        )
    if not 1 <= len(result) <= 5000:
        raise TaxonomyInputError("taxonomy_entry_count_invalid")
    return TaxonomyCatalogue(
        provenance, version, "cwe-7", tuple(result), hashlib.sha256(xml).hexdigest()
    )


def _check_yaml_node(node: yaml.Node, loader: yaml.SafeLoader, depth: int = 0) -> None:
    if depth > 64:
        raise TaxonomyInputError("taxonomy_yaml_budget_exceeded")
    if node.tag not in {
        "tag:yaml.org,2002:" + name
        for name in ("map", "seq", "str", "null", "bool", "int", "float", "timestamp")
    }:
        raise TaxonomyInputError("taxonomy_yaml_tag_forbidden")
    if isinstance(node, yaml.MappingNode):
        keys: set[object] = set()
        for key, value in node.value:
            if not isinstance(key, yaml.ScalarNode):
                raise TaxonomyInputError("taxonomy_yaml_key_invalid")
            _check_yaml_node(key, loader, depth + 1)
            constructed_key: object = loader.construct_object(key)
            if type(constructed_key) not in (str, int, bool, float, type(None), date, datetime) or (
                isinstance(constructed_key, float) and not math.isfinite(constructed_key)
            ):
                raise TaxonomyInputError("taxonomy_yaml_key_invalid")
            if constructed_key in keys:
                raise TaxonomyInputError("taxonomy_yaml_duplicate_key")
            keys.add(constructed_key)
            _check_yaml_node(value, loader, depth + 1)
    elif isinstance(node, yaml.SequenceNode):
        for value in node.value:
            _check_yaml_node(value, loader, depth + 1)


def _atlas_identifier_quotes(node: yaml.Node, text: str) -> dict[str, tuple[str, int, int]]:
    quotes: dict[str, tuple[str, int, int]] = {}
    if not isinstance(node, yaml.MappingNode):
        raise TaxonomyInputError("taxonomy_atlas_format_unsupported")
    root_values = {
        key.value: value for key, value in node.value if isinstance(key, yaml.ScalarNode)
    }
    matrices = root_values.get("matrices")
    if not isinstance(matrices, yaml.SequenceNode):
        raise TaxonomyInputError("taxonomy_atlas_format_unsupported")
    for matrix in matrices.value:
        if not isinstance(matrix, yaml.MappingNode):
            raise TaxonomyInputError("taxonomy_atlas_format_unsupported")
        matrix_values = {
            key.value: value for key, value in matrix.value if isinstance(key, yaml.ScalarNode)
        }
        techniques = matrix_values.get("techniques")
        if not isinstance(techniques, yaml.SequenceNode):
            raise TaxonomyInputError("taxonomy_atlas_format_unsupported")
        for technique in techniques.value:
            if not isinstance(technique, yaml.MappingNode):
                raise TaxonomyInputError("taxonomy_entry_invalid")
            values = {
                key.value: value
                for key, value in technique.value
                if isinstance(key, yaml.ScalarNode)
            }
            identifier = values.get("id")
            if not isinstance(identifier, yaml.ScalarNode):
                raise TaxonomyInputError("taxonomy_entry_invalid")
            start = text.rfind("\n", 0, identifier.start_mark.index) + 1
            end = text.find("\n", identifier.end_mark.index)
            end = len(text) if end == -1 else end
            quote = text[start:end].rstrip("\r")
            end = start + len(quote)
            if identifier.value not in quote:
                raise TaxonomyInputError("taxonomy_identifier_coordinates_invalid")
            quotes[identifier.value] = (quote, start, end)
    return quotes


def parse_atlas_catalogue(raw: bytes, provenance: CatalogueProvenance) -> TaxonomyCatalogue:
    """Parse the frozen legacy ATLAS format; newer formats require explicit integration.

    PyYAML performs YAML decoding. Aliases, duplicate keys and nonstandard tags are
    rejected before construction. No downloaded Python, URLs or PoCs are executed.
    """
    if provenance.kind != "atlas":
        raise TaxonomyInputError("taxonomy_kind_invalid")
    _verify_raw(raw, provenance)
    try:
        depth = 0
        for nodes, event in enumerate(yaml.parse(raw, Loader=yaml.SafeLoader), start=1):
            if isinstance(event, yaml.AliasEvent):
                raise TaxonomyInputError("taxonomy_yaml_alias_forbidden")
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                depth += 1
            elif isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                depth -= 1
            if depth > 64 or nodes > 100000:
                raise TaxonomyInputError("taxonomy_yaml_budget_exceeded")
        node = yaml.compose(raw, Loader=yaml.SafeLoader)
        if node is None:
            raise TaxonomyInputError("taxonomy_yaml_invalid")
        loader = yaml.SafeLoader(raw)
        try:
            _check_yaml_node(node, loader)
        finally:
            loader.dispose()
        identifier_quotes = _atlas_identifier_quotes(node, raw.decode("utf-8"))
        decoded: object = yaml.safe_load(raw)
    except TaxonomyInputError:
        raise
    except (yaml.YAMLError, UnicodeError, RecursionError, ValueError, KeyError):
        raise TaxonomyInputError("taxonomy_yaml_invalid") from None
    if not isinstance(decoded, dict) or decoded.get("id") != "ATLAS":
        raise TaxonomyInputError("taxonomy_atlas_format_unsupported")
    version = decoded.get("version")
    matrices = decoded.get("matrices")
    if not isinstance(version, str) or re.fullmatch(r"\d+\.\d+\.\d+", version) is None:
        raise TaxonomyInputError("taxonomy_version_invalid")
    if not isinstance(matrices, list) or not 1 <= len(matrices) <= 10:
        raise TaxonomyInputError("taxonomy_atlas_format_unsupported")
    result: list[TaxonomyEntry] = []
    identifiers: set[str] = set()
    for matrix_index, matrix in enumerate(matrices):
        if not isinstance(matrix, dict) or not isinstance(matrix.get("techniques"), list):
            raise TaxonomyInputError("taxonomy_atlas_format_unsupported")
        for technique_index, technique in enumerate(matrix["techniques"]):
            if not isinstance(technique, dict):
                raise TaxonomyInputError("taxonomy_entry_invalid")
            identifier = technique.get("id")
            name = technique.get("name")
            if (
                not isinstance(identifier, str)
                or re.fullmatch(r"AML\.T[0-9]{4}(?:\.[0-9]{3})?", identifier) is None
                or identifier in identifiers
                or not isinstance(name, str)
                or not 1 <= len(name) <= 2000
                or "\0" in name
                or technique.get("object-type") != "technique"
            ):
                raise TaxonomyInputError("taxonomy_entry_invalid")
            identifiers.add(identifier)
            if identifier not in identifier_quotes:
                raise TaxonomyInputError("taxonomy_identifier_coordinates_invalid")
            quote, start, end = identifier_quotes[identifier]
            result.append(
                TaxonomyEntry(
                    identifier,
                    name,
                    f"/matrices/{matrix_index}/techniques/{technique_index}",
                    quote,
                    start,
                    end,
                )
            )
    if not 1 <= len(result) <= 5000:
        raise TaxonomyInputError("taxonomy_entry_count_invalid")
    return TaxonomyCatalogue(
        provenance, version, "atlas-legacy", tuple(result), hashlib.sha256(raw).hexdigest()
    )


def load_taxonomy_catalogue(
    session: Session,
    store: ContentStorage,
    access_scope: AccessScope,
    scope: VisibilityScope,
    revision_id: UUID,
    kind: Literal["cwe", "atlas"],
) -> TaxonomyCatalogue:
    """Read only an already persisted current catalogue after source/document/revision ACLs.

    The caller registers official catalogue sources and persists raw bytes and version
    metadata. This loader adds no catalogue URL fetching or public context fields.
    Publication must still recheck every returned source revision against PostgreSQL.
    """
    access_scope.requires(READ_PUBLIC)
    _require_input_scopes(session, access_scope, scope, (str(revision_id),))
    row = (
        session.execute(
            select(
                document_revisions,
                documents.c.source_id,
                content_objects.c.size_bytes,
                sources.c.category.label("source_category"),
            )
            .join(documents, documents.c.document_id == document_revisions.c.document_id)
            .join(sources, sources.c.source_id == documents.c.source_id)
            .join(
                content_objects, content_objects.c.content_hash == document_revisions.c.content_hash
            )
            .where(document_revisions.c.revision_id == str(revision_id))
            .with_for_update(read=True, of=(document_revisions, documents, sources))
        )
        .mappings()
        .one_or_none()
    )
    if row is None or not row["is_current"]:
        raise TaxonomyInputError("taxonomy_revision_not_current")
    metadata = row["source_metadata"]
    if (
        metadata.get("content_coverage") != "full_text"
        or row["source_category"] != "technical_standard"
        or row["parse_status"] not in {"parsed", "partial"}
        or not 1 <= row["size_bytes"] <= MAX_CATALOGUE_BYTES
    ):
        raise TaxonomyInputError("taxonomy_source_incomplete")
    try:
        provenance = CatalogueProvenance(
            kind=kind,
            canonical_uri=row["canonical_uri"],
            snapshot_version=metadata.get("taxonomy_version"),
            content_sha256=row["content_hash"],
            revision_id=revision_id,
            document_id=UUID(row["document_id"]),
            source_id=UUID(row["source_id"]),
        )
    except (ValidationError, ValueError):
        raise TaxonomyInputError("taxonomy_provenance_invalid") from None
    _require_input_scopes(session, access_scope, scope, (str(revision_id),))
    try:
        raw = store.read_verified(row["content_hash"])
    except FileNotFoundError:
        raise TaxonomyInputError("taxonomy_object_missing") from None
    except OSError:
        raise TaxonomyInputError("taxonomy_object_unavailable") from None
    except ValueError:
        raise TaxonomyInputError("taxonomy_object_integrity_invalid") from None
    if len(raw) != row["size_bytes"]:
        raise TaxonomyInputError("taxonomy_object_integrity_invalid")
    _require_input_scopes(session, access_scope, scope, (str(revision_id),))
    return (parse_cwe_catalogue if kind == "cwe" else parse_atlas_catalogue)(raw, provenance)
