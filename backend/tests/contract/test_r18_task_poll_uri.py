"""Task polling paths accept UUID groups without broadening the legacy profile."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

SCHEMA = json.loads(
    (
        Path(__file__).resolve().parents[3] / "contracts/schemas/public_api_extensions_v1.json"
    ).read_text(encoding="utf-8")
)
VALIDATOR = Draft202012Validator({**SCHEMA, "$ref": "#/$defs/TaskDescriptor/properties/poll_uri"})


@pytest.mark.parametrize(
    "identifier",
    (
        "-" * 36,
        "a" * 36,
        "0000000-00000-4000-8000-000000000001",
        "00000000-0000-4000-8000-000000000001/extra",
    ),
)
def test_invalid_poll_identifier_is_rejected(identifier: str) -> None:
    assert not VALIDATOR.is_valid("/api/v1/tasks/" + identifier)


def test_grouped_uuid_poll_identifier_is_preserved() -> None:
    assert VALIDATOR.is_valid("/api/v1/tasks/00000000-0000-4000-8000-000000000001")
