"""Independent synthetic connection checks; no external DNS, sockets or provider calls."""

from concurrent.futures import ThreadPoolExecutor
import json
import threading

from pydantic import SecretStr
import pytest
from tests.unit.test_r07_model_fields import context, fixture_documents, fixture_outputs

from ai_intel.domain.enums import ClaimOrigin, DimensionStatus
from ai_intel.enrichment.field_sources import FieldEvidenceError
from ai_intel.enrichment.model_fields import extract_model_dimension
from ai_intel.infrastructure import http_transport
from ai_intel.infrastructure.models import generation
from ai_intel.infrastructure.models.generation import GenerationClient, GenerationLimits

PROVIDERS = ("openai", "anthropic", "deepseek_openai", "deepseek_anthropic")
DIMENSIONS = ("atlas", "versions", "literature", "poc")


class WireHarness:
    def __init__(self, monkeypatch, provider="openai", failure=None, timeout=2.0):
        self.documents = fixture_documents()
        self.outputs = fixture_outputs(self.documents)
        self.calls = []
        self.resolutions = []
        self.closed = []
        self.provider = provider
        self.failure = failure
        self.first_entered = threading.Event()
        self.release_first = threading.Event()
        self.second_entered = threading.Event()
        self.hold_first = False
        self.clock = None
        self.dns_cost = 0.0
        model = "deepseek-flash" if provider.startswith("deepseek") else "review-offline-model"
        self.client = GenerationClient(provider, model, SecretStr("synthetic-review-credential"),
            limits=GenerationLimits(total_timeout_seconds=timeout, max_concurrent_requests=1,
                                    max_calls=2))
        harness = self

        class Response:
            def __init__(self, body, status):
                self.body, self.status, self.position = body, status, 0

            def getheaders(self):
                return [("Content-Type", "application/json"),
                        ("Content-Length", str(len(self.body))),
                        ("Location", "https://example.invalid/forbidden")]

            def read(self, size):
                output = self.body[self.position:self.position + size]
                self.position += len(output)
                return output

            def close(self):
                harness.closed.append("response")

        class Connection:
            def __init__(self, hostname, port, address, deadline, tls_context):
                self.hostname, self.address, self.deadline = hostname, address, deadline

            def request(self, method, path, body, headers):
                payload = json.loads(body)
                anthropic = provider.endswith("anthropic")
                content = payload["messages"][0]["content"][0]["text"] if anthropic else payload["messages"][1]["content"]
                dimension = json.loads(content)["question"].split()[1]
                harness.calls.append({"dimension": dimension, "method": method,
                    "path": path, "host": self.hostname, "address": self.address,
                    "deadline": self.deadline.expires_at,
                    "maximum": payload.get("max_tokens", payload.get("max_completion_tokens"))})
                if len(harness.calls) == 1:
                    harness.first_entered.set()
                    if harness.hold_first:
                        assert harness.release_first.wait(1.0)
                else:
                    harness.second_entered.set()
                if harness.failure == "timeout":
                    raise TimeoutError("synthetic timeout")
                if harness.failure == "network":
                    raise OSError("synthetic network failure")
                raw = "invalid JSON" if harness.failure == "format" else json.dumps(harness.outputs[dimension])
                if anthropic:
                    wire = {"id": "independent-single", "type": "message", "role": "assistant",
                        "model": model, "stop_reason": "end_turn",
                        "content": [{"type": "text", "text": raw}],
                        "usage": {"input_tokens": 7, "output_tokens": 2}}
                else:
                    wire = {"id": "independent-single", "object": "chat.completion", "model": model,
                        "choices": [{"index": 0, "finish_reason": "stop", "message": {"role": "assistant", "content": raw}}],
                        "usage": {"prompt_tokens": 7, "completion_tokens": 2, "total_tokens": 9}}
                self.response = Response(json.dumps(wire).encode(),
                    harness.failure if type(harness.failure) is int else 200)

            def getresponse(self):
                return self.response

            def check_deadline(self):
                self.deadline.remaining_seconds()

            def expire(self):
                harness.closed.append("expired")

            def close(self):
                harness.closed.append("connection")

            def abort(self):
                harness.closed.append("abort")

        def resolve(hostname, deadline):
            harness.resolutions.append((hostname, deadline.expires_at))
            if harness.clock is not None:
                harness.clock[0] += harness.dns_cost
            return ["8.8.8.8", "1.1.1.1"]

        monkeypatch.setattr(http_transport, "_PinnedConnection", Connection)
        monkeypatch.setattr(self.client._gateway, "_resolve_addresses", resolve)

    def extract(self, dimension="versions", **changes):
        policy = {"budget_authorized": True, "content_is_private": False, "egress_granted": False}
        policy.update(changes)
        return extract_model_dimension(context(self.documents), self.documents, self.client,
                                       dimension=dimension, **policy)

    def assert_all_permits_free(self):
        for semaphore in (self.client._slots, self.client._gateway._request_slots):
            assert semaphore.acquire(blocking=False)
            try:
                assert not semaphore.acquire(blocking=False)
            finally:
                semaphore.release()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("dimension", DIMENSIONS)
