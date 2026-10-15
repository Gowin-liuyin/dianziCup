"""锁定版本Pydantic的实际有效core schema，不含真实模型或凭据。"""

from dataclasses import dataclass
import json

from pydantic import BaseModel, ConfigDict
from typing_extensions import TypedDict


class DefaultTyped(TypedDict):
    required: int


class IgnoreTyped(TypedDict):
    __pydantic_config__ = ConfigDict(extra="ignore")
    required: int


@dataclass
class DefaultDataclass:
    required: int


@dataclass
class IgnoreDataclass:
    __pydantic_config__ = ConfigDict(extra="ignore")
    required: int


for child in (DefaultTyped, IgnoreTyped, DefaultDataclass, IgnoreDataclass):
    class Root(BaseModel):
        model_config = ConfigDict(extra="forbid")
        nested: child

    print(child.__name__)
    print(json.dumps(Root.__pydantic_core_schema__, default=str, indent=2))
