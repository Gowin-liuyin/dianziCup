"""有界SBOM库存投影与原声明sidecar；不是全规范validator或库存生产接线。"""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, replace
from datetime import datetime
from typing import NoReturn

from packageurl import PackageURL, ValidationSeverity

from ai_intel.assessment.version_ranges import compare_versions
from ai_intel.assets.manifest_parser import (
    MAX_COMPONENTS,
    MAX_JSON_DEPTH,
    MAX_JSON_NODES,
    MAX_STRING_LENGTH,
    ManifestParseResult,
    ManifestValidationError,
    parse_manifest,
)
from ai_intel.domain.access import READ_ASSET, AccessScope, PermissionDeniedError

SBOM_ADAPTER_VERSION = "r11-sbom-adapter-1"
MAX_SBOM_BYTES = 1048576
MAX_SBOM_NODES = 200000
CDX_VERSIONS = frozenset({"1.5", "1.6", "1.7"})
CDX_TYPES = frozenset(
    {
        "application",
        "framework",
        "library",
        "container",
        "platform",
        "operating-system",
        "device",
        "device-driver",
        "firmware",
        "file",
        "machine-learning-model",
        "data",
    }
)
CDX_HASH_ALGORITHMS = frozenset(
    {
        "MD5",
        "SHA-1",
        "SHA-256",
        "SHA-384",
        "SHA-512",
        "SHA3-256",
        "SHA3-384",
        "SHA3-512",
        "BLAKE2b-256",
        "BLAKE2b-384",
        "BLAKE2b-512",
        "BLAKE3",
    }
)
SPDX_HASH_ALGORITHMS = frozenset(
    {
        "SHA1",
        "BLAKE3",
        "SHA3-384",
        "SHA256",
        "SHA384",
        "BLAKE2b-512",
        "BLAKE2b-256",
        "SHA3-512",
        "MD2",
        "ADLER32",
        "MD4",
        "SHA3-256",
        "BLAKE2b-384",
        "SHA512",
        "MD6",
        "MD5",
        "SHA224",
    }
)
HASH_LENGTHS = {
    "MD2": 32,
    "MD4": 32,
    "MD5": 32,
    "ADLER32": 8,
    "SHA1": 40,
    "SHA-1": 40,
    "SHA224": 56,
    "SHA256": 64,
    "SHA-256": 64,
    "SHA384": 96,
    "SHA-384": 96,
    "SHA512": 128,
    "SHA-512": 128,
    "SHA3-256": 64,
    "SHA3-384": 96,
    "SHA3-512": 128,
    "BLAKE2b-256": 64,
    "BLAKE2b-384": 96,
    "BLAKE2b-512": 128,
    "BLAKE3": 64,
    "Streebog-256": 64,
    "Streebog-512": 128,
}
CDX_AGGREGATES = frozenset(
    {
        "complete",
        "incomplete",
        "incomplete_first_party_only",
        "incomplete_first_party_proprietary_only",
        "incomplete_first_party_opensource_only",
        "incomplete_third_party_only",
        "incomplete_third_party_proprietary_only",
        "incomplete_third_party_opensource_only",
        "unknown",
        "not_specified",
    }
)
SPDX_RELATIONSHIPS = frozenset(
    {
        "VARIANT_OF",
        "COPY_OF",
        "PATCH_FOR",
        "TEST_DEPENDENCY_OF",
        "CONTAINED_BY",
        "DATA_FILE_OF",
        "OPTIONAL_COMPONENT_OF",
        "ANCESTOR_OF",
        "GENERATES",
        "CONTAINS",
        "OPTIONAL_DEPENDENCY_OF",
        "FILE_ADDED",
        "REQUIREMENT_DESCRIPTION_FOR",
        "DEV_DEPENDENCY_OF",
        "DEPENDENCY_OF",
        "BUILD_DEPENDENCY_OF",
        "DESCRIBES",
        "PREREQUISITE_FOR",
        "HAS_PREREQUISITE",
        "PROVIDED_DEPENDENCY_OF",
        "DYNAMIC_LINK",
        "DESCRIBED_BY",
        "METAFILE_OF",
        "DEPENDENCY_MANIFEST_OF",
        "PATCH_APPLIED",
        "RUNTIME_DEPENDENCY_OF",
        "TEST_OF",
        "TEST_TOOL_OF",
        "DEPENDS_ON",
        "SPECIFICATION_FOR",
        "FILE_MODIFIED",
        "DISTRIBUTION_ARTIFACT",
        "AMENDS",
        "DOCUMENTATION_OF",
        "GENERATED_FROM",
        "STATIC_LINK",
        "OTHER",
        "BUILD_TOOL_OF",
        "TEST_CASE_OF",
        "PACKAGE_OF",
        "DESCENDANT_OF",
        "FILE_DELETED",
        "EXPANDED_FROM_ARCHIVE",
        "DEV_TOOL_OF",
        "EXAMPLE_OF",
    }
)


