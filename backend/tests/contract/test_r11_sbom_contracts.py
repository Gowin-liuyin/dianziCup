"""本地官方schema核验合成fixtures，offline registry禁止外部$ref抓取。"""

import gzip
import json
from pathlib import Path

import pytest
from jsonschema import Draft7Validator, FormatChecker
from referencing import Registry
from referencing.exceptions import NoSuchResource
from tests.unit.test_r11_sbom_parser import cdx_document, parse, spdx_document

from ai_intel.assets.inventory_contracts import AssetSnapshotResponse
from ai_intel.assets.sbom_parser import SbomValidationError

RUN = Path(__file__).resolve().parents[3] / "reports/runs/recovery_r11_sbom_adapters_20261016"


def prohibit_reference(uri):
    raise NoSuchResource(ref=uri)


def validate(document, name):
    schema = json.loads(gzip.decompress((RUN / (name + ".schema.json.gz")).read_bytes()))
    Draft7Validator(
        schema, registry=Registry(retrieve=prohibit_reference), format_checker=FormatChecker()
    ).validate(document)


@pytest.mark.parametrize("version", ["1.5", "1.6", "1.7"])
def test_official_cdx_schema_validates_supported_fixture_and_complete_03_projection(version):
    document = cdx_document(
        version, compositions=[{"aggregate": "complete", "assemblies": ["component-a"]}]
    )
    validate(document, "cyclonedx-" + version)
    result = parse(document)
    dto = AssetSnapshotResponse.model_validate(result.manifest.snapshot)
    assert dto.inventory_completeness == "unknown" and dto.declared_scope == ()
    assert result.completeness_declarations[0].aggregate == "complete"
    assert result.completeness_declarations[0].source_field_locator == "/compositions/0"


def test_official_spdx_maintenance_schema_validates_fixture_and_source_checksum():
    document = spdx_document()
    document["packages"][0]["checksums"] = [{"algorithm": "SHA256", "checksumValue": "a" * 64}]
    validate(document, "spdx-2.3.1")
    result = parse(document, "spdx_json")
    assert (
        result.component_sources[0].checksums[0].source_field_locator == "/packages/0/checksums/0"
    )
    assert result.manifest.snapshot.components[0].image_digest is None


@pytest.mark.parametrize("field", ["versionRange", "scope", "purl"])
def test_valid_standard_but_unrepresentable_features_are_explicitly_unsupported(field):
    document = cdx_document()
    if field == "versionRange":
        del document["components"][0]["version"]
        document["components"][0].update(isExternal=True, versionRange="vers:pypi/1.0|2.0")
    elif field == "scope":
        document["components"][0]["scope"] = "excluded"
    else:
        document["components"][0]["purl"] = "pkg:pypi/langchain@1.0?arch=x86"
    validate(document, "cyclonedx-1.7")
    with pytest.raises(SbomValidationError):
        parse(document)


def test_bom_schema_version_change_has_same_projection_but_distinct_complete_source_digest():
    first, second = parse(cdx_document("1.5")), parse(cdx_document("1.6"))
    assert first.manifest.snapshot.snapshot_sha256 == second.manifest.snapshot.snapshot_sha256
    assert first.combined_semantic_sha256 != second.combined_semantic_sha256


def test_license_and_comment_are_retained_as_raw_data_without_risk_interpretation():
    document = cdx_document()
    document["components"][0].update(
        licenses=[{"expression": "MIT"}], description="Not an absence of vulnerabilities."
    )
    validate(document, "cyclonedx-1.7")
    result = parse(document)
    assert "/components/0/licenses" in result.unmapped_field_locators
    assert "/components/0/description" in result.unmapped_field_locators
    assert b"MIT" in result.manifest.source_bytes
    assert result.manifest.snapshot.inventory_completeness == "unknown"


def test_spdx_external_document_and_relationship_remain_declarations_not_owned_components():
    document = spdx_document(
        externalDocumentRefs=[
            {
                "externalDocumentId": "DocumentRef-external",
                "spdxDocument": "https://example.test/spdx/external",
                "checksum": {"algorithm": "SHA1", "checksumValue": "b" * 40},
            }
        ],
        relationships=[
            {
                "spdxElementId": "SPDXRef-A",
                "relatedSpdxElement": "DocumentRef-external:SPDXRef-B",
                "relationshipType": "DEPENDS_ON",
            }
        ],
    )
    validate(document, "spdx-2.3.1")
    result = parse(document, "spdx_json")
    assert len(result.manifest.snapshot.components) == 1
    assert (
        result.external_documents[0].checksum.source_field_locator
        == "/externalDocumentRefs/0/checksum"
    )
    assert result.dependency_edges[0].target_ref == "DocumentRef-external:SPDXRef-B"


@pytest.mark.parametrize("version", ["1.6", "1.7"])
def test_official_provides_relationship_is_supported_in_both_versions(version):
    document = cdx_document(
        version, dependencies=[{"ref": "component-a", "provides": ["component-a"]}]
    )
    validate(document, "cyclonedx-" + version)
    result = parse(document)
    assert result.dependency_edges[0].relationship == "provides"
    assert result.dependency_edges[0].source_field_locator == "/dependencies/0/provides/0"


def test_provides_is_not_a_15_relationship():
    document = cdx_document(
        "1.5", dependencies=[{"ref": "component-a", "provides": ["component-a"]}]
    )
    with pytest.raises(SbomValidationError) as rejected:
        parse(document)
    assert rejected.value.code == "unsupported_dependency_relation"


@pytest.mark.parametrize("sentinel", ["NONE", "NOASSERTION"])
def test_spdx_unknown_relationship_target_is_a_declaration_only(sentinel):
    document = spdx_document(
        relationships=[
            {
                "spdxElementId": "SPDXRef-A",
                "relatedSpdxElement": sentinel,
                "relationshipType": "DEPENDS_ON",
            }
        ]
    )
    validate(document, "spdx-2.3.1")
    result = parse(document, "spdx_json")
    assert len(result.manifest.snapshot.components) == 1
    assert result.dependency_edges[0].target_ref == sentinel


def test_official_valid_dense_10000_has_explicit_shared_projection_budget_gap():
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
    validate(document, "cyclonedx-1.7")
    with pytest.raises(SbomValidationError) as rejected:
        parse(document)
    assert rejected.value.code == "projection_node_limit"
