"""Reviewer-owned assertions use saved official bytes without network or content copying."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.catalog_pages import normalize_avid_blob, normalize_catalog_page, select_avid_blob
from ai_intel.ingestion.sources.avid_records import normalize_avid_vulnerability
from ai_intel.ingestion.sources.github_releases import parse_github_releases
from ai_intel.ingestion.sources.repository import RepositoryFetchError

RUN = Path(__file__).resolve().parent
ORIGINALS = Path("D:/dianzi-runtime-cache/01a13a70-858c-7d92-8070-0b2693ad7fc4/r06-integrated-live-1156/diagnostic-originals")
RELEASE_HASH = "972aa16090d1bbeae02a8deb2c32352ff77be894754e998e7a8c7555b031a5cf"
AVID_HASH = "f8808b9479707e2b3ca074e569f9f678d692033c85767b387e15fbf31c3b246e"
TREE_HASH = "0c04c3689ee1cd32714083b8e066c8f10c06439ebd2b0c7a10b9a2c4ecb4b5e5"
PIN = {"tree_sha": "8eda5f4e6f74a3738eb980b795c4f813c6e52ca8", "record_offset": 1}
HEADERS = {"Link": '<https://api.github.com/repositories/658928958/releases?per_page=20&page=2>; rel="next", <https://api.github.com/repositories/658928958/releases?per_page=20&page=14>; rel="last"'}


def official_bytes(kind):
    name, digest, size = {"release": ("ollama_releases-1", RELEASE_HASH, 616207),
                          "avid": ("avid_community-4", AVID_HASH, 2860),
                          "tree": ("avid_community-3", TREE_HASH, None)}[kind]
    body = (ORIGINALS / (name + "-" + digest + ".body")).read_bytes()
    assert hashlib.sha256(body).hexdigest() == digest
    if size is not None:
        assert len(body) == size
    return body


def nodes(value):
    if isinstance(value, dict):
        return 1 + sum(1 + nodes(item) for item in value.values())
    if isinstance(value, list):
        return 1 + sum(nodes(item) for item in value)
    return 1


def release_fixture():
    return {"id": 999999999, "tag_name": "v1", "name": "Reviewer synthetic", "body": "review context",
            "draft": False, "prerelease": False, "published_at": "2026-10-14T00:00:00Z",
            "html_url": "https://github.com/ollama/ollama/releases/tag/v1"}


def test_saved_official_release_bytes_preserve_full_records_and_cursor():
    body = official_bytes("release")
    raw = json.loads(body)
    assert nodes(raw) == 24815
    assert nodes({"release": raw}) == 24817
    assert len(raw) == 20
    with pytest.raises(ValueError, match="structure outside limit"):
        strict_json_object(b'{"release":' + body + b'}', 2 * 1024 * 1024 + 13)
    page = normalize_catalog_page("ollama_releases", body, {}, HEADERS)
    assert page.next_cursor == {"page": 2}
    assert len(page.documents) == 20
    assert [json.loads(member.payload) for member in page.documents] == raw
    assert all(member.parsed.status == "parsed" for member in page.documents)
    assert all(member.metadata["risk_status"] == "not_assessed" for member in page.documents)
    (RUN / "release_observation.json").write_text(json.dumps({"sha256": RELEASE_HASH, "size_bytes": len(body), "source_nodes": nodes(raw),
        "wrapper_nodes": nodes({"release": raw}), "documents": 20, "block_counts": [len(x.parsed.blocks) for x in page.documents],
        "next_cursor": page.next_cursor, "network_calls": 0}, indent=2), encoding="utf-8")


def test_saved_official_avid_bytes_preserve_git_identity_and_reference_context():
    tree, body = official_bytes("tree"), official_bytes("avid")
    selection = select_avid_blob(tree, PIN)
    assert selection is not None
    member = normalize_avid_blob(selection, body)
    raw_envelope = json.loads(body)
    decoded = base64.b64decode(raw_envelope["content"])
    assert member.payload == decoded
    record = json.loads(decoded)
    assert record["data_version"] == "0.2"
    assert any(x["type"] == "screenshot" and x["url"] == "../img/R00031.png" for x in record["references"])
    assert member.metadata["git_tree_sha"] == PIN["tree_sha"]
    assert member.metadata["git_blob_sha"] == selection.blob_sha
    assert "../img/R00031.png" in member.parsed.normalized_text
    assert any("未获取或读取图片" in note for note in member.metadata["source_notes"])
    assert not any("R00031" in x for x in member.metadata["referenced_advisory_ids"])
    (RUN / "avid_observation.json").write_text(json.dumps({"envelope_sha256": AVID_HASH, "envelope_size_bytes": len(body),
        "tree_response_sha256": TREE_HASH, "tree_response_size_bytes": len(tree), "tree_sha": selection.tree_sha,
        "blob_sha": selection.blob_sha, "decoded_sha256": hashlib.sha256(decoded).hexdigest(), "decoded_size_bytes": len(decoded),
        "source_record_id": member.source_record_id, "path": selection.path, "next_cursor": selection.next_cursor,
        "referenced_advisory_ids": member.metadata["referenced_advisory_ids"], "block_count": len(member.parsed.blocks),
        "network_calls": 0, "screenshot_fetches": 0}, indent=2), encoding="utf-8")


@pytest.mark.parametrize("count", [50000, 50001])
def test_release_exact_node_ceiling(count):
    item = release_fixture()
    item["padding"] = []
    empty_count = nodes({"items": [item]})
    item["padding"] = [0] * (count - empty_count)
    body = json.dumps([item]).encode()
    assert nodes({"items": [item]}) == count
    if count == 50000:
        assert len(parse_github_releases(body)) == 1
        assert strict_json_object(b'{"items":' + body + b'}', 2 * 1024 * 1024 + 10, maximum_nodes=50000)["items"] == [item]
    else:
        with pytest.raises(RepositoryFetchError):
            normalize_catalog_page("ollama_releases", body, {})


@pytest.mark.parametrize("bad", [b'[{"id":1,"id":2}]', b'[{"x":NaN}]', b'[{"x":Infinity}]', b'[{"x":-Infinity}]',
                                 b'[{"x":1e400}]', b'[{"x":"\\u0000"}]', b'[{"x":"\\udfff"}]', b'[{"x":"\xff"}]'])
def test_release_malformed_boundary_stays_rejected(bad):
    with pytest.raises(RepositoryFetchError):
        normalize_catalog_page("ollama_releases", bad, {})


def test_release_two_mib_depth_and_model_default_do_not_move():
    with pytest.raises(RepositoryFetchError):
        normalize_catalog_page("ollama_releases", b'[]' + b' ' * (2 * 1024 * 1024 - 1), {})
    deep = 0
    for _ in range(33):
        deep = [deep]
    item = release_fixture()
    item["padding"] = deep
    with pytest.raises(RepositoryFetchError):
        normalize_catalog_page("ollama_releases", json.dumps([item]).encode(), {})
    with pytest.raises(ValueError, match="structure outside limit"):
        strict_json_object(json.dumps({"x": [0] * 10001}))


@pytest.mark.parametrize("uri", ["../../img/R00031.png", "../img/R00031.png/", "../img/R00031.png?x=1", "../img/R00031.png#x",
                                 "../img/R00031.png\r", "../img/R00031.png\x00", "../img/R00031.PNG", "/img/R00031.png",
                                 "../img/%52%30%30%30%33%31.png", "..\\img\\R00031.png", "../img/R00031.png/../../file",
                                 "//127.0.0.1/R00031.png", "http://10.0.0.1/R00031.png", "https://localhost/R00031.png",
                                 "https://user:password@example.org/R00031.png", "file:///img/R00031.png"])
def test_real_avid_mutated_unsafe_reference_is_rejected(uri):
    record = json.loads(base64.b64decode(json.loads(official_bytes("avid"))["content"]))
    screenshot = next(x for x in record["references"] if x["type"] == "screenshot")
    screenshot["url"] = uri
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(json.dumps(record).encode())


@pytest.mark.parametrize("kind", ["image", "website", "Screenshot", "screenshot "])
def test_real_avid_screenshot_path_requires_exact_type(kind):
    record = json.loads(base64.b64decode(json.loads(official_bytes("avid"))["content"]))
    next(x for x in record["references"] if x["type"] == "screenshot")["type"] = kind
    with pytest.raises(RepositoryFetchError):
        normalize_avid_vulnerability(json.dumps(record).encode())