class SbomValidationError(ManifestValidationError):
    """固定格式/兼容/来源位置错误，不回显原文或第三方解析器异常。"""


@dataclass(frozen=True)
class SbomFieldSource:
    field_name: str
    source_field_locator: str


@dataclass(frozen=True)
class SbomChecksum:
    algorithm: str
    checksum_value: str
    source_field_locator: str


@dataclass(frozen=True)
class SbomComponentSource:
    component_id: str
    source_ref: str | None
    component_type: str | None
    source_field_locator: str
    field_sources: tuple[SbomFieldSource, ...]
    checksums: tuple[SbomChecksum, ...]


@dataclass(frozen=True)
class SbomDependencyEdge:
    source_ref: str
    target_ref: str
    relationship: str
    source_field_locator: str


@dataclass(frozen=True)
class SbomCompletenessDeclaration:
    aggregate: str
    assemblies: tuple[str, ...]
    dependencies: tuple[str, ...]
    vulnerabilities: tuple[str, ...]
    source_field_locator: str


@dataclass(frozen=True)
class SbomExternalDocument:
    document_ref: str
    document_uri: str
    checksum: SbomChecksum
    source_field_locator: str


@dataclass(frozen=True)
class SbomParseResult:
    """投影hash不是完整SBOM变更hash；combined含保守全JSON结构sidecar，raw标精确原bytes。"""

    manifest: ManifestParseResult
    spec_version: str
    component_sources: tuple[SbomComponentSource, ...]
    dependency_edges: tuple[SbomDependencyEdge, ...]
    completeness_declarations: tuple[SbomCompletenessDeclaration, ...]
    external_documents: tuple[SbomExternalDocument, ...]
    unmapped_field_locators: tuple[str, ...]
    sidecar_sha256: str
    combined_semantic_sha256: str
    raw_sha256: str


@dataclass(frozen=True)
class _ProjectedComponent:
    manifest_fields: dict[str, object]
    source_ref: str | None
    component_type: str | None
    locator: str
    field_sources: tuple[SbomFieldSource, ...]
    checksums: tuple[SbomChecksum, ...]


