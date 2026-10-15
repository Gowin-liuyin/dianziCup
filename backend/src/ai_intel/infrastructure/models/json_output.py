"""有界模型JSON边界；重复键、非有限数字、无效Unicode不能进入业务schema。"""

import json
import math


def strict_json_object(
    raw: str | bytes, maximum_bytes: int = 262144, *, maximum_nodes: int = 10000
) -> dict[str, object]:
    if type(maximum_nodes) is not int or not 1 <= maximum_nodes <= 50000:
        raise ValueError("JSON node budget outside limit")

    def pairs(entries: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in entries:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def constant(value: str) -> object:
        raise ValueError("non-finite JSON number")

    encoded = raw.encode("utf-8") if isinstance(raw, str) else raw
    if not 1 <= len(encoded) <= maximum_bytes:
        raise ValueError("JSON body outside limit")
    payload: object = json.loads(
        encoded.decode("utf-8"), object_pairs_hook=pairs, parse_constant=constant
    )
    pending: list[tuple[object, int]] = [(payload, 0)]
    count = 0
    while pending:
        value, depth = pending.pop()
        count += 1
        if depth > 32 or count > maximum_nodes:
            raise ValueError("JSON structure outside limit")
        if isinstance(value, str):
            value.encode("utf-8")
            if "\0" in value:
                raise ValueError("JSON string contains NUL")
        elif isinstance(value, float) and not math.isfinite(value):
            raise ValueError("non-finite JSON number")
        elif isinstance(value, dict):
            pending.extend((key, depth + 1) for key in value)
            pending.extend((child, depth + 1) for child in value.values())
        elif isinstance(value, list):
            pending.extend((child, depth + 1) for child in value)
    if not isinstance(payload, dict):
        raise ValueError("JSON object required")
    return payload
