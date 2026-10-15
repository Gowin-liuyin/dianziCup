"""合成SBOM fixtures的六类纯适配边界，不计生产/外部live。"""

import hashlib
import json
from datetime import UTC, datetime

import pytest

from ai_intel.assets.sbom_parser import SbomValidationError, parse_sbom
from ai_intel.domain.access import AccessScope, Role

ASSET_ID = "b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1"
NOW = datetime(2026, 10, 16, 0, tzinfo=UTC)
SCOPE = AccessScope.for_authenticated_user("synthetic-actor", "synthetic-tenant", Role.TENANT_ADMIN)


def cdx_document(version="1.7", components=None, **extra):
    return {
        "bomFormat": "CycloneDX",
        "specVersion": version,
        "version": 1,
        "components": components
        if components is not None
        else [
            {
                "type": "library",
                "name": "langchain",
                "version": "1.0",
                "purl": "pkg:pypi/langchain@1.0",
                "bom-ref": "component-a",
            },
        ],
        **extra,
    }


def spdx_document(packages=None, **extra):
    return {
        "spdxVersion": "SPDX-2.3",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": "Synthetic SBOM",
        "documentNamespace": "https://example.test/spdx/synthetic-1",
        "dataLicense": "CC0-1.0",
        "creationInfo": {"created": "2026-10-16T00:00:00Z", "creators": ["Tool: synthetic-test"]},
        "packages": packages
        if packages is not None
        else [
            {
                "SPDXID": "SPDXRef-A",
                "name": "langchain",
                "downloadLocation": "NOASSERTION",
                "filesAnalyzed": False,
                "versionInfo": "1.0",
                "externalRefs": [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": "pkg:pypi/langchain@1.0",
                    }
                ],
            }
        ],
        **extra,
    }


def parse(document, sbom_format="cyclonedx_json", **arguments):
    raw = (
        document
        if isinstance(document, bytes)
        else json.dumps(document, ensure_ascii=False).encode()
    )
    return parse_sbom(
        raw,
        sbom_format=sbom_format,
        scope=SCOPE,
        authorized_asset_tenant_id=SCOPE.tenant_id,
        asset_id=ASSET_ID,
        snapshot_number=arguments.pop("snapshot_number", 1),
        source_version="synthetic-sbom-1",
        observed_at=NOW,
        recorded_at=NOW,
        **arguments,
    )


@pytest.mark.parametrize("version", ["1.5", "1.6", "1.7"])
def test_cdx_supported_versions_project_real_fields_and_preserve_unknown(version):
    result = parse(cdx_document(version))
    component = result.manifest.snapshot.components[0]
    assert (
        component.ecosystem,
        component.package_name,
        component.version,
        component.version_scheme,
    ) == ("PyPI", "langchain", "1.0", "pep440")
    assert component.source_field_locator == "/components/0"
    assert component.image_digest is None and component.dependency_path is None
    assert result.manifest.snapshot.inventory_completeness == "unknown"
    assert (
        result.manifest.snapshot.configuration == ()
        and result.manifest.snapshot.tool_permissions is None
    )
    assert result.spec_version == version


def test_spdx_projects_package_refs_with_exact_source_locations():
    result = parse(spdx_document(), "spdx_json")
    component = result.manifest.snapshot.components[0]
    assert component.package_name == "langchain" and component.ecosystem == "PyPI"
    assert component.source_field_locator == "/packages/0"
    sources = {
        field.field_name: field.source_field_locator
        for field in result.component_sources[0].field_sources
    }
    assert sources["purl"] == "/packages/0/externalRefs/0/referenceLocator"
    assert sources["version"] == "/packages/0/versionInfo"


@pytest.mark.parametrize("sbom_format", ["cyclonedx_json", "spdx_json"])
def test_missing_direct_version_is_unknown_even_if_purl_contains_version(sbom_format):
    document = cdx_document() if sbom_format == "cyclonedx_json" else spdx_document()
    container = document["components"] if sbom_format == "cyclonedx_json" else document["packages"]
    del container[0]["version" if sbom_format == "cyclonedx_json" else "versionInfo"]
    result = parse(document, sbom_format)
    assert result.manifest.snapshot.components[0].version is None


