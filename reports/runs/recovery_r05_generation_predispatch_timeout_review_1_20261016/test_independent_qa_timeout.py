"""QA第二次共享调用派发前失败，保留第一次真实fixture attempt。"""

import pytest
from test_r05_grounded_answer import candidate, evidence, prepared

from ai_intel.answering.contracts import GroundedAnswerFailure
from ai_intel.answering.grounding import generate_grounded_answer
from ai_intel.infrastructure.models import generation


def test_verifier_predispatch_timeout_preserves_first_attempt_without_second_post(monkeypatch):
    client, calls = prepared(monkeypatch, [candidate()], timeout=1.0)
    original = client.generate
    requested = []

    def generate(request, schema):
        requested.append(request)
        if len(requested) == 2:
            readings = iter((100.0, 103.0))
            monkeypatch.setattr(generation.time, "monotonic", lambda: next(readings, 103.0))
        return original(request, schema)

    monkeypatch.setattr(client, "generate", generate)
    with pytest.raises(GroundedAnswerFailure) as observed:
        generate_grounded_answer(client, "公告的修复版本？", (evidence(),))
    assert observed.value.code == "model_network_timeout"
    assert len(observed.value.attempts) == len(calls) == 1
    assert observed.value.attempts[0].outcome == "succeeded"
    assert observed.value.attempts[0].fee == "unknown"
    assert len(requested) == 2 and not any(item.allow_format_repair for item in requested)
