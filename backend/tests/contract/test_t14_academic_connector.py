"""T14 学术连接器合同验收测试: 覆盖 T14-C01—C06。"""

from __future__ import annotations

import pytest

from ai_intel.ingestion.sources.academic import (
    AcademicContractError,
    count_distinct_research,
    group_versions_by_paper,
    normalize_academic_record,
)


def test_two_version_updates_share_one_entity_t14_c01() -> None:
    """T14-C01: 同论文两次版本更新 → 同实体不同文档版本, 不重复统计。"""
    v1 = normalize_academic_record({"paper_id": "ARXIV-1", "title": "Paper", "version": "v1"})
    v2 = normalize_academic_record({"paper_id": "ARXIV-1", "title": "Paper", "version": "v2"})
    v3 = normalize_academic_record({"paper_id": "ARXIV-1", "title": "Paper", "version": "v3"})
    grouped = group_versions_by_paper([v1, v2, v3])
    assert list(grouped) == ["ARXIV-1"]
    assert [record.version_label for record in grouped["ARXIV-1"]] == ["v1", "v2", "v3"]
    assert count_distinct_research([v1, v2, v3]) == 1
    other = normalize_academic_record({"paper_id": "ARXIV-2", "title": "Other"})
    assert count_distinct_research([v1, v2, other]) == 2


def test_abstract_only_marks_full_text_not_fetched_t14_c02() -> None:
    """T14-C02: 只有摘要可索引, 全文字段标未获取, 不虚构实验结果。"""
    record = normalize_academic_record(
        {"paper_id": "ARXIV-1", "title": "Paper", "abstract": "We study jailbreaks."}
    )
    assert record.abstract == "We study jailbreaks."
    assert record.full_text_fetched is False
    assert record.extraction_status == "metadata_only"
    assert record.full_text_link is None


def test_paper_without_cve_gets_no_forged_identifier_t14_c03() -> None:
    """T14-C03: 没有 CVE 的论文是正常实体, 不制造漏洞标识。"""
    record = normalize_academic_record(
        {"paper_id": "ARXIV-3", "title": "No cve here", "abstract": "text"}
    )
    assert record.paper_id == "ARXIV-3"
    assert not record.paper_id.startswith("CVE-")
    assert record.attack_target_text is None


def test_ai_title_without_security_waits_for_relevance_module_t14_c04() -> None:
    """T14-C04: 标题含 AI 但无安全内容的记录保留, 等待相关性模块筛选(连接器不裁决)。"""
    record = normalize_academic_record(
        {"paper_id": "ARXIV-4", "title": "AI accelerates image captioning", "abstract": "vision"}
    )
    assert record.paper_id == "ARXIV-4"
    assert record.extraction_status == "metadata_only"
    assert record.attack_target_text is None and record.model_names_text is None


def test_inaccessible_api_page_is_blocked_not_guessed_t14_c05() -> None:
    """T14-C05: API 页不可访问 → capability blocked, 不猜未确认参数。"""
    with pytest.raises(AcademicContractError):
        normalize_academic_record({"unexpected": "shape"})
    partial = normalize_academic_record(
        {
            "paper_id": "ARXIV-5",
            "title": "T",
            "pdf_text_incomplete": True,
            "full_text_fetched": True,
        }
    )
    assert partial.extraction_status == "full_text_partial"


def test_pdf_with_images_but_no_text_is_partial_t14_c06() -> None:
    """T14-C06: PDF 含关键图片但文本缺失 → partial, 不宣称完整抽取。"""
    record = normalize_academic_record(
        {
            "paper_id": "ARXIV-6",
            "title": "Figures only",
            "full_text_fetched": True,
            "pdf_text_incomplete": True,
            "model_names": "GPT-4",
            "attack_target": "LLM chat",
        }
    )
    assert record.extraction_status == "full_text_partial"
    assert record.model_names_text == "GPT-4" and record.attack_target_text == "LLM chat"
    assert record.withdrawn is False