def test_same_name_different_ecosystem_is_not_collapsed():
    result = parse(
        cdx_document(
            components=[
                {"type": "library", "name": "same", "purl": "pkg:pypi/same"},
                {"type": "library", "name": "same", "purl": "pkg:npm/same"},
            ]
        )
    )
    assert {component.ecosystem for component in result.manifest.snapshot.components} == {
        "PyPI",
        "npm",
    }
    assert len({component.component_id for component in result.manifest.snapshot.components}) == 2


def test_nested_assemblies_are_flattened_without_fabricating_dependency_path():
    result = parse(
        cdx_document(
            components=[
                {
                    "type": "application",
                    "name": "parent",
                    "bom-ref": "parent",
                    "components": [
                        {"type": "library", "name": "child", "bom-ref": "child"},
                    ],
                },
            ],
            dependencies=[{"ref": "parent", "dependsOn": ["child"]}],
        )
    )
    assert [component.package_name for component in result.manifest.snapshot.components] == [
        "parent",
        "child",
    ]
    assert (
        result.manifest.snapshot.components[1].source_field_locator == "/components/0/components/0"
    )
    assert all(
        component.dependency_path is None for component in result.manifest.snapshot.components
    )
    assert result.dependency_edges[0].relationship == "dependsOn"


@pytest.mark.parametrize("field", ["checksum", "graph", "composition", "comment"])
def test_sidecar_changes_do_not_disappear_behind_projection_hash(field):
    document = cdx_document(
        compositions=[{"aggregate": "unknown", "assemblies": ["component-a"]}],
        dependencies=[{"ref": "component-a", "dependsOn": []}],
    )
    original = parse(document)
    if field == "checksum":
        document["components"][0]["hashes"] = [{"alg": "SHA-256", "content": "a" * 64}]
    elif field == "graph":
        document["dependencies"][0]["dependsOn"] = ["component-a"]
    elif field == "composition":
        document["compositions"][0]["aggregate"] = "complete"
    else:
        document["components"][0]["description"] = "License commentary is not risk evidence."
    changed = parse(document)
    assert original.manifest.snapshot.snapshot_sha256 == changed.manifest.snapshot.snapshot_sha256
    assert original.sidecar_sha256 != changed.sidecar_sha256
    assert original.combined_semantic_sha256 != changed.combined_semantic_sha256
    assert original.raw_sha256 != changed.raw_sha256
    assert changed.manifest.snapshot.inventory_completeness == "unknown"


def test_original_unicode_bytes_hash_and_determinism_survive_projection():
    document = cdx_document()
    document["components"][0]["name"] = "LangChain 安全组件"
    raw = json.dumps(document, ensure_ascii=False, indent=2).encode()
    first, second = parse(raw), parse(raw)
    assert first.manifest.source_bytes == raw
    assert first.raw_sha256 == first.manifest.source_sha256 == hashlib.sha256(raw).hexdigest()
    assert first.manifest.snapshot.components[0].display_name == "LangChain 安全组件"
    assert first.combined_semantic_sha256 == second.combined_semantic_sha256
    assert first.manifest.snapshot.snapshot_id == second.manifest.snapshot.snapshot_id
    compact = parse(json.dumps(document, ensure_ascii=False, separators=(",", ":")).encode())
    assert compact.sidecar_sha256 == first.sidecar_sha256 and compact.raw_sha256 != first.raw_sha256


@pytest.mark.parametrize(
    "purl",
    ["pkg:pypi/langchain@2.0", "pkg:pypi/langchain@1.0?arch=x86", "pkg:pypi/langchain@1.0#src"],
)
def test_conflicting_version_and_unrepresentable_purl_are_typed_errors(purl):
    document = cdx_document()
    document["components"][0]["purl"] = purl
    with pytest.raises(SbomValidationError):
        parse(document)


def test_pep440_equivalent_versions_are_consistent_but_exact_text_is_preserved():
    document = cdx_document()
    document["components"][0]["version"] = "1.0.0"
    assert parse(document).manifest.snapshot.components[0].version == "1.0.0"


@pytest.mark.parametrize("version", ["1.4", "2.0", "1.7.1", None])
def test_unsupported_cdx_versions_do_not_return_empty_success(version):
    with pytest.raises(SbomValidationError) as rejected:
        parse(cdx_document(version))
    assert rejected.value.code == "unsupported_sbom_version"