def test_single_path_uses_actual_pinned_transport(monkeypatch, provider, dimension):
    harness = WireHarness(monkeypatch, provider)
    original = harness.client.limits
    result = harness.extract(dimension)
    assert len(harness.calls) == len(harness.resolutions) == len(result.model_attempts) == 1
    assert harness.calls[0]["dimension"] == dimension
    assert harness.calls[0]["maximum"] == 1024
    assert harness.calls[0]["method"] == "POST"
    assert harness.calls[0]["address"] == "8.8.8.8"
    assert len(result.attempts) == 1
    assert result.attempts[0].status == DimensionStatus.PENDING
    assert all(item.origin == ClaimOrigin.MODEL_HYPOTHESIS for item in result.attempts[0].candidates)
    metadata = result.model_attempts[0]
    assert metadata.call_id == "independent-single"
    assert metadata.usage.input_tokens == 7 and metadata.usage.output_tokens == 2
    assert metadata.fee == "unknown" and metadata.outcome == "succeeded"
    assert harness.client.limits is original
    assert harness.closed.count("response") == harness.closed.count("connection") == 1
    harness.assert_all_permits_free()


@pytest.mark.parametrize("provider", PROVIDERS)
@pytest.mark.parametrize("failure,code,status", [
    ("format", "model_format_invalid", DimensionStatus.FAILED),
    ("network", "model_network_failure", DimensionStatus.FAILED),
    ("timeout", "model_network_timeout", DimensionStatus.FAILED),
    (401, "model_permanent_auth_error", DimensionStatus.BLOCKED),
    (429, "model_rate_limited", DimensionStatus.FAILED),
    (503, "model_transient_server_error", DimensionStatus.FAILED),
    (302, "model_network_failure", DimensionStatus.FAILED)])
def test_each_wire_failure_has_one_call_and_safe_metadata(monkeypatch, provider, failure, code, status):
    harness = WireHarness(monkeypatch, provider, failure)
    result = harness.extract("poc")
    assert len(harness.calls) == len(harness.resolutions) == len(result.model_attempts) == 1
    assert len(result.attempts) == 1 and result.attempts[0].dimension == "poc"
    assert result.attempts[0].status == status
    assert result.attempts[0].error_code == result.model_attempts[0].outcome == code
    assert not result.attempts[0].candidates and result.model_attempts[0].fee == "unknown"
    harness.assert_all_permits_free()


@pytest.mark.parametrize("budget", [True, False, float("nan"), float("inf"), 1.0, "1024", None, 0, -1, 8193])
def test_non_integer_and_nonfinite_budgets_rejected_without_dns(monkeypatch, budget):
    harness = WireHarness(monkeypatch)
    with pytest.raises(FieldEvidenceError, match="^field_call_policy_invalid$"):
        harness.extract(total_output_token_budget=budget)
    assert not harness.calls and not harness.resolutions
    harness.assert_all_permits_free()


