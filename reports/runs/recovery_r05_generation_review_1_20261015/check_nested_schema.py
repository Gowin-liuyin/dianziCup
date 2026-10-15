import dataclasses
import json
from pydantic import BaseModel, ConfigDict
from typing_extensions import TypedDict
from ai_intel.infrastructure.models.generation import require_strict_schema
class Child(TypedDict):
    required: int
@dataclasses.dataclass
class ChildData:
    required: int
for child_type in (Child, ChildData):
    class Root(BaseModel):
        model_config=ConfigDict(extra='forbid')
        nested: child_type
    print(child_type.__name__, json.dumps(Root.model_json_schema()))
    try:
        require_strict_schema(Root)
        value=Root.model_validate_json('{"nested":{"required":1,"extra":"silently dropped"}}', strict=True)
        print(value.model_dump())
    except Exception as error:
        print(type(error).__name__, str(error))
