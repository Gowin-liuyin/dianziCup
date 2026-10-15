"""Synthetic source compatibility regressions keep model budgets and unsafe references closed."""

import base64
import hashlib
import json

import pytest

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.catalog_pages import (
    AvidBlobSelection,
    normalize_avid_blob,
    normalize_catalog_page,
)
from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.repository import RepositoryFetchError


def synthetic_release(identifier: int = 1, asset_count: int = 0) -> dict[str, object]:
    return {
        "id": identifier,
        "tag_name": "v1.0",
        "name": "Synthetic release",
        "body": "Synthetic release notes",
        "draft": False,
        "prerelease": False,
        "published_at": "2026-10-14T08:00:00Z",
        "html_url": "https://github.com/ollama/ollama/releases/tag/v1.0",
        "assets": [
            {
                "id": asset + 1,
                "name": "synthetic.bin",
                "size": 1,
                "url": "https://api.github.com/repos/ollama/ollama/releases/assets/1",
                "browser_download_url": (
                    "https://github.com/ollama/ollama/releases/download/v1.0/synthetic.bin"
                ),
                "uploader": {"id": 1, "login": "synthetic"},
            }
            for asset in range(asset_count)
        ],
    }


def test_release_page_over_model_node_budget_preserves_assets_and_next_page() -> None:
    original_items = [synthetic_release(identifier, 40) for identifier in range(1, 21)]
    body = json.dumps(original_items).encode()
    assert len(body) < 2 * 1024 * 1024
    with pytest.raises(ValueError, match="JSON structure outside limit"):
        strict_json_object(b'{"releases":' + body + b"}", 2 * 1024 * 1024 + 13)
    assert len(parse_github_releases(body)) == 20
    page = normalize_catalog_page(
        "ollama_releases",
        body,
        {},
        {
            "Link": (
                "<https://api.github.com/repositories/658928958/releases?per_page=20&page=2>; "
                'rel="next"'
            )
        },
    )
    assert len(page.documents) == 20
    assert page.next_cursor == {"page": 2}
    assert all(member.parsed.status == "parsed" for member in page.documents)
    assert [json.loads(member.payload) for member in page.documents] == original_items
    assert all(member.metadata["risk_status"] == "not_assessed" for member in page.documents)


def test_release_source_node_budget_remains_finite() -> None:
    release = synthetic_release()
    release["assets"] = [0] * 50001
    with pytest.raises(RepositoryFetchError):
        normalize_catalog_page("ollama_releases", json.dumps([release]).encode(), {})


def test_release_byte_and_depth_limits_remain_closed() -> None:
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(b"[]" + b" " * (2 * 1024 * 1024))
    release = synthetic_release()
    nested: object = 0
    for _ in range(33):
        nested = [nested]
    release["assets"] = nested
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(json.dumps([release]).encode())


@pytest.mark.parametrize(
    "bad",
    [
        b'[{"id":1,"id":2}]',
        b'[{"id":NaN}]',
        b'[{"id":"\\u0000"}]',
        b'[{"id":"\\ud800"}]',
        b'[{"id":"\xff"}]',
    ],
)
def test_release_invalid_json_still_fails(bad: bytes) -> None:
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(bad)


def test_model_json_default_is_still_ten_thousand_nodes() -> None:
    with pytest.raises(ValueError, match="JSON structure outside limit"):
        strict_json_object(json.dumps({"items": [0] * 10001}))


def synthetic_avid_record(
    reference_uri: object = "../img/R00031.png", reference_type: object = "screenshot"
) -> bytes:
    return json.dumps(
        {
            "data_type": "AVID",
            "data_version": "0.2",
            "metadata": {"vuln_id": "AVID-2026-V999"},
            "problemtype": {"description": {"lang": "en", "value": "Synthetic title"}},
            "description": {"lang": "en", "value": "Synthetic context body"},
            "references": [
                {
                    "type": reference_type,
                    "label": "Synthetic screenshot; CVE-2023-9999 is not an identity",
                    "url": reference_uri,
                }
            ],
        }
    ).encode()


def test_avid_relative_screenshot_preserves_original_context_without_advisory_identity() -> None:
    payload = synthetic_avid_record()
    article = normalize_avid_vulnerability(payload)
    assert article.article_id == "AVID-2026-V999"
    assert article.referenced_advisory_ids == ()
    assert article.body_text == "Synthetic context body"
    digest = hashlib.sha1(b"blob " + str(len(payload)).encode() + b"\0" + payload).hexdigest()
    envelope = json.dumps(
        {
            "sha": digest,
            "encoding": "base64",
            "size": len(payload),
            "content": base64.b64encode(payload).decode(),
        }
    ).encode()
    selection = AvidBlobSelection("a" * 40, digest, "vulnerabilities/2026/AVID-2026-V999.json", {})
    member = normalize_avid_blob(selection, envelope)
    assert member.payload == payload
    assert json.loads(member.payload)["data_version"] == "0.2"
    assert json.loads(member.payload)["references"][0]["type"] == "screenshot"
    assert "../img/R00031.png" in member.parsed.normalized_text
    assert member.metadata["referenced_advisory_ids"] == []
    assert member.metadata["source_adapter_version"] == "catalog-pages-3"
    notes = member.metadata["source_notes"]
    assert isinstance(notes, list)
    assert any(isinstance(note, str) and "未获取或读取图片" in note for note in notes)


@pytest.mark.parametrize(
    "reference_uri",
    [
        "../../img/R00031.png",
        "../img/../R00031.png",
        "../img/R00031.png?token=synthetic",
        "../img/R00031.png#fragment",
        "../img/R00031.png\n",
        "../img/R00031.png\x7f",
        "..\\img\\R00031.png",
        "../img/%52%30%30%30%33%31.png",
        "file:///img/R00031.png",
        "http://127.0.0.1/R00031.png",
        "https://example.com:8443/R00031.png",
        "https://user:synthetic@example.com/R00031.png",
        "../img/R00031.exe",
        "../img/R0031.png",
        "../img/R０００３１.png",
        None,
        17,
    ],
)
def test_avid_unknown_or_unsafe_relative_reference_still_fails(reference_uri: object) -> None:
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(synthetic_avid_record(reference_uri))


@pytest.mark.parametrize("reference_type", ["website", "image", "Screenshot", None, 1])
def test_avid_relative_image_requires_exact_screenshot_type(reference_type: object) -> None:
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(synthetic_avid_record(reference_type=reference_type))
