"""Deferred Pydantic schema must be built before inspection of its effective validation graph."""

import json
import pytest
from pydantic import BaseModel, ConfigDict
from typing_extensions import TypedDict
from test_r05_generation import prepared, request, wire
from ai_intel.infrastructure.models.generation import GenerationFailure

class LooseChild(TypedDict):
    __pydantic_config__ = ConfigDict(extra='ignore')
    required: int

@pytest.mark.parametrize('location', ['root', 'nested'])
def test_deferred_schema_does_not_bypass_extra_contract(monkeypatch, location):
    if location == 'root':
        class Deferred(BaseModel):
            model_config = ConfigDict(extra='ignore', defer_build=True)
            required: int
        body = {'required': 1, 'extra': 'must reject'}
    else:
        class Deferred(BaseModel):
            model_config = ConfigDict(extra='forbid', defer_build=True)
            nested: LooseChild
        body = {'nested': {'required': 1, 'extra': 'must reject'}}
    assert Deferred.__pydantic_complete__ is False
    client, calls = prepared(monkeypatch, responses=[wire(raw=json.dumps(body))])
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(), Deferred)
    assert caught.value.code == 'model_schema_must_forbid_extra'
    assert calls == [] and caught.value.attempts == ()
