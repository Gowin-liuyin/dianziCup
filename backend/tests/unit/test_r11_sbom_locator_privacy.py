"""来源定位逐段校验；合成私有路径不得改变原文、摘要或安全字段。"""

import hashlib
from urllib.parse import quote

import pytest
from tests.unit.test_r11_sbom_inventory_uri_privacy_followup import parsed_document

from ai_intel.assets.sbom_inventory import (
    SbomProjectionValidationError,
    freeze_sbom_sidecar,
    safe_sbom_sidecar,
)
from ai_intel.assets.sbom_inventory_contracts import AssetSnapshotSbomResponse


def pointer_field(value: str) -> str:
    return value.replace("~", "~0").replace("/", "~1")


@pytest.mark.parametrize("key", ["../../private/sbom.json", "..\\..\\private\\sbom.json"])
def test_original_relative_private_path_key_is_redacted(key: str) -> None:
    parsed = parsed_document(**{key: "opaque"})
    public = freeze_sbom_sidecar(parsed.sbom)
    expected = "/redacted-field:" + hashlib.sha256(key.encode()).hexdigest()
    assert expected in public.unmapped_field_locators
    assert any(
        item.source_field_locator == expected
        and item.reason == "unsafe_uri_or_path"
        and item.replacement_ref is None
        for item in public.redactions
    )
    assert "private" not in public.model_dump_json()
    assert public.raw_sha256 == hashlib.sha256(parsed.manifest.source_bytes).hexdigest()
    assert public.combined_semantic_sha256 == parsed.sbom.combined_semantic_sha256
    assert safe_sbom_sidecar(public) == public


def test_original_placeholder_does_not_skip_later_uri_segment() -> None:
    payload = freeze_sbom_sidecar(parsed_document(components=[], dependencies=[]).sbom).model_dump(
        mode="json"
    )
    locator = (
        "/redacted-field:"
        + "a" * 64
        + "/postgresql:~1~1synthetic_user:synthetic_password@db.internal~1private"
    )
    payload["unmapped_field_locators"] = [locator]
    payload["redactions"] = [
        {"source_field_locator": locator, "reason": "unsafe_uri_or_path", "replacement_ref": None}
    ]
    with pytest.raises(SbomProjectionValidationError):
        safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload))


@pytest.mark.parametrize(
    "key",
    [
        ".",
        "..",
        "./private",
        "../private",
        "private/sbom.json",
        "private\\sbom.json",
        "a/../private",
        "a\\..\\private",
        "C:private",
        "~/private",
        "\\\\db\\private",
        "postgresql://synthetic_user:synthetic_password@db.internal/private",
        " postgresql:synthetic_password@db.internal",
        "synthetic_user:synthetic_password@db.internal",
        " .. ",
        "pkg:generic/../../private",
        "pkg:npm/%2e%2e/private",
        "field\x1f",
        "%2E%2E%2Fprivate",
        "%252E%252E%255Cprivate",
        "%2525252525252e%2525252525252e",
    ],
)
def test_unsafe_raw_field_has_stable_placeholder(key: str) -> None:
    parsed = parsed_document(**{key: {"public-child": "opaque"}})
    public = freeze_sbom_sidecar(parsed.sbom)
    expected = "/redacted-field:" + hashlib.sha256(key.encode()).hexdigest()
    assert expected in public.unmapped_field_locators
    assert safe_sbom_sidecar(public) == public
    assert parsed.manifest.source_bytes.decode().find("opaque") >= 0


def test_legacy_nested_locator_preserves_every_safe_segment() -> None:
    payload = freeze_sbom_sidecar(parsed_document(components=[], dependencies=[]).sbom).model_dump(
        mode="json"
    )
    payload.update(schema_version="r11-sbom-sidecar-1", redactions=[])
    payload["unmapped_field_locators"] = ["/public-parent/..~1private/0/public-child"]
    public = safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload))
    expected = (
        "/public-parent/redacted-field:"
        + hashlib.sha256(b"../private").hexdigest()
        + "/0/public-child"
    )
    assert public.unmapped_field_locators == (expected,)
    assert safe_sbom_sidecar(public) == public


@pytest.mark.parametrize(
    "key",
    ["public-field", "公开字段", "0", "1.2", "pkg:pypi/a@1.0", "pkg:npm/public/pkg@1.0", "a~b"],
)
def test_safe_field_purl_and_numeric_index_remain_visible(key: str) -> None:
    public = freeze_sbom_sidecar(parsed_document(**{key: "opaque"}).sbom)
    assert "/" + pointer_field(key) in public.unmapped_field_locators
    assert safe_sbom_sidecar(public) == public


