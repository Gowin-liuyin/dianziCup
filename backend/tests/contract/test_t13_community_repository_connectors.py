"""T13 社区/仓库连接器合同验收测试: 覆盖 T13-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.ingestion.sources.repository import (
    RepositoryAccessBlocked,
    RepositoryFetchError,
    fetch_with_access_guard,
    link_release_and_fix_commit,
    normalize_community_article,
    normalize_repository_record,
)


def test_release_and_fix_commit_link_without_merging_t13_c01() -> None:
    """T13-C01: 同产品 release 与修复 commit 可关联但不合并成同文档。"""
    release = normalize_repository_record(
        {
            "record_type": "release",
            "fixed_identifier": "v2.1",
            "title": "Release 2.1",
            "related_product": "libdemo",
        }
    )
    commit = normalize_repository_record(
        {
            "record_type": "commit",
            "fixed_identifier": "a" * 40,
            "title": "Fix advisory",
            "related_product": "libdemo",
        }
    )
    linked_release, linked_commit, relation_key = link_release_and_fix_commit(
        release, commit, "libdemo"
    )
    assert linked_release is release and linked_commit is commit
    assert linked_release.fixed_identifier != linked_commit.fixed_identifier
    assert relation_key == f"libdemo:v2.1:{'a' * 40}"
    assert linked_release.record_type == "release" and linked_commit.record_type == "commit"


def test_multi_vulnerability_article_links_each_separately_t13_c02() -> None:
    """T13-C02: 社区文章涉及多个漏洞各自关联, 不并成一个漏洞。"""
    article = normalize_community_article(
        {
            "article_id": "POST-1",
            "title": "Two issues discussed",
            "body": "text",
            "referenced_advisory_ids": ["ADV-1", "ADV-2"],
        }
    )
    assert article.referenced_advisory_ids == ("ADV-1", "ADV-2")
    assert len(article.referenced_advisory_ids) == 2
    assert article.referenced_advisory_ids[0] != article.referenced_advisory_ids[1]


def test_pinned_commit_identifier_traces_version_t13_c03() -> None:
    """T13-C03: 固定 commit 引用可追溯版本, 不只保存浮动 main。"""
    pinned = normalize_repository_record(
        {
            "record_type": "commit",
            "fixed_identifier": "b" * 40,
            "title": "fix",
            "related_product": "libdemo",
        }
    )
    assert len(pinned.fixed_identifier) == 40
    with pytest.raises(RepositoryFetchError):
        normalize_repository_record(
            {
                "record_type": "commit",
                "fixed_identifier": "main",
                "title": "fix",
                "related_product": "libdemo",
            }
        )


def test_private_or_missing_repo_fails_but_history_survives_t13_c04() -> None:
    """T13-C04: 仓库转私有/404 获取失败, 历史证据不自动撤回(由调用方保留)。"""
    with pytest.raises(RepositoryFetchError):
        fetch_with_access_guard(lambda: {"status_code": 404})
    with pytest.raises(RepositoryFetchError):
        fetch_with_access_guard(lambda: {"status_code": 410})
    historical = normalize_repository_record(
        {
            "record_type": "release",
            "fixed_identifier": "v1",
            "title": "old",
            "related_product": "libdemo",
        }
    )
    assert historical.fixed_identifier == "v1"


def test_missing_permission_is_blocked_live_not_fake_response_t13_c05() -> None:
    """T13-C05: 接口无权限 → blocked_live, 不退化成伪响应。"""
    with pytest.raises(RepositoryAccessBlocked):
        fetch_with_access_guard(lambda: {"status_code": 403})
    with pytest.raises(RepositoryAccessBlocked):
        fetch_with_access_guard(lambda: {"status_code": 401})


def test_poc_link_stored_as_metadata_not_executed_t13_c06() -> None:
    """T13-C06: POC 链接进入材料只保存元数据, 不自动执行。"""
    record = normalize_repository_record(
        {
            "record_type": "security_advisory",
            "fixed_identifier": "ADV-1",
            "title": "issue",
            "related_product": "libdemo",
            "poc_link": "https://example.invalid/poc",
        }
    )
    assert record.metadata_only_link == "https://example.invalid/poc"
    assert record.record_type == "security_advisory"
