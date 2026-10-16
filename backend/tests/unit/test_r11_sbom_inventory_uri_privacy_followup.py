"""独立复核的新编码定位符与重复引用红灯；既有33例输入/断言不变。"""

import hashlib
import json
from datetime import UTC, datetime
from urllib.parse import quote

import pytest

from ai_intel.assets.sbom_inventory import (
    SbomProjectionValidationError,
    _safe_http_uri,
    freeze_sbom_sidecar,
    parse_inventory_input,
    safe_sbom_sidecar,
)
from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse
from ai_intel.domain.access import AccessScope, Role


def parsed_document(**extra):
    private = "https://synthetic_user:synthetic_password@example.test/sbom"
    raw = json.dumps(
        {
            "bomFormat": "CycloneDX",
            "specVersion": "1.7",
            "components": [
                {"type": "library", "name": "a", "bom-ref": private},
                {"type": "library", "name": "b", "bom-ref": "public-b"},
                {"type": "library", "name": "c", "bom-ref": "public-c"},
            ],
            "dependencies": [{"ref": private, "dependsOn": ["public-b", "public-c"]}],
            **extra,
        },
        ensure_ascii=False,
    ).encode()
    now = datetime(2026, 10, 16, 0, tzinfo=UTC)
    result = parse_inventory_input(
        raw,
        manifest_format="cyclonedx_json",
        scope=AccessScope.for_authenticated_user("actor", "tenant", Role.TENANT_ADMIN),
        authorized_asset_tenant_id="tenant",
        asset_id="b7e76085-9ebe-4f8d-bd1c-356ee8e6d5d1",
        snapshot_number=1,
        source_version="synthetic-followup",
        observed_at=now,
        recorded_at=now,
    )
    assert result.sbom is not None
    return result


def encoded_key(layers):
    key = "https://synthetic_user:synthetic_password@example.test/sbom"
    for _ in range(layers):
        key = quote(key, safe="")
    return key


@pytest.mark.parametrize("layers", [5, 8])
def test_review_deep_encoding_is_not_a_public_source_locator(layers):
    key = encoded_key(layers)
    parsed = parsed_document(**{key: "synthetic opaque"})
    public = freeze_sbom_sidecar(parsed.sbom)
    assert key not in public.model_dump_json()
    assert "synthetic_password" not in public.model_dump_json()
    assert any("redacted-field:" in item for item in public.unmapped_field_locators)
    assert public.raw_sha256 == hashlib.sha256(parsed.manifest.source_bytes).hexdigest()
    assert public.combined_semantic_sha256 == parsed.sbom.combined_semantic_sha256
    assert safe_sbom_sidecar(public) == public


def test_review_every_repeated_locator_occurrence_must_match_bound_alias():
    payload = freeze_sbom_sidecar(parsed_document().sbom).model_dump(mode="json")
    assert (
        payload["dependency_edges"][0]["source_ref"] == payload["dependency_edges"][1]["source_ref"]
    )
    payload["dependency_edges"][1]["source_ref"] = "safe-public-ref"
    with pytest.raises(SbomProjectionValidationError):
        safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload))


@pytest.mark.parametrize("key", [encoded_key(1), encoded_key(4), encoded_key(12), encoded_key(64)])
def test_bounded_decoding_hides_uri_at_and_beyond_limit(key):
    public = freeze_sbom_sidecar(parsed_document(**{key: "opaque"}).sbom)
    assert key not in public.model_dump_json()
    assert any("redacted-field:" in item for item in public.unmapped_field_locators)
    assert safe_sbom_sidecar(public) == public


@pytest.mark.parametrize(
    "key",
    ["malformed%", "malformed%2", "malformed%GG", "%FF", "%C0%AF", "%ED%A0%80", "%00"],
)
def test_malformed_or_control_percent_encoding_has_typed_placeholder(key):
    public = freeze_sbom_sidecar(parsed_document(**{key: "opaque"}).sbom)
    assert key not in public.model_dump_json()
    assert any("redacted-field:" in item for item in public.unmapped_field_locators)
    assert safe_sbom_sidecar(public) == public


@pytest.mark.parametrize(
    "key", ["公开字段", "%E5%85%AC%E5%BC%80%E5%AD%97%E6%AE%B5", "public-field"]
)
def test_ordinary_unicode_and_public_keys_remain_visible(key):
    public = freeze_sbom_sidecar(parsed_document(**{key: "opaque"}).sbom)
    assert "/" + key in public.unmapped_field_locators


def test_distinct_encoded_source_keys_have_noncolliding_stable_locations():
    keys = [encoded_key(layers) for layers in (0, 1, 4, 5, 8)]
    public = freeze_sbom_sidecar(parsed_document(**dict.fromkeys(keys, "opaque")).sbom)
    locators = [item for item in public.unmapped_field_locators if "redacted-field:" in item]
    assert len(locators) == len(set(locators)) == len(keys)
    assert safe_sbom_sidecar(public) == public


@pytest.mark.parametrize("version", ["r11-sbom-sidecar-1", "r11-sbom-sidecar-2"])
def test_repeated_same_reference_is_readable_and_idempotent(version):
    parsed = parsed_document()
    public = freeze_sbom_sidecar(parsed.sbom)
    if version.endswith("1"):
        payload = public.model_dump()
        payload.update(schema_version=version, dependency_edges=parsed.sbom.dependency_edges)
        payload.update(component_sources=parsed.sbom.component_sources, redactions=())
        public = safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload))
    assert public.dependency_edges[0].source_ref == public.dependency_edges[1].source_ref
    assert public.dependency_edges[0].target_ref != public.dependency_edges[1].target_ref
    assert safe_sbom_sidecar(public) == public


@pytest.mark.parametrize("path", ["%FF", "%C0%AF", "%ED%A0%80", "%00", "%GG", "%2525252525252F"])
def test_http_path_invalid_unicode_or_unresolved_encoding_is_not_safe(path):
    assert not _safe_http_uri("https://example.test/" + path)