@pytest.mark.parametrize(
    "tail", ["../private", "private\\file", "postgresql://u:p@db.internal/private", "%00", "%FF"]
)
@pytest.mark.parametrize("placeholder_first", [True, False])
def test_all_marked_segments_are_checked(tail: str, placeholder_first: bool) -> None:
    payload = freeze_sbom_sidecar(parsed_document(components=[], dependencies=[]).sbom).model_dump(
        mode="json"
    )
    placeholder = "redacted-field:" + "a" * 64
    fields = [placeholder, pointer_field(tail)]
    if not placeholder_first:
        fields.reverse()
    locator = "/" + "/".join(fields)
    payload["unmapped_field_locators"] = [locator]
    payload["redactions"] = [
        {"source_field_locator": locator, "reason": "unsafe_uri_or_path", "replacement_ref": None}
    ]
    with pytest.raises(SbomProjectionValidationError):
        safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload))


@pytest.mark.parametrize(
    "spoof", ["missing", "alias", "upper_hash", "short_hash", "escape", "extra"]
)
def test_placeholder_requires_canonical_exact_server_marker(spoof: str) -> None:
    payload = freeze_sbom_sidecar(parsed_document(**{"../private": "opaque"}).sbom).model_dump(
        mode="json"
    )
    if spoof == "missing":
        payload["redactions"] = []
    elif spoof == "alias":
        payload["redactions"][-1]["replacement_ref"] = "redacted-ref:" + "b" * 64
    elif spoof in {"upper_hash", "short_hash", "escape"}:
        tail = {"upper_hash": "A" * 64, "short_hash": "a" * 63, "escape": "a" * 64 + "~2"}[spoof]
        locator = "/redacted-field:" + tail
        payload["unmapped_field_locators"] = [locator]
        payload["redactions"] = [
            {
                "source_field_locator": locator,
                "reason": "unsafe_uri_or_path",
                "replacement_ref": None,
            }
        ]
    else:
        payload["redactions"].append(
            {
                "source_field_locator": "/unused",
                "reason": "unsafe_uri_or_path",
                "replacement_ref": None,
            }
        )
    with pytest.raises(SbomProjectionValidationError):
        safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload))


def test_literal_generated_field_prefix_cannot_collide_with_private_key() -> None:
    private = "../private"
    literal = "redacted-field:" + hashlib.sha256(private.encode()).hexdigest()
    public = freeze_sbom_sidecar(parsed_document(**{private: "opaque", literal: "opaque"}).sbom)
    expected = {
        "/redacted-field:" + hashlib.sha256(key.encode()).hexdigest() for key in (private, literal)
    }
    assert expected <= set(public.unmapped_field_locators)
    assert safe_sbom_sidecar(public) == public


@pytest.mark.parametrize("layers", [1, 4, 5, 8])
def test_encoded_relative_path_has_distinct_original_key_hash(layers: int) -> None:
    key = "../private/sbom.json"
    for _ in range(layers):
        key = quote(key, safe="")
    public = freeze_sbom_sidecar(parsed_document(**{key: "opaque"}).sbom)
    assert (
        "/redacted-field:" + hashlib.sha256(key.encode()).hexdigest()
        in public.unmapped_field_locators
    )


@pytest.mark.parametrize(
    "field", ["source_field_locator", "field_source", "checksum", "edge", "composition"]
)
def test_known_typed_locators_cannot_hide_unsafe_segments(field: str) -> None:
    payload = freeze_sbom_sidecar(parsed_document().sbom).model_dump(mode="json")
    locator = "/components/0/..~1private"
    if field == "source_field_locator":
        payload["component_sources"][0]["source_field_locator"] = locator
    elif field == "field_source":
        payload["component_sources"][0]["field_sources"][0]["source_field_locator"] = locator
    elif field == "checksum":
        payload["component_sources"][0]["checksums"] = [
            {"algorithm": "SHA256", "checksum_value": "c" * 64, "source_field_locator": locator}
        ]
    elif field == "edge":
        payload["dependency_edges"][0]["source_field_locator"] = locator
    else:
        payload["completeness_declarations"] = [
            {
                "aggregate": "unknown",
                "assemblies": [],
                "dependencies": [],
                "vulnerabilities": [],
                "source_field_locator": locator,
            }
        ]
    with pytest.raises(SbomProjectionValidationError):
        safe_sbom_sidecar(AssetSnapshotSbomResponse.model_validate(payload))
