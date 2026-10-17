"""共享 JSON 边界回归；所有输入均为显式合成 fixture，不计 live。"""

import json
import sys
import traceback

import pytest

from ai_intel.infrastructure.models.json_output import strict_json_object


@pytest.mark.parametrize("as_bytes", [False, True])
def test_normal_json_retains_values(as_bytes: bool) -> None:
    raw = '{"text":"汉字","values":[true,null,1,1.25],"child":{"ok":false}}'
    result = strict_json_object(raw.encode() if as_bytes else raw)
    assert result == {
        "text": "汉字",
        "values": [True, None, 1, 1.25],
        "child": {"ok": False},
    }


@pytest.mark.parametrize("shape", ["array", "object"])
def test_depth_32_remains_allowed_and_33_is_rejected(shape: str) -> None:
    def nested(depth: int) -> str:
        if shape == "array":
            return '{"a":' + "[" * (depth - 1) + "0" + "]" * (depth - 1) + "}"
        return '{"a":' * depth + "0" + "}" * depth

    assert isinstance(strict_json_object(nested(32)), dict)
    with pytest.raises(ValueError, match=r"^JSON structure outside limit$"):
        strict_json_object(nested(33))


@pytest.mark.parametrize("limit", [300, 600, 1000])
@pytest.mark.parametrize("as_bytes", [False, True])
def test_decoder_depth_20000_is_a_safe_value_error(limit: int, as_bytes: bool) -> None:
    original_limit = sys.getrecursionlimit()
    configured_limit = min(limit, original_limit)
    raw = '{"fixture_token":"fixture-tokenlike-depth-secret","nested":'
    raw += "[" * 20000 + "0" + "]" * 20000 + "}"
    try:
        sys.setrecursionlimit(configured_limit)
        with pytest.raises(ValueError) as raised:
            strict_json_object(raw.encode() if as_bytes else raw)
        assert type(raised.value) is ValueError
        assert str(raised.value) == "JSON structure outside limit"
        rendered = "".join(traceback.format_exception(raised.value))
        assert "fixture-tokenlike-depth-secret" not in rendered
        assert raw not in rendered
        assert sys.getrecursionlimit() == configured_limit
        assert strict_json_object('{"ok":true}') == {"ok": True}
    finally:
        sys.setrecursionlimit(original_limit)


@pytest.mark.parametrize("raw", ['{"a":1,"a":2}', '{"outer":{"a":1,"a":2}}'])
def test_duplicate_keys_are_still_rejected(raw: str) -> None:
    with pytest.raises(ValueError, match=r"^duplicate JSON key$"):
        strict_json_object(raw)


def test_byte_budget_still_counts_utf8_bytes() -> None:
    raw = '{"text":"汉"}'
    size = len(raw.encode())
    assert strict_json_object(raw, size) == {"text": "汉"}
    with pytest.raises(ValueError, match=r"^JSON body outside limit$"):
        strict_json_object(raw, size - 1)


@pytest.mark.parametrize("raw", [b'{"a":"\xff"}', '{"a":"\\ud800"}'])
def test_unicode_errors_keep_the_original_error_class(raw: str | bytes) -> None:
    with pytest.raises(UnicodeError):
        strict_json_object(raw)


def test_node_budget_boundaries_remain_exact() -> None:
    assert strict_json_object('{"a":[0,1]}', maximum_nodes=5) == {"a": [0, 1]}
    with pytest.raises(ValueError, match=r"^JSON structure outside limit$"):
        strict_json_object('{"a":[0,1]}', maximum_nodes=4)
    raw = json.dumps({"items": [0] * 9997})
    assert len(strict_json_object(raw)["items"]) == 9997
    with pytest.raises(ValueError, match=r"^JSON structure outside limit$"):
        strict_json_object(json.dumps({"items": [0] * 9998}))


@pytest.mark.parametrize("budget", [0, 50001, True, 1.5])
def test_invalid_node_budget_is_not_relaxed(budget: object) -> None:
    with pytest.raises(ValueError, match=r"^JSON node budget outside limit$"):
        strict_json_object("{}", maximum_nodes=budget)


@pytest.mark.parametrize(
    "raw,message",
    [
        ('{"a":NaN}', "non-finite JSON number"),
        ('{"a":Infinity}', "non-finite JSON number"),
        ('{"a":1e999}', "non-finite JSON number"),
        ('{"a":"\\u0000"}', "JSON string contains NUL"),
        ("[]", "JSON object required"),
    ],
)
def test_existing_json_rejections_are_preserved(raw: str, message: str) -> None:
    with pytest.raises(ValueError, match="^" + message + "$"):
        strict_json_object(raw)