def _object(value: object, locator: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise SbomValidationError("invalid_field_type", locator)
    return {key: child for key, child in value.items()}


def _array(value: object, locator: str) -> list[object]:
    if not isinstance(value, list):
        raise SbomValidationError("invalid_field_type", locator)
    return list(value)


def _text(value: object, locator: str) -> str:
    if not isinstance(value, str) or not value or len(value) > MAX_STRING_LENGTH:
        raise SbomValidationError("invalid_string", locator)
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise SbomValidationError("invalid_string", locator)
    return value


def _text_array(value: object, locator: str) -> tuple[str, ...]:
    values = _array(value, locator)
    if len(values) > MAX_COMPONENTS:
        raise SbomValidationError("reference_limit", locator)
    result = tuple(_text(child, f"{locator}/{index}") for index, child in enumerate(values))
    if len(set(result)) != len(result):
        raise SbomValidationError("duplicate_reference", locator)
    return result


def _field_locator(parent: str, field: str) -> str:
    return parent + "/" + field.replace("~", "~0").replace("/", "~1")


def _json(raw: bytes) -> dict[str, object]:
    """独立200000节点预算保留10000最小CDX组件；重复键规则与原严格JSON一致。"""

    def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in entries:
            if key in result:
                raise SbomValidationError("duplicate_json_key")
            result[key] = value
        return result

    def constant(value: str) -> NoReturn:
        raise SbomValidationError("non_finite_json_number")

    try:
        payload: object = json.loads(
            raw.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant
        )
    except SbomValidationError:
        raise
    except (ValueError, UnicodeError, RecursionError):
        raise SbomValidationError("invalid_json") from None
    pending: list[tuple[object, int]] = [(payload, 0)]
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > MAX_JSON_DEPTH:
            raise SbomValidationError("json_depth_limit")
        if count > MAX_SBOM_NODES:
            raise SbomValidationError("json_node_limit")
        if isinstance(value, str):
            try:
                value.encode("utf-8")
            except UnicodeError:
                raise SbomValidationError("invalid_json_unicode") from None
            if "\0" in value:
                raise SbomValidationError("invalid_json_unicode")
        elif isinstance(value, float) and not math.isfinite(value):
            raise SbomValidationError("non_finite_json_number")
        elif isinstance(value, dict):
            if {"$ref", "$dynamicRef"} & set(value):
                raise SbomValidationError("unsupported_json_reference")
            pending.extend((key, depth + 1) for key in value)
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
    result = _object(payload, "/")
    if {
        "tenant_id",
        "user_id",
        "role",
        "file_path",
        "server_path",
        "authorization",
        "api_key",
        "password",
    } & set(result):
        raise SbomValidationError("unsupported_identity_or_path_field")
    return result


def _checksums(value: object, locator: str, *, cdx_version: str | None) -> tuple[SbomChecksum, ...]:
    values = _array(value, locator)
    allowed = SPDX_HASH_ALGORITHMS if cdx_version is None else CDX_HASH_ALGORITHMS
    if cdx_version == "1.7":
        allowed = allowed | {"Streebog-256", "Streebog-512"}
    result: list[SbomChecksum] = []
    seen: dict[str, str] = {}
    for index, item in enumerate(values):
        position = f"{locator}/{index}"
        record = _object(item, position)
        algorithm_key, value_key = (
            ("algorithm", "checksumValue") if cdx_version is None else ("alg", "content")
        )
        if set(record) != {algorithm_key, value_key}:
            raise SbomValidationError("invalid_checksum_fields", position)
        algorithm = _text(record.get(algorithm_key), position + "/" + algorithm_key)
        digest = _text(record.get(value_key), position + "/" + value_key)
        if algorithm not in allowed or not re.fullmatch(r"[0-9a-fA-F]+", digest):
            raise SbomValidationError("invalid_checksum", position)
        expected_length = HASH_LENGTHS.get(algorithm)
        if expected_length is not None and len(digest) != expected_length:
            raise SbomValidationError("invalid_checksum_length", position)
        digest = digest.lower()
        if algorithm in seen and seen[algorithm] != digest:
            raise SbomValidationError("conflicting_checksums", position)
        seen[algorithm] = digest
        result.append(SbomChecksum(algorithm, digest, position))
    return tuple(result)


def _project_component(
    record: dict[str, object], locator: str, *, cdx_version: str | None
) -> _ProjectedComponent:
    name = _text(record.get("name"), locator + "/name")
    version_key = "version" if cdx_version is not None else "versionInfo"
    version = (
        _text(record[version_key], locator + "/" + version_key) if version_key in record else None
    )
    field_sources = [SbomFieldSource("package_name", locator + "/name")]
    component_type = None
    reference = None
    purl = None
    purl_locator = locator + "/purl"
    if cdx_version is not None:
        component_type = _text(record.get("type"), locator + "/type")
        types = CDX_TYPES if cdx_version == "1.5" else CDX_TYPES | {"cryptographic-asset"}
        if component_type not in types:
            raise SbomValidationError("unsupported_component_type", locator + "/type")
        if "scope" in record and record["scope"] != "required":
            raise SbomValidationError("unsupported_component_scope", locator + "/scope")
        if "isExternal" in record:
            if cdx_version != "1.7" or type(record["isExternal"]) is not bool:
                raise SbomValidationError("invalid_external_component", locator + "/isExternal")
            if record["isExternal"]:
                raise SbomValidationError("unsupported_external_component", locator + "/isExternal")
        if "versionRange" in record:
            raise SbomValidationError(
                "unsupported_component_version_range", locator + "/versionRange"
            )
        if "bom-ref" in record:
            reference = _text(record["bom-ref"], locator + "/bom-ref")
        if "purl" in record:
            purl = _text(record["purl"], purl_locator)
        checksum_values = record.get("hashes", [])
        checksum_locator = locator + "/hashes"
    else:
        reference = _text(record.get("SPDXID"), locator + "/SPDXID")
        if not re.fullmatch(r"SPDXRef-[A-Za-z0-9.-]+", reference):
            raise SbomValidationError("invalid_spdx_id", locator + "/SPDXID")
        _text(record.get("downloadLocation"), locator + "/downloadLocation")
        if "filesAnalyzed" in record and type(record["filesAnalyzed"]) is not bool:
            raise SbomValidationError("invalid_field_type", locator + "/filesAnalyzed")
        for index, child in enumerate(
            _array(record.get("externalRefs", []), locator + "/externalRefs")
        ):
            position = f"{locator}/externalRefs/{index}"
            external = _object(child, position)
            category = _text(external.get("referenceCategory"), position + "/referenceCategory")
            reference_type = _text(external.get("referenceType"), position + "/referenceType")
            external_locator = _text(
                external.get("referenceLocator"), position + "/referenceLocator"
            )
            if category not in {
                "OTHER",
                "PERSISTENT-ID",
                "PERSISTENT_ID",
                "SECURITY",
                "PACKAGE-MANAGER",
                "PACKAGE_MANAGER",
            }:
                raise SbomValidationError("invalid_external_reference_category", position)
            if reference_type == "purl":
                if category not in {"PACKAGE-MANAGER", "PACKAGE_MANAGER"}:
                    raise SbomValidationError("invalid_purl_reference_category", position)
                if purl is not None:
                    raise SbomValidationError("ambiguous_purl_reference", position)
                purl, purl_locator = external_locator, position + "/referenceLocator"
        checksum_values = record.get("checksums", [])
        checksum_locator = locator + "/checksums"
    fields: dict[str, object] = {"package_name": name}
    if version is not None:
        fields["version"] = version
        field_sources.append(SbomFieldSource("version", locator + "/" + version_key))
    if purl is not None:
        try:
            parsed = PackageURL.from_string(purl)
            if any(
                message.severity == ValidationSeverity.ERROR
                for message in parsed.validate(strict=True)
            ):
                raise ValueError("invalid purl")
        except (ValueError, TypeError):
            raise SbomValidationError("invalid_purl", purl_locator) from None
        if parsed.qualifiers or parsed.subpath:
            raise SbomValidationError("unsupported_purl_features", purl_locator)
        ecosystem = {"pypi": "PyPI", "npm": "npm"}.get(parsed.type, parsed.type)
        package_name = parsed.name if not parsed.namespace else parsed.namespace + "/" + parsed.name
        if not re.fullmatch(r"[A-Za-z0-9@._/-]+", package_name):
            raise SbomValidationError("unsupported_package_name", purl_locator)
        if version is not None and parsed.version is not None and version != parsed.version:
            scheme = {"PyPI": "pep440", "npm": "semver"}.get(ecosystem, "unknown")
            comparison = compare_versions(
                version, parsed.version, scheme=scheme, ecosystem=ecosystem
            )
            if comparison.ordering != 0:
                raise SbomValidationError("conflicting_purl_version", purl_locator)
        fields.update(ecosystem=ecosystem, package_name=package_name, purl=purl)
        field_sources = [field for field in field_sources if field.field_name != "package_name"]
        field_sources.extend(
            [
                SbomFieldSource("package_name", purl_locator),
                SbomFieldSource("ecosystem", purl_locator),
                SbomFieldSource("purl", purl_locator),
            ]
        )
        if name != package_name:
            fields["display_name"] = name
            field_sources.append(SbomFieldSource("display_name", locator + "/name"))
    elif not re.fullmatch(r"[A-Za-z0-9@._/-]+", name):
        raise SbomValidationError("unsupported_package_name", locator + "/name")
    return _ProjectedComponent(
        fields,
        reference,
        component_type,
        locator,
        tuple(field_sources),
        _checksums(checksum_values, checksum_locator, cdx_version=cdx_version),
    )


def _check_ref(
    reference: str,
    known: set[str],
    locator: str,
    *,
    external_documents: set[str] | None = None,
    allow_unknown: bool = False,
) -> None:
    if reference in known or (allow_unknown and reference in {"NONE", "NOASSERTION"}):
        return
    if external_documents is not None:
        parts = reference.split(":", 1)
        if (
            len(parts) == 2
            and parts[0] in external_documents
            and re.fullmatch(r"SPDXRef-[A-Za-z0-9.-]+", parts[1])
        ):
            return
    elif re.fullmatch(
        r"urn:cdx:[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[1-9][0-9]*#.+",
        reference,
    ):
        return
    raise SbomValidationError("unresolved_reference", locator)


def _cdx(
    document: dict[str, object],
) -> tuple[
    list[_ProjectedComponent],
    list[SbomDependencyEdge],
    list[SbomCompletenessDeclaration],
    list[SbomExternalDocument],
    set[str],
]:
    version = document.get("specVersion")
    if (
        document.get("bomFormat") != "CycloneDX"
        or not isinstance(version, str)
        or version not in CDX_VERSIONS
    ):
        raise SbomValidationError("unsupported_sbom_version", "/specVersion")
    if "version" in document and (type(document["version"]) is not int or document["version"] < 1):
        raise SbomValidationError("invalid_bom_revision", "/version")
    rows = _array(document.get("components", []), "/components")
    metadata = _object(document.get("metadata", {}), "/metadata")
    pending = [(child, f"/components/{index}") for index, child in reversed(list(enumerate(rows)))]
    if "component" in metadata:
        pending.append((metadata["component"], "/metadata/component"))
    projected: list[_ProjectedComponent] = []
    references: set[str] = set()
    unmapped: set[str] = {
        _field_locator("", key)
        for key in document
        if key
        not in {"bomFormat", "specVersion", "version", "components", "dependencies", "compositions"}
    }
    while pending:
        child, locator = pending.pop()
        record = _object(child, locator)
        component = _project_component(record, locator, cdx_version=version)
        projected.append(component)
        if len(projected) > MAX_COMPONENTS:
            raise SbomValidationError("component_limit", locator)
        if component.source_ref is not None:
            if component.source_ref in references:
                raise SbomValidationError("duplicate_component_reference", locator + "/bom-ref")
            references.add(component.source_ref)
        unmapped.update(
            _field_locator(locator, key)
            for key in record
            if key not in {"name", "type", "version", "purl", "bom-ref", "components", "hashes"}
        )
        children = _array(record.get("components", []), locator + "/components")
        pending.extend(
            (value, f"{locator}/components/{index}")
            for index, value in reversed(list(enumerate(children)))
        )
    for index, value in enumerate(_array(document.get("services", []), "/services")):
        service = _object(value, f"/services/{index}")
        if "bom-ref" in service:
            reference = _text(service["bom-ref"], f"/services/{index}/bom-ref")
            if reference in references:
                raise SbomValidationError(
                    "duplicate_component_reference", f"/services/{index}/bom-ref"
                )
            references.add(reference)
    edges: list[SbomDependencyEdge] = []
    for index, child in enumerate(_array(document.get("dependencies", []), "/dependencies")):
        locator = f"/dependencies/{index}"
        record = _object(child, locator)
        reference = _text(record.get("ref"), locator + "/ref")
        _check_ref(reference, references, locator + "/ref")
        for relationship in ("dependsOn", "provides"):
            if relationship == "provides" and version == "1.5" and relationship in record:
                raise SbomValidationError(
                    "unsupported_dependency_relation", locator + "/" + relationship
                )
            for target_index, target in enumerate(
                _text_array(record.get(relationship, []), locator + "/" + relationship)
            ):
                position = f"{locator}/{relationship}/{target_index}"
                _check_ref(target, references, position)
                edges.append(SbomDependencyEdge(reference, target, relationship, position))
    declarations: list[SbomCompletenessDeclaration] = []
    for index, child in enumerate(_array(document.get("compositions", []), "/compositions")):
        locator = f"/compositions/{index}"
        record = _object(child, locator)
        aggregate = _text(record.get("aggregate"), locator + "/aggregate")
        if aggregate not in CDX_AGGREGATES:
            raise SbomValidationError("invalid_composition_aggregate", locator + "/aggregate")
        assemblies = _text_array(record.get("assemblies", []), locator + "/assemblies")
        dependencies = _text_array(record.get("dependencies", []), locator + "/dependencies")
        for key, values in (("assemblies", assemblies), ("dependencies", dependencies)):
            for reference_index, reference in enumerate(values):
                _check_ref(reference, references, f"{locator}/{key}/{reference_index}")
        declarations.append(
            SbomCompletenessDeclaration(
                aggregate,
                assemblies,
                dependencies,
                _text_array(record.get("vulnerabilities", []), locator + "/vulnerabilities"),
                locator,
            )
        )
    return projected, edges, declarations, [], unmapped


def _spdx(
    document: dict[str, object],
) -> tuple[
    list[_ProjectedComponent],
    list[SbomDependencyEdge],
    list[SbomCompletenessDeclaration],
    list[SbomExternalDocument],
    set[str],
]:
    if document.get("spdxVersion") != "SPDX-2.3":
        raise SbomValidationError("unsupported_sbom_version", "/spdxVersion")
    if document.get("SPDXID") != "SPDXRef-DOCUMENT" or document.get("dataLicense") != "CC0-1.0":
        raise SbomValidationError("invalid_spdx_document", "/")
    _text(document.get("name"), "/name")
    _text(document.get("documentNamespace"), "/documentNamespace")
    creation = _object(document.get("creationInfo"), "/creationInfo")
    created = _text(creation.get("created"), "/creationInfo/created")
    try:
        if datetime.fromisoformat(created).utcoffset() is None:
            raise ValueError("timezone required")
    except (ValueError, OverflowError):
        raise SbomValidationError("invalid_creation_time", "/creationInfo/created") from None
    if not _text_array(creation.get("creators"), "/creationInfo/creators"):
        raise SbomValidationError("missing_creator", "/creationInfo/creators")
    rows = _array(document.get("packages", []), "/packages")
    if len(rows) > MAX_COMPONENTS:
        raise SbomValidationError("component_limit", "/packages")
    projected = [
        _project_component(
            _object(child, f"/packages/{index}"), f"/packages/{index}", cdx_version=None
        )
        for index, child in enumerate(rows)
    ]
    references = {"SPDXRef-DOCUMENT"}
    for component in projected:
        if component.source_ref in references:
            raise SbomValidationError(
                "duplicate_component_reference", component.locator + "/SPDXID"
            )
        if component.source_ref is not None:
            references.add(component.source_ref)
    for section in ("files", "snippets"):
        for index, child in enumerate(_array(document.get(section, []), "/" + section)):
            locator = f"/{section}/{index}/SPDXID"
            reference = _text(_object(child, locator).get("SPDXID"), locator)
            if not re.fullmatch(r"SPDXRef-[A-Za-z0-9.-]+", reference) or reference in references:
                raise SbomValidationError("invalid_or_duplicate_spdx_id", locator)
            references.add(reference)
    external_documents: list[SbomExternalDocument] = []
    external_ids: set[str] = set()
    for index, child in enumerate(
        _array(document.get("externalDocumentRefs", []), "/externalDocumentRefs")
    ):
        locator = f"/externalDocumentRefs/{index}"
        record = _object(child, locator)
        reference = _text(record.get("externalDocumentId"), locator + "/externalDocumentId")
        if not re.fullmatch(r"DocumentRef-[A-Za-z0-9.+-]+", reference) or reference in external_ids:
            raise SbomValidationError("invalid_external_document_id", locator)
        external_ids.add(reference)
        checksum = _checksums([record.get("checksum")], locator + "/checksum", cdx_version=None)[0]
        checksum = replace(checksum, source_field_locator=locator + "/checksum")
        external_documents.append(
            SbomExternalDocument(
                reference,
                _text(record.get("spdxDocument"), locator + "/spdxDocument"),
                checksum,
                locator,
            )
        )
    edges: list[SbomDependencyEdge] = []
    for index, child in enumerate(_array(document.get("relationships", []), "/relationships")):
        locator = f"/relationships/{index}"
        record = _object(child, locator)
        source = _text(record.get("spdxElementId"), locator + "/spdxElementId")
        target = _text(record.get("relatedSpdxElement"), locator + "/relatedSpdxElement")
        relationship = _text(record.get("relationshipType"), locator + "/relationshipType")
        if relationship not in SPDX_RELATIONSHIPS:
            raise SbomValidationError(
                "unsupported_relationship_type", locator + "/relationshipType"
            )
        _check_ref(source, references, locator + "/spdxElementId", external_documents=external_ids)
        _check_ref(
            target,
            references,
            locator + "/relatedSpdxElement",
            external_documents=external_ids,
            allow_unknown=True,
        )
        edges.append(SbomDependencyEdge(source, target, relationship, locator))
    for index, reference in enumerate(
        _text_array(document.get("documentDescribes", []), "/documentDescribes")
    ):
        _check_ref(
            reference, references, f"/documentDescribes/{index}", external_documents=external_ids
        )
    unmapped = {
        _field_locator("", key)
        for key in document
        if key
        not in {
            "spdxVersion",
            "packages",
            "relationships",
            "externalDocumentRefs",
            "documentDescribes",
        }
    }
    for index, child in enumerate(rows):
        unmapped.update(
            _field_locator(f"/packages/{index}", key)
            for key in _object(child, f"/packages/{index}")
            if key not in {"name", "versionInfo", "SPDXID", "checksums", "externalRefs"}
        )
    return projected, edges, [], external_documents, unmapped


def _original_locator(locator: str, projected: list[_ProjectedComponent], section: str) -> str:
    if locator == "/components":
        return section
    match = re.match(r"/components/([0-9]+)(.*)$", locator)
    if not match or int(match[1]) >= len(projected):
        return locator
    item = projected[int(match[1])]
    if not match[2]:
        return item.locator
    field_name = match[2].lstrip("/").split("/", 1)[0]
    return next(
        (
            source.source_field_locator
            for source in item.field_sources
            if source.field_name == field_name
        ),
        item.locator,
    )


def parse_sbom(
    raw_bytes: bytes,
    *,
    sbom_format: str,
    scope: AccessScope,
    authorized_asset_tenant_id: str,
    asset_id: str,
    snapshot_number: int,
    source_version: str,
    observed_at: datetime,
    recorded_at: datetime,
) -> SbomParseResult:
    """仅授权bytes→现有库存候选及声明sidecar；原完整性保持unknown，不读取引用或写PG。"""
    if not isinstance(scope, AccessScope):
        raise PermissionDeniedError("authenticated asset scope required")
    scope.requires(READ_ASSET)
    if not scope.tenant_id or not authorized_asset_tenant_id:
        raise PermissionDeniedError("tenant asset scope required")
    scope.enforce_visible("tenant", authorized_asset_tenant_id)
    if type(raw_bytes) is not bytes or not 1 <= len(raw_bytes) <= MAX_SBOM_BYTES:
        raise SbomValidationError("sbom_size_or_type_limit")
    if sbom_format not in {"cyclonedx_json", "spdx_json"}:
        raise SbomValidationError("unsupported_sbom_format")
    document = _json(raw_bytes)
    projected, edges, declarations, external_documents, unmapped = (
        _cdx(document) if sbom_format == "cyclonedx_json" else _spdx(document)
    )
    component_section = "/components" if sbom_format == "cyclonedx_json" else "/packages"
    manifest_value = {
        "format_version": 1,
        "components": [item.manifest_fields for item in projected],
    }
    normalized = json.dumps(manifest_value, ensure_ascii=True, separators=(",", ":")).encode()
    node_count = 5 + sum(1 + 2 * len(item.manifest_fields) for item in projected)
    if node_count > MAX_JSON_NODES:
        raise SbomValidationError(
            "projection_node_limit",
            component_section,
        )
    try:
        manifest = parse_manifest(
            normalized,
            manifest_format="json_manifest_v1",
            scope=scope,
            authorized_asset_tenant_id=authorized_asset_tenant_id,
            asset_id=asset_id,
            snapshot_number=snapshot_number,
            source_version=source_version,
            observed_at=observed_at,
            recorded_at=recorded_at,
        )
    except ManifestValidationError as rejected:
        locator = _original_locator(rejected.locator, projected, component_section)
        raise SbomValidationError(rejected.code, locator) from None
    components = tuple(
        replace(component, source_field_locator=item.locator)
        for component, item in zip(manifest.snapshot.components, projected, strict=True)
    )
    raw_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    manifest = replace(
        manifest,
        snapshot=replace(manifest.snapshot, components=components, source_kind=sbom_format),
        source_sha256=raw_sha256,
        parser_version=SBOM_ADAPTER_VERSION,
        source_bytes=raw_bytes,
        issues=tuple(
            replace(
                issue,
                locators=tuple(
                    _original_locator(locator, projected, component_section)
                    for locator in issue.locators
                ),
            )
            for issue in manifest.issues
        ),
    )
    sidecar_digest = hashlib.sha256(
        json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    combined_digest = hashlib.sha256(
        json.dumps(
            [SBOM_ADAPTER_VERSION, manifest.snapshot.snapshot_sha256, sidecar_digest],
            separators=(",", ":"),
        ).encode()
    ).hexdigest()
    sources = tuple(
        SbomComponentSource(
            component.component_id,
            item.source_ref,
            item.component_type,
            item.locator,
            item.field_sources,
            item.checksums,
        )
        for component, item in zip(components, projected, strict=True)
    )
    spec_version = (
        document["specVersion"] if sbom_format == "cyclonedx_json" else document["spdxVersion"]
    )
    if not isinstance(spec_version, str):
        raise SbomValidationError("unsupported_sbom_version")
    return SbomParseResult(
        manifest,
        spec_version,
        sources,
        tuple(edges),
        tuple(declarations),
        tuple(external_documents),
        tuple(sorted(unmapped)),
        sidecar_digest,
        combined_digest,
        raw_sha256,
    )
