"""API投影仍服从冻结v2问答合同，不能放松引用和身份边界。"""

import json
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ai_intel.api.question_contracts import QuestionAnswerResponse, QuestionRequest

ROOT = Path(__file__).resolve().parents[3]
IDENTIFIER = UUID("00000000-0000-4000-8000-000000000001")


def frozen_validator(definition: str) -> Draft202012Validator:
    contract = json.loads(
        (ROOT / "contracts/schemas/public_api_v2.json").read_text(encoding="utf-8")
    )
    return Draft202012Validator({"$ref": f"#/$defs/{definition}", "$defs": contract["$defs"]})


def test_request_projects_to_frozen_ask_contract() -> None:
    request = QuestionRequest(
        question="这一事件有哪些原文支持的风险？", mode="library", event_ids=(IDENTIFIER,)
    )
    frozen_validator("AskRequest").validate(request.model_dump(mode="json", exclude_none=True))


@pytest.mark.parametrize("question", ["", "   ", "\0", "\ud800"])
def test_empty_or_invalid_question_is_not_sent_to_models(question: str) -> None:
    with pytest.raises(ValidationError):
        QuestionRequest(question=question, mode="library")


def test_identity_fields_are_not_question_inputs() -> None:
    with pytest.raises(ValidationError):
        QuestionRequest.model_validate(
            {"question": "风险", "mode": "library", "tenant_id": "foreign"}
        )


def test_completed_answer_matches_frozen_public_contract() -> None:
    at = datetime(2026, 10, 15, 8, tzinfo=UTC)
    response = QuestionAnswerResponse(
        answer_id=IDENTIFIER,
        answer_text="资料不足，无法确定该资产是否受影响。",
        claims=(),
        citations=(),
        limitations=("仅当前事件的公开来源，不含资产研判。",),
        freshness="unknown",
        data_mode="live",
        started_at=at,
        completed_at=at,
        latency_milliseconds=0,
    )
    frozen_validator("QAAnswer").validate(response.model_dump(mode="json"))
