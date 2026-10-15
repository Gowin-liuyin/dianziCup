"""已批准只读DTO与公共v2的对齐；不把fixture计成真实业务链路。"""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError

from ai_intel.api.knowledge_contracts import EnrichmentProjection, EventListResponse

SCHEMA = json.loads(
    (Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_v2.json").read_text(
        encoding="utf-8"
    )
)


@pytest.mark.parametrize(
    "dimension",
    ["cvss", "epss", "kev", "cwe", "atlas", "versions", "literature", "poc", "exposure"],
)
def test_missing_dimensions_remain_pending_in_public_schema(dimension: str) -> None:
    projection = EnrichmentProjection(
        dimension=dimension,
        status="pending",
        claim_ids=(),
        citations=(),
        freshness="unknown",
        observed_at=None,
        source_version=None,
        error_code=None,
    )
    schema = {"$ref": "#/$defs/Enrichment", "$defs": SCHEMA["$defs"]}
    Draft202012Validator(schema).validate(projection.model_dump(mode="json"))


def test_available_without_citation_rejected_in_both_contracts() -> None:
    payload = {
        "dimension": "cvss",
        "status": "available",
        "claim_ids": [str(uuid4())],
        "citations": [],
        "freshness": "unknown",
        "observed_at": None,
        "source_version": None,
        "error_code": None,
    }
    with pytest.raises(ValidationError):
        EnrichmentProjection.model_validate(payload)
    schema = {"$ref": "#/$defs/Enrichment", "$defs": SCHEMA["$defs"]}
    assert not Draft202012Validator(schema).is_valid(payload)


def test_empty_list_does_not_assert_safety_and_requires_explicit_mode() -> None:
    response = EventListResponse(items=(), next_cursor=None, data_mode="live")
    assert response.model_dump(mode="json") == {
        "schema_version": 2,
        "items": [],
        "next_cursor": None,
        "data_mode": "live",
    }
    with pytest.raises(ValidationError):
        EventListResponse.model_validate({"items": [], "next_cursor": None})
    with pytest.raises(ValidationError):
        EventListResponse.model_validate(
            {"items": [], "next_cursor": None, "data_mode": "live", "is_safe": True}
        )