def test_10000_minimal_components_pass_without_truncation():
    result = parse(
        cdx_document(
            components=[
                {"type": "library", "name": "package-" + str(index)} for index in range(10000)
            ]
        )
    )
    assert len(result.manifest.snapshot.components) == 10000


def test_10001_components_are_rejected_without_partial_result():
    with pytest.raises(SbomValidationError) as rejected:
        parse(
            cdx_document(
                components=[
                    {"type": "library", "name": "package-" + str(index)} for index in range(10001)
                ]
            )
        )
    assert rejected.value.code == "component_limit"


def test_legal_dense_10000_projection_limit_is_visible_not_lowered_or_truncated():
    document = cdx_document(
        components=[
            {
                "type": "library",
                "name": "p" + str(index),
                "purl": "pkg:pypi/p" + str(index),
                "version": "1",
            }
            for index in range(10000)
        ]
    )
    with pytest.raises(SbomValidationError) as rejected:
        parse(document)
    assert rejected.value.code == "projection_node_limit"


def test_unknown_json_field_pointer_escapes_unicode_slashes_and_tildes():
    document = cdx_document()
    document["配置/范围~"] = {"opaque": "值"}
    document["components"][0]["license/annotation~"] = "未知"
    result = parse(document)
    assert "/配置~1范围~0" in result.unmapped_field_locators
    assert "/components/0/license~1annotation~0" in result.unmapped_field_locators
    assert "未知" in result.manifest.source_bytes.decode()


@pytest.mark.parametrize("field", ["name", "purl"])
def test_frozen_parser_rejection_maps_to_actual_original_field(field):
    document = cdx_document()
    if field == "name":
        document["components"][0].pop("purl")
        document["components"][0]["name"] = ".."
    else:
        document["components"][0]["purl"] = "pkg:pypi/langchain@1!0"
        document["components"][0]["version"] = "1!0"
    with pytest.raises(SbomValidationError) as rejected:
        parse(document)
    assert rejected.value.locator == "/components/0/" + field


@pytest.mark.parametrize("sbom_format", ["cyclonedx_json", "spdx_json"])
def test_no_purl_leaves_ecosystem_and_scheme_unknown(sbom_format):
    document = cdx_document() if sbom_format == "cyclonedx_json" else spdx_document()
    component = (
        document["components"][0] if sbom_format == "cyclonedx_json" else document["packages"][0]
    )
    component.pop("purl" if sbom_format == "cyclonedx_json" else "externalRefs")
    result = parse(document, sbom_format).manifest.snapshot.components[0]
    assert result.ecosystem == result.version_scheme == "unknown"
    assert result.version == "1.0"


def test_spdx_unsupported_wire_version_and_conflicting_purl_are_typed():
    document = spdx_document(spdxVersion="SPDX-2.3.1")
    with pytest.raises(SbomValidationError) as rejected:
        parse(document, "spdx_json")
    assert rejected.value.code == "unsupported_sbom_version"
    document["spdxVersion"] = "SPDX-2.3"
    document["packages"][0]["externalRefs"][0]["referenceLocator"] = "pkg:pypi/langchain@2.0"
    with pytest.raises(SbomValidationError) as rejected:
        parse(document, "spdx_json")
    assert rejected.value.code == "conflicting_purl_version"
    assert rejected.value.locator == "/packages/0/externalRefs/0/referenceLocator"


def test_conflicting_component_versions_keep_both_and_original_issue_locators():
    document = spdx_document(
        packages=[
            {
                "name": "same",
                "SPDXID": "SPDXRef-A",
                "downloadLocation": "NOASSERTION",
                "versionInfo": "1.0",
            },
            {
                "name": "same",
                "SPDXID": "SPDXRef-B",
                "downloadLocation": "NOASSERTION",
                "versionInfo": "2.0",
            },
        ]
    )
    result = parse(document, "spdx_json")
    assert len(result.manifest.snapshot.components) == 2
    assert result.manifest.issues[0].code == "conflicting_component_versions"
    assert result.manifest.issues[0].locators == ("/packages/0", "/packages/1")
