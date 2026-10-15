"""New independent probes for fixed metadata and Pydantic effective input schemas."""

import json
from dataclasses import dataclass

import pytest
from pydantic import BaseModel, ConfigDict, Field, create_model
from test_r05_generation import Answer, prepared, request, wire
from typing_extensions import TypedDict

from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.generation import GenerationFailure


@pytest.mark.parametrize('provider', ['deepseek_openai', 'deepseek_anthropic'])
@pytest.mark.parametrize('field', ['prompt_version', 'schema_version', 'model_version'])
@pytest.mark.parametrize('placement', ['{}', 'prefix-{}-suffix'])
def test_known_key_in_identifier_fails_before_any_schema_body_or_network(monkeypatch, provider, field, placement):
    client, calls = prepared(monkeypatch, provider=provider)
    known = client._credential.get_secret_value()
    def forbidden(*arguments, **keywords):
        raise AssertionError('schema or body evaluated before credential identity check')
    monkeypatch.setattr(generation, 'require_strict_schema', forbidden)
    monkeypatch.setattr(generation, 'encode_wire', forbidden)
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(**{field: placement.format(known)}), Answer)
    assert caught.value.code == 'model_credential_in_input'
    assert calls == [] and caught.value.attempts == ()
    assert known not in repr(vars(caught.value)) + str(caught.value)


class IgnoreTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra='ignore', json_schema_extra={'additionalProperties': False})
    required: int


class AllowTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra='allow')
    required: int


@dataclass
class IgnoreDataclass:
    __pydantic_config__ = ConfigDict(extra='ignore', json_schema_extra={'additionalProperties': False})
    required: int


@dataclass
class AllowDataclass:
    __pydantic_config__ = ConfigDict(extra='allow')
    required: int


@pytest.mark.parametrize('child', [IgnoreTyped, AllowTyped, IgnoreDataclass, AllowDataclass])
@pytest.mark.parametrize('location', ['list_map', 'nullable_tuple'])
def test_container_schema_overrides_are_rejected_with_no_repair_attempt(monkeypatch, child, location):
    annotation = list[dict[str, child]] if location == 'list_map' else tuple[child | None, ...]
    schema = create_model('ContainerRoot', __config__=ConfigDict(extra='forbid'), nested=(annotation, ...))
    client, calls = prepared(monkeypatch)
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(allow_format_repair=True), schema)
    assert caught.value.code == 'model_schema_must_forbid_extra'
    assert calls == [] and caught.value.attempts == ()


class SchemaHookLoose(BaseModel):
    model_config = ConfigDict(extra='ignore')
    required: int
    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        result = handler(core_schema)
        result['additionalProperties'] = False
        return result


def test_real_json_schema_hook_cannot_disguise_effective_ignore(monkeypatch):
    class StrictParent(BaseModel):
        model_config = ConfigDict(extra='forbid')
        child: SchemaHookLoose
    exported = StrictParent.model_json_schema()
    assert exported['$defs']['SchemaHookLoose']['additionalProperties'] is False
    assert SchemaHookLoose.model_validate_json('{"required":1,"extra":"ignored"}', strict=True).model_dump() == {'required': 1}
    client, calls = prepared(monkeypatch)
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(), StrictParent)
    assert caught.value.code == 'model_schema_must_forbid_extra'
    assert calls == []


class InheritTyped(TypedDict):
    required: int


class StrictTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra='forbid')
    required: int


@dataclass
class InheritDataclass:
    required: int


@dataclass
class StrictDataclass:
    __pydantic_config__ = ConfigDict(extra='forbid')
    required: int


@pytest.mark.parametrize('child', [InheritTyped, StrictTyped, InheritDataclass, StrictDataclass])
@pytest.mark.parametrize('extra', [False, True])
def test_effective_strict_schema_accepts_valid_json_and_rejects_nested_extras(monkeypatch, child, extra):
    schema = create_model('StrictContainer', __config__=ConfigDict(extra='forbid'), nested=(list[dict[str, child]], ...))
    leaf = {'required': 7, **({'extra': 'must fail'} if extra else {})}
    payload = {'nested': [{'public-evidence': leaf}]}
    client, calls = prepared(monkeypatch, responses=[wire(raw=json.dumps(payload))])
    if extra:
        with pytest.raises(GenerationFailure) as caught:
            client.generate(request(), schema)
        assert caught.value.code == 'model_format_invalid'
    else:
        result = client.generate(request(), schema)
        assert result.value.model_dump(mode='json') == payload
    assert len(calls) == 1


class RecursiveTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra='forbid')
    required: int
    children: list['RecursiveTyped']


@dataclass
class RecursiveDataclass:
    __pydantic_config__ = ConfigDict(extra='forbid')
    required: int
    children: list['RecursiveDataclass']


@pytest.mark.parametrize('child', [RecursiveTyped, RecursiveDataclass])
@pytest.mark.parametrize('extra', [False, True])
def test_recursive_definitions_validate_each_leaf_without_preflight_loop(monkeypatch, child, extra):
    schema = create_model('RecursiveRoot', __config__=ConfigDict(extra='forbid'), tree=(child, ...))
    body = {'tree': {'required': 1, 'children': [{'required': 2, 'children': [], **({'extra': 'must fail'} if extra else {})}]}}
    client, calls = prepared(monkeypatch, responses=[wire(raw=json.dumps(body))])
    if extra:
        with pytest.raises(GenerationFailure) as caught:
            client.generate(request(), schema)
        assert caught.value.code == 'model_format_invalid'
    else:
        assert client.generate(request(), schema).value.model_dump(mode='json') == body
    assert len(calls) == 1


class RecursiveLoose(BaseModel):
    model_config = ConfigDict(extra='forbid')
    children: list['RecursiveLoose']
    loose: IgnoreTyped | None


def test_recursive_reference_still_discovers_nested_loose_input(monkeypatch):
    client, calls = prepared(monkeypatch)
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(), RecursiveLoose)
    assert caught.value.code == 'model_schema_must_forbid_extra' and calls == []


def test_validation_ignores_fake_presentation_metadata(monkeypatch):
    class Safe(BaseModel):
        model_config = ConfigDict(extra='forbid')
        required: int = Field(json_schema_extra={'documentation': {'type': 'model', 'config': {'extra_fields_behavior': 'ignore'}}})
    client, calls = prepared(monkeypatch, responses=[wire(raw='{"required":7}')])
    assert client.generate(request(), Safe).value.required == 7
    assert len(calls) == 1
