"""Offline JSON contract cases use only frozen public v2 and explicit fixtures."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from tests.unit.test_public_write_adapters import (
    fixture_receipt,
    fixture_request,
    fixture_services,
)

from ai_intel.api.public_write_adapters import (
    parse_public_ask_request,
    parse_public_stack_request,
    stack_current_assessments,
)
from ai_intel.domain.enums import AssessmentStatus

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / "contracts/schemas/public_api_v2.json").read_text(encoding="utf-8"))


def validator(name):
    return Draft202012Validator(
        {"$ref": f"#/$defs/{name}", "$defs": SCHEMA["$defs"]}, format_checker=FormatChecker()
    )


@pytest.mark.parametrize(
    "raw",
    [
        b"",
        b"[]",
        b"{}",
        b'{"question":"x","question":"y","mode":"auto"}',
        b'{"question":NaN,"mode":"auto"}',
        b'{"question":"\\ud800","mode":"auto"}',
        b'{"question":"x","mode":"auto","tenant_id":"forged"}',
        b'{"question":"x","mode":"auto","conversation_id":null}',
        b'{"question":"x","mode":"auto","event_ids":["00000000000000000000000000000001"]}',
        b'{"question":"x","mode":"auto","known_at":"2026-10-16"}',
        b'{"question":"x","mode":"auto","known_at":0}',
    ],
)
def test_invalid_question_bytes_identity_uuid_and_timestamp_are_rejected(raw):
    with pytest.raises((ValueError, UnicodeError)):
        parse_public_ask_request(raw)


@pytest.mark.parametrize(
    "raw",
    [
        b"{}",
        b"[]",
        b'{"components":null}',
        b'{"components":[],"tenant_id":"forged"}',
        b'{"components":[{"ecosystem":"PyPI","package_name":"x"}]}',
        b'{"components":[{"ecosystem":"PyPI","package_name":"x","version":1}]}',
        b'{"components":[{"ecosystem":"PyPI","package_name":"x","version":null,"component_id":null}]}',
        b'{"components":[{"ecosystem":"PyPI","package_name":"x","version":null,"assessment_id":"forged"}]}',
        b'{"components":[],"components":[]}',
        json.dumps(
            {"components": [{"ecosystem": "npm", "package_name": "x", "version": None}] * 201}
        ).encode(),
        b" " * 1048577,
    ],
    ids=[
        "missing",
        "array",
        "null",
        "identity",
        "missing_version",
        "typed_version",
        "null_id",
        "body_assessment_id",
        "duplicate",
        "201_components",
        "byte_limit",
    ],
)
def test_invalid_stack_input_cannot_become_upload_or_a_typed_task(raw):
    with pytest.raises((ValueError, UnicodeError)):
        parse_public_stack_request(raw)


@pytest.mark.parametrize("status", list(AssessmentStatus))
def test_all_four_real_service_projection_states_validate_against_frozen_v2(status):
    from uuid import UUID

    receipt = fixture_receipt(status)
    service, knowledge = fixture_services(receipt)
    result = stack_current_assessments(
        fixture_request(), (UUID(receipt.assessment_id),), service, knowledge
    )
    validator("StackCheckResult").validate(result.model_dump(mode="json", exclude_unset=True))


def test_input_wire_fields_match_the_frozen_component_and_stack_contracts():
    raw = b'{"components":[{"ecosystem":"npm","package_name":"x","version":null}]}'
    validator("StackCheckRequest").validate(json.loads(raw))
    assert parse_public_stack_request(raw).model_dump(
        mode="json", exclude_unset=True
    ) == json.loads(raw)
    raw_question = b'{"question":"fixture","mode":"auto"}'
    validator("AskRequest").validate(json.loads(raw_question))
    assert parse_public_ask_request(raw_question).model_dump(
        mode="json", exclude_unset=True
    ) == json.loads(raw_question)
