"""Independent actual parse and safe-failure checks after forced deferred-schema construction."""
import json
import pytest
from pydantic import BaseModel, ConfigDict, create_model
from typing_extensions import TypedDict
from test_r05_generation import prepared, request, wire
from ai_intel.infrastructure.models.generation import GenerationFailure

class StrictLeaf(TypedDict):
    count: int

@pytest.mark.parametrize('extra', [False, True])
def test_deferred_inherited_container_retains_actual_strict_validation(monkeypatch, extra):
    schema = create_model('DeferredInheritedStrict', __config__=ConfigDict(extra='forbid', defer_build=True), values=(dict[str, list[StrictLeaf]], ...))
    body = {'values': {'evidence': [{'count': 7, **({'extra': 'must reject'} if extra else {})}]}}
    assert schema.__pydantic_complete__ is False
    client, calls = prepared(monkeypatch, responses=[wire(raw=json.dumps(body))])
    if extra:
        with pytest.raises(GenerationFailure) as caught:
            client.generate(request(), schema)
        assert caught.value.code == 'model_format_invalid'
    else:
        assert client.generate(request(), schema).value.model_dump() == body
    assert schema.__pydantic_complete__ is True and len(calls) == 1

@pytest.mark.parametrize('extra', [False, True])
def test_deferred_recursive_schema_parses_complete_output(monkeypatch, extra):
    class DeferredTree(BaseModel):
        model_config=ConfigDict(extra='forbid', defer_build=True)
        count: int
        children: list['DeferredTree']
    body={'count':1,'children':[{'count':2,'children':[],**({'extra':'must reject'} if extra else {})}]}
    assert DeferredTree.__pydantic_complete__ is False
    client,calls=prepared(monkeypatch,responses=[wire(raw=json.dumps(body))])
    if extra:
        with pytest.raises(GenerationFailure) as caught:
            client.generate(request(),DeferredTree)
        assert caught.value.code=='model_format_invalid'
    else:
        assert client.generate(request(),DeferredTree).value.model_dump()==body
    assert len(calls)==1

def test_unresolved_deferred_schema_has_no_sensitive_name_or_attempt_trace(monkeypatch):
    marker='SyntheticPrivateSchemaReference'
    schema=create_model('UnresolvedReview',__config__=ConfigDict(extra='forbid',defer_build=True),value=(marker,...))
    client,calls=prepared(monkeypatch)
    with pytest.raises(GenerationFailure) as caught:
        client.generate(request(),schema)
    assert caught.value.code=='model_schema_must_forbid_extra'
    assert marker not in str(caught.value)+repr(vars(caught.value))
    assert calls==[] and caught.value.attempts==()
