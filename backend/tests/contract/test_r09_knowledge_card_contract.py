"""R09非CVE机制与标准政策卡字段合同；fixture不计真实资料/live验收。"""

import json
from concurrent.futures import ThreadPoolExecutor
from uuid import UUID

import pytest

from ai_intel.enrichment.card_extraction import (
    CardExtractionFailure,
    CardExtractionOutput,
    build_knowledge_card,
    extract_knowledge_card,
)
from ai_intel.enrichment.knowledge_cards import PAPER_FIELDS, PUBLICATION_FIELDS
from r09_card_fixtures import PUBLIC_SCOPE, candidate_field, prepared_client, source_document


@pytest.mark.parametrize(
    "mechanism,attacker,input_path,task,permission,environment,conclusion,limit",
    [
        (
            "prompt_injection",
            "控制检索文档",
            "检索上下文",
            "工具助手",
            "write_filesystem",
            "作者沙箱助手",
            "作者报告文件可被修改",
            "只读工具未验证",
        ),
        (
            "training_data_poisoning",
            "修改训练样本",
            "微调训练数据",
            "分类模型",
            "训练数据写入",
            "作者离线训练集",
            "作者报告触发样本偏移",
            "生产数据未验证",
        ),
        (
            "model_extraction",
            "查询预测接口",
            "黑盒模型API",
            "图像分类",
            "预测接口访问",
            "作者实验接口",
            "作者报告训练替代模型",
            "未访问当前资产",
        ),
    ],
)
def test_three_non_cve_mechanism_field_contracts(
    monkeypatch: pytest.MonkeyPatch,
    mechanism: str,
    attacker: str,
    input_path: str,
    task: str,
    permission: str,
    environment: str,
    conclusion: str,
    limit: str,
) -> None:
    values = (mechanism, attacker, input_path, task, permission, environment, conclusion, limit)
    source = source_document(
        tuple(f"fixture source explicitly states: {value}." for value in values)
    )
    output = {
        "fields": [
            candidate_field(source, name, value, evidence_index=index)
            for index, (name, value) in enumerate(zip(PAPER_FIELDS, values, strict=True))
        ]
    }
    client, calls = prepared_client(monkeypatch, output)
    draft = extract_knowledge_card(client, source, PUBLIC_SCOPE)
    assert tuple(field.field_name for field in draft.fields) == PAPER_FIELDS
    assert tuple(field.proposed_values[0].value for field in draft.fields) == values
    assert all(field.status == "candidate" for field in draft.fields)
    assert all(field.semantic_support == "unverified" for field in draft.fields)
    assert all(
        value.origin == "model_hypothesis"
        for field in draft.fields
        for value in field.proposed_values
    )
    assert draft.verification_level == "unknown" and draft.confirmation_status == "awaiting_review"
    assert len(calls) == 1 and draft.data_mode == "fixture"
    assert not {"cve_ids", "cvss", "team_reproduced", "asset_rule"}.intersection(
        field.field_name for field in draft.fields
    )


def test_policy_draft_final_keep_historical_revision_and_dates_separate() -> None:
    old_source = source_document(("Draft issued 2026-01-02; scope is not stated.",), kind="policy")
    new_source = source_document(
        ("Final issued 2026-03-01; effective from 2026-04-15.",),
        kind="policy",
        revision_id=UUID("00000000-0000-4000-8000-000000000039"),
        revision_number=2,
    )
    old_output = CardExtractionOutput.model_validate_json(
        json.dumps({"fields": [candidate_field(old_source, "publication_status", "draft")]}),
        strict=True,
    )
    new_output = CardExtractionOutput.model_validate_json(
        json.dumps(
            {
                "fields": [
                    candidate_field(new_source, "publication_status", "final"),
                    candidate_field(new_source, "published_at", "2026-03-01"),
                    candidate_field(new_source, "effective_at", "2026-04-15"),
                ]
            }
        ),
        strict=True,
    )
    old_card = build_knowledge_card(old_source, old_output)
    new_card = build_knowledge_card(new_source, new_output)
    assert old_card.document_id == new_card.document_id
    assert old_card.revision_id != new_card.revision_id
    assert [
        field.proposed_values[0].value for field in new_card.fields if field.proposed_values
    ] == ["final", "2026-03-01", "2026-04-15"]
    assert old_card.fields[3].proposed_values[0].value == "draft"
    assert old_card.fields[5].status == "unknown"
    assert old_card.fields[6].status == "unknown"
    assert all(field.revision_number == 1 for field in old_card.fields)
    assert all(field.revision_number == 2 for field in new_card.fields)
    assert new_source.document.source_published_at is None


