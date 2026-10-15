"""真实留档回放和显式合成分页，不把内部转换当产品live。"""

import base64
import hashlib
import json
from pathlib import Path

import pytest
from test_r04_real_parsing import make_pdf

from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.ingestion.catalog_pages import (
    normalize_avid_blob,
    normalize_catalog_page,
    select_avid_blob,
)
from ai_intel.ingestion.source_catalog import SourceCatalogError, build_catalog_request

ROOT = Path(__file__).resolve().parents[3]
FEEDS = ROOT / "reports/runs/recovery_r06_feed_parsers_20261015"
REPOSITORY = ROOT / "reports/runs/recovery_r06_repository_community_20261015"


def test_arxiv_archived_page_advances_by_actual_count_without_skipping_papers():
    page = normalize_catalog_page(
        "arxiv_security", (FEEDS / "doh_06_arxiv_ai_security.body").read_bytes(), {}
    )
    assert len(page.documents) == 2 and page.next_cursor == {"start": 2}
    first = page.documents[0]
    assert first.source_record_id == "arxiv:2609.05903"
    assert first.canonical_uri.endswith("2609.05903v2")
    assert first.kind.value == "paper" and first.metadata["content_coverage"] == "abstract"
    assert first.metadata["full_text_fetched"] is False
    assert first.published_at.isoformat() == "2026-09-05T05:56:41+00:00"
    assert "start=2" in build_catalog_request("arxiv_security", page.next_cursor).url


def test_feed_excerpt_and_missing_article_body_are_not_paper_or_fulltext():
    page = normalize_catalog_page(
        "trailofbits_blog", (FEEDS / "trailofbits_metadata_excerpt.xml").read_bytes(), {}
    )
    assert len(page.documents) == 20 and page.next_cursor == {}
    assert page.documents[0].metadata["content_coverage"] == "feed_excerpt"
    assert page.documents[1].metadata["content_coverage"] == "metadata"
    assert all(
        item.kind.value == "article" and item.metadata["full_text_fetched"] is False
        for item in page.documents
    )


def test_osv_offline_record_keeps_alias_relation_and_range_inputs_in_raw_document():
    record = json.loads((REPOSITORY / "osv_ollama_real.body").read_bytes())
    body = json.dumps({"vulns": [record]}).encode()
    page = normalize_catalog_page("osv_ollama", body, {})
    assert page.documents and page.documents[0].kind.value == "advisory"
    first = page.documents[0]
    assert "GHSA-fccc-8m69-8r78" in first.source_record_id
    assert "CVE-2025-0315" in first.metadata["aliases"]
    assert "last_affected" in first.payload.decode()


def test_release_offline_record_keeps_original_body_and_does_not_assert_a_vulnerability():
    page = normalize_catalog_page(
        "ollama_releases", (REPOSITORY / "ollama_release_real.body").read_bytes(), {}
    )
    assert len(page.documents) == 1
    member = page.documents[0]
    assert member.kind.value == "repository_record"
    assert member.source_record_id == "github:ollama/ollama:release:413093320"
    assert member.metadata["prerelease"] is True
    assert member.metadata["risk_status"] == "not_assessed"


def avid_tree(record_bytes):
    digest = hashlib.sha1(
        b"blob " + str(len(record_bytes)).encode() + b"\0" + record_bytes
    ).hexdigest()
    tree = {
        "sha": "a" * 40,
        "truncated": False,
        "tree": [
            {
                "path": "reports/2023/AVID-2023-R0001.json",
                "type": "blob",
                "sha": "b" * 40,
                "size": 12,
            },
            {
                "path": "vulnerabilities/2023/AVID-2023-V001.json",
                "type": "blob",
                "sha": digest,
                "size": len(record_bytes),
            },
        ],
    }
    return json.dumps(tree).encode(), digest


def test_avid_directory_is_not_a_document_and_blob_hash_and_date_precision_are_preserved():
    record = (REPOSITORY / "avid_02.record.json").read_bytes()
    body, digest = avid_tree(record)
    selected = select_avid_blob(body, {})
    assert selected is not None and selected.blob_sha == digest and selected.next_cursor == {}
    blob = json.dumps(
        {
            "sha": digest,
            "encoding": "base64",
            "size": len(record),
            "content": base64.b64encode(record).decode(),
        }
    ).encode()
    member = normalize_avid_blob(selected, blob)
    assert member.source_record_id == "AVID-2023-V001"
    assert member.payload == record and member.published_at is None
    assert member.metadata["published_precision"] == "calendar_date"
    assert member.metadata["published_at_raw"] == "2023-03-31"
    assert member.kind.value == "article" and member.canonical_uri.endswith(digest)