@pytest.mark.parametrize("dimension", [[], (), ["atlas", "poc"], ("poc", "poc"), {}, "", "ATLAS", "poc,versions", None, 1, True])
def test_single_api_never_accepts_multidimension_shapes(monkeypatch, dimension):
    harness = WireHarness(monkeypatch)
    with pytest.raises(FieldEvidenceError, match="^field_dimension_invalid$"):
        harness.extract(dimension)
    assert not harness.calls and not harness.resolutions
    harness.assert_all_permits_free()


@pytest.mark.parametrize("field", ["budget_authorized", "content_is_private", "egress_granted"])
@pytest.mark.parametrize("value", [1, None, "false", float("nan")])
def test_policy_flags_require_real_booleans(monkeypatch, field, value):
    harness = WireHarness(monkeypatch)
    with pytest.raises(FieldEvidenceError, match="^field_call_policy_invalid$"):
        harness.extract(**{field: value})
    assert not harness.calls and not harness.resolutions
    harness.assert_all_permits_free()


def test_oversized_deadline_does_not_mutate_or_take_any_permit(monkeypatch):
    harness = WireHarness(monkeypatch, timeout=20.000001)
    original = harness.client.limits
    for _ in range(3):
        with pytest.raises(FieldEvidenceError, match="^field_single_dimension_timeout_invalid$"):
            harness.extract()
        harness.assert_all_permits_free()
    assert harness.client.limits is original
    assert not harness.calls and not harness.resolutions


def test_concurrent_requests_share_one_permit_and_release_it(monkeypatch):
    harness = WireHarness(monkeypatch)
    harness.hold_first = True
    original = harness.client.limits
    second_started = threading.Event()

    def invoke_second():
        second_started.set()
        return harness.extract("poc")

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(harness.extract, "versions")
        assert harness.first_entered.wait(1.0)
        second = pool.submit(invoke_second)
        assert second_started.wait(1.0)
        assert not harness.second_entered.wait(0.05)
        harness.release_first.set()
        outcomes = [first.result(timeout=2), second.result(timeout=2)]
    assert [item["dimension"] for item in harness.calls] == ["versions", "poc"]
    assert all(item.attempts[0].candidates and len(item.model_attempts) == 1 for item in outcomes)
    assert harness.client.limits is original
    harness.assert_all_permits_free()


def test_waiting_for_occupied_permit_times_out_without_network_then_recovers(monkeypatch):
    harness = WireHarness(monkeypatch, timeout=0.05)
    assert harness.client._slots.acquire(blocking=False)
    try:
        result = harness.extract()
        assert result.attempts[0].error_code == "model_concurrency_timeout"
        assert result.attempts[0].status == DimensionStatus.FAILED
        assert result.model_attempts == ()
        assert not harness.calls and not harness.resolutions
    finally:
        harness.client._slots.release()
    harness.assert_all_permits_free()
    assert harness.extract().attempts[0].candidates
    harness.assert_all_permits_free()


@pytest.mark.parametrize("dns_cost", [1.0, 3.0])
def test_dns_spends_the_same_single_deadline(monkeypatch, dns_cost):
    harness = WireHarness(monkeypatch)
    harness.clock = [100.0]
    harness.dns_cost = dns_cost
    monkeypatch.setattr(generation.time, "monotonic", lambda: harness.clock[0])
    result = harness.extract()
    assert harness.resolutions[0][1] == 102.0
    if dns_cost == 1.0:
        assert harness.calls[0]["deadline"] == 102.0
        assert result.attempts[0].candidates
    else:
        assert harness.calls == []
        assert result.attempts[0].error_code == "model_network_timeout"
        assert len(result.model_attempts) == 1
    harness.assert_all_permits_free()