@pytest.mark.parametrize("kind", ["standard", "policy"])
def test_publication_card_retains_every_required_source_field(kind: str) -> None:
    values = (
        "Fixture Publisher",
        "FIXTURE-001",
        "draft-1",
        "draft",
        "2026-01-02",
        "2026-04-03",
        "research systems",
        "Fixture clause: assess risk.",
        "Assess risk summary.",
    )
    source = source_document(values, kind=kind)
    output = CardExtractionOutput.model_validate_json(
        json.dumps(
            {
                "fields": [
                    candidate_field(source, name, value, evidence_index=index)
                    for index, (name, value) in enumerate(
                        zip(PUBLICATION_FIELDS, values, strict=True)
                    )
                ]
            }
        ),
        strict=True,
    )
    card = build_knowledge_card(source, output)
    assert tuple(field.proposed_values[0].value for field in card.fields[:-1]) == values
    assert all(field.proposed_values[0].citations for field in card.fields[:-1])
    assert card.fields[-1].status == "unknown"
    assert card.confirmation_status == "awaiting_review"


@pytest.mark.parametrize(
    "kind,correct,wrong",
    [
        ("standard", "standard_recommendation", "policy_obligation"),
        ("policy", "policy_obligation", "standard_recommendation"),
    ],
)
def test_standard_recommendation_and_policy_obligation_never_share_fields(
    kind: str, correct: str, wrong: str
) -> None:
    source = source_document(("Operators should assess risk.",), kind=kind)
    valid = CardExtractionOutput.model_validate_json(
        json.dumps({"fields": [candidate_field(source, correct, "Assess risk")]}), strict=True
    )
    draft = build_knowledge_card(source, valid)
    assert tuple(field.field_name for field in draft.fields) == (*PUBLICATION_FIELDS, correct)
    assert draft.fields[-1].status == "candidate"
    invalid = CardExtractionOutput.model_validate_json(
        json.dumps({"fields": [candidate_field(source, wrong, "Assess risk")]}), strict=True
    )
    with pytest.raises(CardExtractionFailure, match="card_field_for_kind_invalid"):
        build_knowledge_card(source, invalid)


def test_clause_original_and_paraphrase_summary_are_independent() -> None:
    original = "Operators shall restrict access, when this policy applies."
    source = source_document((original,), kind="policy")
    fields = [
        candidate_field(source, "clause_text", original),
        candidate_field(source, "summary", "Access restriction is stated conditionally."),
    ]
    output = CardExtractionOutput.model_validate_json(json.dumps({"fields": fields}), strict=True)
    draft = build_knowledge_card(source, output)
    assert draft.fields[7].proposed_values[0].value == original
    assert draft.fields[8].proposed_values[0].value != original
    assert draft.fields[6].status == "unknown"
    assert draft.fields[-1].status == "unknown"
    modified = CardExtractionOutput.model_validate_json(
        json.dumps(
            {"fields": [candidate_field(source, "clause_text", "Unconditional access ban.")]}
        ),
        strict=True,
    )
    with pytest.raises(CardExtractionFailure, match="card_original_text_mismatch"):
        build_knowledge_card(source, modified)


def test_replay_and_concurrent_builds_do_not_mutate_history_or_share_candidate_lists() -> None:
    source = source_document()
    output = CardExtractionOutput.model_validate_json(
        json.dumps({"fields": [candidate_field(source)]}), strict=True
    )
    source_before = source.model_dump_json()
    with ThreadPoolExecutor(max_workers=2) as pool:
        cards = list(pool.map(lambda _: build_knowledge_card(source, output), range(4)))
    assert cards == [build_knowledge_card(source, output)] * 4
    assert source.model_dump_json() == source_before
    assert cards[0].fields is not cards[1].fields
    assert all(card.revision_id == source.document.revision_id for card in cards)
