"""展示schema/serializer不能替代有效输入验证；合成隔离测试。"""

from dataclasses import dataclass

import pytest
from pydantic import BaseModel, ConfigDict, create_model, model_serializer
from typing_extensions import TypedDict

from ai_intel.infrastructure.models.generation import GenerationFailure
from test_r05_generation import prepared, request, wire


class MisleadingTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra="ignore", json_schema_extra={"additionalProperties": False})
    required: int


@dataclass
class MisleadingDataclass:
    __pydantic_config__ = ConfigDict(extra="ignore", json_schema_extra={"additionalProperties": False})
    required: int


class HookModel(BaseModel):
    model_config = ConfigDict(extra="ignore")
    required: int

    @classmethod
    def __get_pydantic_json_schema__(cls, core_schema, handler):
        result = handler(core_schema)
        result["additionalProperties"] = False
        return result


@pytest.mark.parametrize("child", [MisleadingTyped, MisleadingDataclass, HookModel])
def test_presentation_forbid_does_not_override_validation_ignore(monkeypatch, child):
    root = create_model("HookRoot", __config__=ConfigDict(extra="forbid"), nested=(child, ...))
    assert root.model_json_schema()["$defs"][child.__name__]["additionalProperties"] is False
    client, calls = prepared(monkeypatch)
    with pytest.raises(GenerationFailure, match="model_schema_must_forbid_extra"):
        client.generate(request(), root)
    assert calls == []


def test_serializer_cannot_hide_extra_input_from_validation(monkeypatch):
    class Serialized(BaseModel):
        model_config = ConfigDict(extra="forbid")
        required: int

        @model_serializer
        def safe_looking(self):
            return {"required": 1}

    root = create_model("SerializerRoot", __config__=ConfigDict(extra="forbid"), nested=(Serialized, ...))
    client, calls = prepared(monkeypatch, responses=[wire(raw='{"nested":{"required":1,"extra":"must reject"}}')])
    with pytest.raises(GenerationFailure, match="model_format_invalid"):
        client.generate(request(), root)
    assert len(calls) == 1
