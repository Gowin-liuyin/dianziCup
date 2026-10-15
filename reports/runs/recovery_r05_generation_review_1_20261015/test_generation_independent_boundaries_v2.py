"""Independent synthetic credential and schema probes; no vendor calls."""

from dataclasses import asdict, dataclass
import json
from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError
from typing_extensions import TypedDict
from test_r05_generation import Answer, prepared, request, wire

from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationFailure, GenerationLimits
from ai_intel.infrastructure.models.json_output import strict_json_object
from ai_intel.infrastructure.network import FetchResult


@pytest.mark.parametrize('version_field', ['prompt_version', 'schema_version'])
def test_credential_value_in_metadata_version_is_withheld(monkeypatch, version_field):
    client, calls = prepared(monkeypatch)
    synthetic_credential = client._credential.get_secret_value()
    try:
        result = client.generate(request(**{version_field: synthetic_credential}), Answer)
    except GenerationFailure as failure:
        assert failure.code == 'model_credential_in_input'
        assert not calls
    else:
        assert synthetic_credential not in repr(asdict(result.attempts[0]))


class TypedChild(TypedDict):
    __pydantic_config__ = ConfigDict(extra='ignore')
    required: int


@dataclass
class DataclassChild:
    __pydantic_config__ = ConfigDict(extra='ignore')
    required: int


@pytest.mark.parametrize('child_type', [TypedChild, DataclassChild])
def test_all_nested_object_schemas_forbid_extra_before_network(monkeypatch, child_type):
    class Root(BaseModel):
        model_config = ConfigDict(extra='forbid')
        nested: child_type

    client, calls = prepared(monkeypatch, responses=[wire(raw='{"nested":{"required":1,"extra":"silently dropped"}}')])
    try:
        result = client.generate(request(), Root)
    except GenerationFailure as failure:
        assert failure.code in {'model_schema_must_forbid_extra', 'model_format_invalid'}
        if failure.code == 'model_schema_must_forbid_extra':
            assert calls == []
    else:
        pytest.fail('nested unknown property was silently accepted')


@pytest.mark.parametrize('provider', ['deepseek_openai', 'deepseek_anthropic'])
@pytest.mark.parametrize('field', ['model', 'id'])
def test_reflected_upstream_credential_never_enters_metadata(monkeypatch, provider, field):
    payload = wire(provider, **{field: 'fixture-generation-credential-12345'})
    client, calls = prepared(monkeypatch, provider=provider, responses=[payload])
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(allow_format_repair=True), Answer)
    assert caught.value.code == 'model_credential_in_response'
    assert 'fixture-generation-credential-12345' not in repr(caught.value.attempts)
    assert len(calls) == 1


@pytest.mark.parametrize('provider', ['deepseek_openai', 'deepseek_anthropic'])
def test_private_egress_block_happens_before_schema_or_body_encoding(monkeypatch, provider):
    client, calls = prepared(monkeypatch, provider=provider)
    def fail_if_called(*arguments, **keywords):
        raise AssertionError('body or schema evaluated before egress policy')
    monkeypatch.setattr(generation, 'encode_wire', fail_if_called)
    monkeypatch.setattr(Answer, 'model_json_schema', fail_if_called)
    with pytest.raises(PermissionError):
        client.generate(request(), Answer, content_is_private=True, egress_granted=False)
    assert calls == []


@pytest.mark.parametrize('provider', ['openai', 'anthropic'])
def test_native_clients_use_trusted_model_and_fixed_endpoint(monkeypatch, provider):
    client = GenerationClient(provider, 'approved-native-model', SecretStr('synthetic-native-review-credential'))
    packets = []
    def post(url, body, **options):
        packets.append((url, json.loads(body), options))
        payload = wire(provider, model='resolved-native-model')
        return FetchResult(url, 200, 'application/json', json.dumps(payload).encode())
    monkeypatch.setattr(client._gateway, 'post_json', post)
    result = client.generate(request(model_version='approved-native-model'), Answer)
    assert result.attempts[0].requested_model == 'approved-native-model'
    assert result.attempts[0].response_model == 'resolved-native-model'
    assert packets[0][0] == generation.ENDPOINTS[provider]
    assert packets[0][1]['model'] == 'approved-native-model'
    token_field = 'max_tokens' if provider == 'anthropic' else 'max_completion_tokens'
    assert packets[0][1][token_field] == 100


@pytest.mark.parametrize('field', ['system_text', 'question', 'evidence_texts'])
def test_utf8_and_nul_boundary_preserves_no_bad_input_in_error(field):
    bad = 'synthetic-sensitive-request\ud800'
    changes = {field: (bad,) if field == 'evidence_texts' else bad}
    with pytest.raises(ValidationError) as caught:
        request(**changes)
    assert 'synthetic-sensitive-request' not in str(caught.value)


@pytest.mark.parametrize('maximum,valid', [(8, False), (9, True)])
def test_json_byte_limit_is_utf8_bytes(maximum, valid):
    body = '{"中":0}'
    if valid:
        assert strict_json_object(body, maximum_bytes=maximum) == {'中': 0}
    else:
        with pytest.raises(ValueError):
            strict_json_object(body, maximum_bytes=maximum)


@pytest.mark.parametrize('field,value', [('output_tokens', False), ('output_tokens', -1), ('input_tokens', '1'), ('cache_read_input_tokens', {}), ('cache_creation_input_tokens', 1.2)])
def test_invalid_usage_rejected_without_repair(monkeypatch, field, value):
    client, calls = prepared(monkeypatch, provider='deepseek_anthropic', responses=[wire('deepseek_anthropic', usage={field: value})])
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(allow_format_repair=True), Answer)
    assert caught.value.code == 'model_usage_invalid' and len(calls) == 1


def test_total_output_budget_covers_repair(monkeypatch):
    client, calls = prepared(monkeypatch, responses=[wire(raw='bad-format'), wire()], limits=GenerationLimits(max_total_output_bytes=40))
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(allow_format_repair=True), Answer)
    assert caught.value.code == 'model_output_budget_exhausted'
    assert len(calls) == len(caught.value.attempts) == 2


def test_metadata_hashes_match_the_exact_wire_bytes(monkeypatch):
    import hashlib
    client, calls = prepared(monkeypatch)
    body_saved = []
    original = client._gateway.post_json
    def post(url, body, **options):
        body_saved.append(body)
        return original(url, body, **options)
    monkeypatch.setattr(client._gateway, 'post_json', post)
    result = client.generate(request(), Answer)
    assert result.attempts[0].body_sha256 == hashlib.sha256(body_saved[0]).hexdigest()
    assert result.attempts[0].response_sha256 == hashlib.sha256(json.dumps(wire()).encode()).hexdigest()