@pytest.mark.parametrize("mutation", ["truncated", "wrong_tree", "duplicate", "wrong_blob"])
def test_avid_incomplete_ambiguous_or_changed_snapshot_is_rejected(mutation):
    record = (REPOSITORY / "avid_02.record.json").read_bytes()
    body, digest = avid_tree(record)
    tree = json.loads(body)
    cursor = {}
    if mutation == "truncated":
        tree["truncated"] = True
    elif mutation == "wrong_tree":
        cursor = {"tree_sha": "c" * 40, "record_offset": 0}
    elif mutation == "duplicate":
        tree["tree"].append(tree["tree"][-1])
    else:
        selected = select_avid_blob(body, {})
        with pytest.raises(SourceCatalogError):
            normalize_avid_blob(
                selected,
                json.dumps(
                    {
                        "sha": digest,
                        "encoding": "base64",
                        "size": len(record),
                        "content": base64.b64encode(record + b" ").decode(),
                    }
                ).encode(),
            )
        return
    with pytest.raises(SourceCatalogError):
        select_avid_blob(json.dumps(tree).encode(), cursor)


def test_standard_pdf_keeps_real_page_coordinates_and_partial_is_explicit():
    body = make_pdf(
        (
            "NIST AI 100-1 Artificial Intelligence Risk Management Framework January 2023",
            None,
            "MAP GOVERN MEASURE MANAGE",
        )
    )
    page = normalize_catalog_page("nist_ai_rmf", body, {})
    member = page.documents[0]
    assert member.kind.value == "standard" and member.payload == body
    assert member.parsed.status == "partial"
    assert [block.page_number for block in member.parsed.blocks] == [1, 3]
    assert member.metadata["content_coverage"] != "full_text"


def test_policy_extracts_original_articles_without_fabricating_timezone_or_asset_applicability():
    ordinals = (
        "一",
        "二",
        "三",
        "四",
        "五",
        "六",
        "七",
        "八",
        "九",
        "十",
        "十一",
        "十二",
        "十三",
        "十四",
        "十五",
        "十六",
        "十七",
        "十八",
        "十九",
        "二十",
        "二十一",
        "二十二",
        "二十三",
        "二十四",
    )
    articles = "".join(f"<p>第{number}条 测试原文条款</p>" for number in ordinals[:-1])
    body = (
        '<html><head><meta name="ArticleTitle" content="生成式人工智能服务管理暂行办法">'
        '<meta name="PubDate" content="2023-07-13"></head><body>'
        '<nav>Unrelated navigation</nav><div class="main-content">'
        "<h1>生成式人工智能服务管理暂行办法</h1>"
        + articles
        + "<p><b>第二十四条</b> 本办法自2023年8月15日起施行。</p></div>"
        "<footer>Unrelated footer</footer></body></html>"
    ).encode()
    page = normalize_catalog_page("cac_generative_ai", body, {})
    member = page.documents[0]
    assert member.kind.value == "policy" and member.published_at is None
    assert member.metadata["published_at_raw"] == "2023-07-13"
    assert member.metadata["published_precision"] == "calendar_date"
    assert "Unrelated" not in member.parsed.normalized_text
    assert "第二十四条" in member.parsed.normalized_text


def test_actual_archived_policy_keeps_the_last_article_body_after_inline_heading():
    body = (ROOT / "fixtures/recorded/cac_generative_ai_20261015_public.html").read_bytes()
    member = normalize_catalog_page("cac_generative_ai", body, {}).documents[0]
    assert "本办法自2023年8月15日起施行" in member.parsed.normalized_text
    assert member.metadata["published_at_raw"] == "2023年07月13日 15:00"
    assert member.metadata["published_precision"] == "unknown"
    assert member.published_at is None


def test_source_tree_can_request_larger_bounded_json_without_relaxing_model_default():
    body = json.dumps({"items": list(range(11000))})
    with pytest.raises(ValueError):
        strict_json_object(body)
    assert len(strict_json_object(body, maximum_nodes=30000)["items"]) == 11000


@pytest.mark.parametrize("value", [0, 50001, True])
def test_json_node_limit_itself_is_bounded(value):
    with pytest.raises(ValueError):
        strict_json_object("{}", maximum_nodes=value)
