"""Explicit synthetic diagnostic regressions; these are outside the product tests and live corpus."""

import json

import pytest

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.catalog_pages import normalize_catalog_page
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.repository import RepositoryFetchError


def synthetic_release(identifier=1, asset_count=0):
    return {
        "id": identifier, "tag_name": "v1.0", "name": "Synthetic release",
        "body": "Synthetic release notes", "draft": False, "prerelease": False,
        "published_at": "2026-10-14T08:00:00Z",
        "html_url": "https://github.com/ollama/ollama/releases/tag/v1.0",
        "assets": [{"id": asset + 1, "name": "synthetic.bin", "size": 1,
                    "url": "https://api.github.com/repos/ollama/ollama/releases/assets/1",
                    "browser_download_url": "https://github.com/ollama/ollama/releases/download/v1.0/synthetic.bin",
                    "uploader": {"id": 1, "login": "synthetic"}}
                   for asset in range(asset_count)],
    }


def test_legitimate_twenty_release_asset_metadata_can_exceed_model_node_default():
    body = json.dumps([synthetic_release(identifier, 40) for identifier in range(1, 21)]).encode()
    assert len(body) < 2 * 1024 * 1024
    with pytest.raises(ValueError, match="JSON structure outside limit"):
        strict_json_object(b'{"releases":' + body + b'}', 2 * 1024 * 1024 + 13)
    page = normalize_catalog_page("ollama_releases", body, {}, {
        "Link": '<https://api.github.com/repositories/658928958/releases?per_page=20&page=2>; rel="next"'
    })
    assert len(page.documents) == 20
    assert page.next_cursor == {"page": 2}
    assert all(member.parsed.status == "parsed" for member in page.documents)


def test_source_node_limit_must_remain_finite():
    release = synthetic_release()
    release["assets"] = [0] * 50001
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(json.dumps([release]).encode())


@pytest.mark.parametrize("bad", [
    b'[{"id":1,"id":2}]', b'[{"id":NaN}]', b'[{"id":"\\u0000"}]',
    b'[{"id":"\\ud800"}]', b'[{"id":"\xff"}]',
])
def test_invalid_json_does_not_become_success(bad):
    with pytest.raises(RepositoryFetchError):
        parse_github_releases(bad)


def test_model_default_still_rejects_ten_thousand_plus_nodes():
    with pytest.raises(ValueError, match="JSON structure outside limit"):
        strict_json_object(json.dumps({"items": [0] * 10001}))
