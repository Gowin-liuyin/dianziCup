"""两种官方wire的必需字段/终止语义；合成脱敏合同样本不计供应商live。"""

import pytest

from ai_intel.infrastructure.models.generation import GenerationFailure, decode_wire, parse_usage
from ai_intel.infrastructure.models.json_output import strict_json_object

OPENAI = (
    b'{"id":"fixture-chat","object":"chat.completion","model":"deepseek-flash",'
    b'"choices":[{"index":0,"finish_reason":"stop","message":{"role":"assistant",'
    b'"content":"{\\"ok\\":true}"}}],"usage":{"prompt_tokens":16,"completion_tokens":10,'
    b'"total_tokens":26,"prompt_tokens_details":{"cached_tokens":3}}}'
)
ANTHROPIC = (
    b'{"id":"fixture-msg","type":"message","role":"assistant","model":"deepseek-flash",'
    b'"stop_reason":"end_turn","content":[{"type":"text","text":"{\\"ok\\":true}"}],'
    b'"usage":{"input_tokens":16,"output_tokens":10,"cache_read_input_tokens":3,'
    b'"cache_creation_input_tokens":2}}'
)


@pytest.mark.parametrize("payload,anthropic", [(OPENAI, False), (ANTHROPIC, True)])
def test_official_wire_shape_success(payload, anthropic):
    parsed = strict_json_object(payload)
    result, reason = decode_wire(parsed, anthropic)
    assert result == '{"ok":true}'
    assert reason == ("end_turn" if anthropic else "stop")
    usage = parse_usage(parsed, anthropic)
    assert usage.input_tokens == 16 and usage.output_tokens == 10 and usage.cache_read_tokens == 3
    assert usage.cache_creation_tokens == (2 if anthropic else None)
    assert usage.total_tokens == (None if anthropic else 26)


@pytest.mark.parametrize("payload,anthropic", [(OPENAI, False), (ANTHROPIC, True)])
@pytest.mark.parametrize("remove", ["content", "finish", "role"])
def test_required_wire_fields_not_fabricated(payload, anthropic, remove):
    parsed = strict_json_object(payload)
    if anthropic:
        parsed.pop({"content": "content", "finish": "stop_reason", "role": "role"}[remove])
    elif remove == "finish":
        parsed["choices"][0].pop("finish_reason")
    else:
        parsed["choices"][0]["message"].pop(remove)
    with pytest.raises(GenerationFailure):
        decode_wire(parsed, anthropic)


def test_anthropic_tool_block_is_never_executed():
    parsed = strict_json_object(ANTHROPIC)
    parsed["content"] = [{"type": "tool_use", "name": "run_shell", "input": {"command": "fixture"}}]
    with pytest.raises(GenerationFailure, match="model_tool_call_forbidden"):
        decode_wire(parsed, True)


def test_openai_refusal_rejected_even_with_stop_reason():
    parsed = strict_json_object(OPENAI)
    parsed["choices"][0]["message"]["refusal"] = "fixture refusal"
    with pytest.raises(GenerationFailure, match="model_refused"):
        decode_wire(parsed, False)


@pytest.mark.parametrize(
    "usage",
    [
        {"input_tokens": -1},
        {"output_tokens": "10"},
        {"cache_read_input_tokens": True},
        {"cache_creation_input_tokens": 1.5},
    ],
)
def test_anthropic_usage_is_strict_integer_or_unknown(usage):
    with pytest.raises(GenerationFailure):
        parse_usage({"usage": usage}, True)


@pytest.mark.parametrize("details", [[], "invalid", False, 0])
def test_openai_cache_details_invalid_shape_is_not_unknown(details):
    with pytest.raises(GenerationFailure, match="model_wire_invalid"):
        parse_usage({"usage": {"prompt_tokens_details": details}}, False)
