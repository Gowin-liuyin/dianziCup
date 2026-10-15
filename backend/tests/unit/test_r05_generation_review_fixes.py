"""独立审查确证问题的合成凭据和嵌套验证回归；没有供应商调用。"""

import json
from dataclasses import dataclass

import pytest
from pydantic import BaseModel, ConfigDict, create_model
from test_r05_generation import Answer, prepared, request, wire
from typing_extensions import TypedDict

from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.generation import GenerationFailure


class InheritedTyped(TypedDict):
    required: int


class ForbidTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra="forbid")
    required: int


class IgnoreTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra="ignore")
    required: int


class AllowTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra="allow")
    required: int


@dataclass
class InheritedDataclass:
    required: int


@dataclass
class ForbidDataclass:
    __pydantic_config__ = ConfigDict(extra="forbid")
    required: int


@dataclass
class IgnoreDataclass:
    __pydantic_config__ = ConfigDict(extra="ignore")
    required: int


@dataclass
class AllowDataclass:
    __pydantic_config__ = ConfigDict(extra="allow")
    required: int


@pytest.mark.parametrize("provider", ["deepseek_openai", "deepseek_anthropic"])
@pytest.mark.parametrize("field", ["model_version", "prompt_version", "schema_version"])
@pytest.mark.parametrize("wrapper", ["{}", "prefix-{}", "{}-suffix"])
def test_metadata_identifiers_with_credential_rejected_before_encoding(
    monkeypatch, provider, field, wrapper
):
    client, calls = prepared(monkeypatch, provider=provider)
    credential = client._credential.get_secret_value()

    def forbidden_encoding(*arguments, **keywords):
        raise AssertionError("credential identifiers must be rejected before encoding")

    monkeypatch.setattr(generation, "encode_wire", forbidden_encoding)
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(**{field: wrapper.format(credential)}), Answer)
    assert caught.value.code == "model_credential_in_input"
    assert calls == [] and caught.value.attempts == ()
    assert credential not in repr(vars(caught.value)) + str(caught.value)


@pytest.mark.parametrize("child", [IgnoreTyped, AllowTyped, IgnoreDataclass, AllowDataclass])
@pytest.mark.parametrize("container", ["direct", "list", "mapping", "union"])
def test_nested_override_rejected_before_network(monkeypatch, child, container):
    annotation = {
        "direct": child,
        "list": list[child],
        "mapping": dict[str, child],
        "union": child | None,
    }[container]
    schema = create_model(
        "OverrideRoot", __config__=ConfigDict(extra="forbid"), nested=(annotation, ...)
    )
    client, calls = prepared(monkeypatch)
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(), schema)
    assert caught.value.code == "model_schema_must_forbid_extra"
    assert calls == [] and caught.value.attempts == ()


@pytest.mark.parametrize(
    "child", [InheritedTyped, ForbidTyped, InheritedDataclass, ForbidDataclass]
)
@pytest.mark.parametrize("extra", [False, True])
def test_effectively_forbidden_nested_objects_preserve_validation(monkeypatch, child, extra):
    schema = create_model(
        "StrictRoot", __config__=ConfigDict(extra="forbid"), nested=(dict[str, list[child]], ...)
    )
    nested = {"required": 1, **({"extra": "must reject"} if extra else {})}
    body = {"nested": {"document-key": [nested]}}
    client, calls = prepared(monkeypatch, responses=[wire(raw=json.dumps(body))])
    if extra:
        with pytest.raises(GenerationFailure) as caught:
            client.generate(request(), schema)
        assert caught.value.code == "model_format_invalid"
    else:
        result = client.generate(request(), schema)
        assert result.value.model_dump() == body
    assert len(calls) == 1


def test_recursive_model_definitions_are_checked_without_loop(monkeypatch):
    class Recursive(BaseModel):
        model_config = ConfigDict(extra="forbid")
        value: int
        children: list["Recursive"]

    body = {"value": 1, "children": [{"value": 2, "children": []}]}
    client, calls = prepared(monkeypatch, responses=[wire(raw=json.dumps(body))])
    assert client.generate(request(), Recursive).value.model_dump() == body
    assert len(calls) == 1
