"""Real fixture bytes test one-attempt proof reuse; no model, network, or private store is used."""

import gc
import hashlib
import time
import weakref
from dataclasses import FrozenInstanceError, replace
from unittest.mock import MagicMock

import pytest
from tests.unit.test_detached_job_executor import execution_trace as execution_trace
from tests.unit.test_r16_fan_in_runtime import CONTEXT, completion_request
from tests.unit.test_r16_revalidation_runtime import KEY, reference

from ai_intel.api.actor_references import actor_reference_from_payload, actor_reference_payload
from ai_intel.infrastructure.content_store import ContentStorage, ContentStore
from ai_intel.revalidation import runtime_policy
from ai_intel.revalidation.verified_content import (
    MAX_VERIFIED_CONTENT_BYTES,
    FrozenVerifiedContent,
    VerificationBudgetExceeded,
    VerifiedContentInvalid,
    VerifiedContentRecorder,
    VerifiedFanInResult,
    VerifiedSourceProof,
)
from ai_intel.workers import executor
from ai_intel.workers.executor import JobExecutionError, JobExecutionResult
from ai_intel.workers.jobs import JobLeaseLostError

SOURCE = b"PRIVATE_FIXTURE_SOURCE: original immutable bytes"
SOURCE_HASH = hashlib.sha256(SOURCE).hexdigest()


def proof(**updates):
    request_bytes = completion_request().model_dump_json().encode()
    values = dict(
        job_id=CONTEXT.job_id,
        worker_id=CONTEXT.worker_id,
        attempt_count=CONTEXT.attempt_count,
        tenant_id=CONTEXT.tenant_id,
        actor=reference(),
        request_sha256=hashlib.sha256(request_bytes).hexdigest(),
        content_by_hash={SOURCE_HASH: SOURCE},
    )
    return VerifiedSourceProof(**{**values, **updates})


def test_public_reads_reopen_storage_but_freeze_deduplicated_immutable_bytes():
    store = MagicMock(spec=ContentStorage)
    store.read_verified.return_value = SOURCE
    recorder = VerifiedContentRecorder(store, {SOURCE_HASH: len(SOURCE)})
    assert recorder.read_verified(SOURCE_HASH) == SOURCE
    snapshot = recorder.freeze()
    assert recorder.read_verified(SOURCE_HASH) == SOURCE
    assert store.read_verified.call_count == 2
    assert dict(snapshot) == {SOURCE_HASH: SOURCE}
    with pytest.raises(TypeError):
        snapshot[SOURCE_HASH] = b"changed"
    with pytest.raises(PermissionError):
        recorder.store_bytes(b"cannot write")
    with pytest.raises(PermissionError):
        recorder.delete_object(SOURCE_HASH)
    store.store_bytes.assert_not_called()
    store.delete_object.assert_not_called()


def test_recorder_forwards_original_deadline_without_wrapping_timeout():
    store = MagicMock(spec=ContentStorage)
    recorder = VerifiedContentRecorder(store, {SOURCE_HASH: len(SOURCE)})
    deadline = time.monotonic() + 2
    store.read_verified.side_effect = TimeoutError("content_read_deadline_exhausted")
    with pytest.raises(TimeoutError, match="content_read_deadline_exhausted"):
        recorder.read_verified(SOURCE_HASH, deadline_monotonic=deadline)
    store.read_verified.assert_called_once_with(SOURCE_HASH, deadline_monotonic=deadline)
    assert dict(recorder.freeze()) == {}


def test_expired_recorder_deadline_never_opens_underlying_store():
    store = MagicMock(spec=ContentStorage)
    recorder = VerifiedContentRecorder(store, {SOURCE_HASH: len(SOURCE)})
    with pytest.raises(TimeoutError):
        recorder.read_verified(SOURCE_HASH, deadline_monotonic=time.monotonic() - 1)
    store.read_verified.assert_not_called()
    assert dict(recorder.freeze()) == {}


def test_frozen_verified_content_respects_deadline_without_external_fallback():
    frozen = FrozenVerifiedContent(proof())
    assert frozen.read_verified(SOURCE_HASH, deadline_monotonic=time.monotonic() + 2) == SOURCE
    with pytest.raises(TimeoutError):
        frozen.read_verified(SOURCE_HASH, deadline_monotonic=time.monotonic() - 1)
    with pytest.raises(ValueError, match="deadline must be finite"):
        frozen.read_verified(SOURCE_HASH, deadline_monotonic=float("nan"))


def test_proof_copies_input_mapping_and_hides_raw_bytes_from_result_representation():
    original = {SOURCE_HASH: SOURCE}
    verified = proof(content_by_hash=original)
    original.clear()
    assert FrozenVerifiedContent(verified).read_verified(SOURCE_HASH) == SOURCE
    with pytest.raises(FrozenInstanceError):
        verified.attempt_count = 2
    result = VerifiedFanInResult(proof=verified)
    assert isinstance(result, JobExecutionResult)
    assert "PRIVATE_FIXTURE_SOURCE" not in repr(result)
    assert "PRIVATE_FIXTURE_SOURCE" not in repr(verified)


def test_frozen_guard_reads_have_no_store_fallback_after_storage_shutdown():
    store = MagicMock(spec=ContentStorage)
    store.read_verified.return_value = SOURCE
    recorder = VerifiedContentRecorder(store, {SOURCE_HASH: len(SOURCE)})
    recorder.read_verified(SOURCE_HASH)
    verified = proof(content_by_hash=recorder.freeze())
    store.read_verified.side_effect = FileNotFoundError("fixture storage shut down")
    frozen = FrozenVerifiedContent(verified)
    assert frozen.read_verified(SOURCE_HASH) == SOURCE
    with pytest.raises(VerifiedContentInvalid, match="source_unavailable"):
        frozen.read_verified(hashlib.sha256(b"new source").hexdigest())
    assert store.read_verified.call_count == 1
    with pytest.raises(PermissionError):
        frozen.store_bytes(SOURCE)
    with pytest.raises(PermissionError):
        frozen.delete_object(SOURCE_HASH)


def test_tampered_original_storage_cannot_create_a_proof(tmp_path):
    store = ContentStore(tmp_path / "fixture-content")
    stored = store.store_bytes(SOURCE)
    store.object_path_for_hash(stored.content_hash).write_bytes(b"tampered fixture bytes")
    recorder = VerifiedContentRecorder(store, {stored.content_hash: len(SOURCE)})
    with pytest.raises(VerifiedContentInvalid, match="source_invalid"):
        recorder.read_verified(stored.content_hash)
    assert dict(recorder.freeze()) == {}


def test_total_64_mib_budget_stops_the_next_new_hash_before_external_io():
    assert MAX_VERIFIED_CONTENT_BYTES == 64 * 1024 * 1024
    sources = {
        hashlib.sha256(body).hexdigest(): body
        for body in (bytes([index]) * (2 * 1024 * 1024) for index in range(33))
    }
    store = MagicMock(spec=ContentStorage)
    store.read_verified.side_effect = sources.__getitem__
    recorder = VerifiedContentRecorder(store, {key: len(body) for key, body in sources.items()})
    keys = tuple(sources)
    for key in keys[:32]:
        recorder.read_verified(key)
    assert sum(len(body) for body in recorder.freeze().values()) == 64 * 1024 * 1024
    with pytest.raises(VerificationBudgetExceeded, match="verification_budget_exhausted"):
        recorder.read_verified(keys[32])
    assert store.read_verified.call_count == 32


def test_missing_size_and_more_than_2000_reference_reads_never_fall_back_to_unbounded_io():
    store = MagicMock(spec=ContentStorage)
    recorder = VerifiedContentRecorder(store, {})
    with pytest.raises(VerifiedContentInvalid, match="size_unavailable"):
        recorder.read_verified(SOURCE_HASH)
    store.read_verified.assert_not_called()
    empty_hash = hashlib.sha256(b"").hexdigest()
    store.read_verified.return_value = b""
    recorder = VerifiedContentRecorder(store, {empty_hash: 0})
    for _ in range(2000):
        recorder.read_verified(empty_hash)
    with pytest.raises(VerificationBudgetExceeded):
        recorder.read_verified(empty_hash)
    assert store.read_verified.call_count == 2000


@pytest.mark.parametrize(
    "updates",
    [
        {"mode": "historical_cache"},
        {"content_by_hash": {SOURCE_HASH: b"wrong bytes"}},
        {"content_by_hash": {SOURCE_HASH: bytearray(SOURCE)}},
        {"request_sha256": "untrusted"},
    ],
)
def test_unverified_or_mutable_proof_inputs_are_rejected(updates):
    with pytest.raises(VerifiedContentInvalid):
        proof(**updates)


@pytest.mark.parametrize(
    "updates",
    [
        {"job_id": "other-job"},
        {"worker_id": "other-worker"},
        {"attempt_count": 2},
        {"tenant_id": "other-tenant"},
        {"request_sha256": "a" * 64},
    ],
)
def test_guard_cannot_reuse_proof_from_another_job_attempt_or_request(monkeypatch, updates):
    actor = reference()
    monkeypatch.setattr(runtime_policy, "_lock_bound_actor", lambda *args: actor)
    monkeypatch.setattr(runtime_policy, "require_current_scope", lambda *args: None)
    final_validation = MagicMock()
    monkeypatch.setattr(runtime_policy, "guard_completed_fan_in", final_validation)
    handler = runtime_policy.make_revalidation_change_handler(MagicMock(), MagicMock(), KEY)
    assert handler.completion_guard is not None
    result = VerifiedFanInResult(proof=replace(proof(), **updates))
    with pytest.raises(JobExecutionError, match="proof_identity_changed"):
        handler.completion_guard(
            MagicMock(), CONTEXT, completion_request().model_dump_json().encode(), result
        )
    final_validation.assert_not_called()


def test_guard_requires_verified_result_and_passes_only_frozen_content_to_original_validator(
    monkeypatch,
):
    actor = reference()
    monkeypatch.setattr(runtime_policy, "_lock_bound_actor", lambda *args: actor)
    monkeypatch.setattr(runtime_policy, "require_current_scope", lambda *args: None)
    final_validation = MagicMock()
    monkeypatch.setattr(runtime_policy, "guard_completed_fan_in", final_validation)
    handler = runtime_policy.make_revalidation_change_handler(MagicMock(), MagicMock(), KEY)
    assert handler.completion_guard is not None
    payload = completion_request().model_dump_json().encode()
    with pytest.raises(JobExecutionError, match="proof_unavailable"):
        handler.completion_guard(MagicMock(), CONTEXT, payload, JobExecutionResult())
    handler.completion_guard(MagicMock(), CONTEXT, payload, VerifiedFanInResult(proof=proof()))
    frozen_content = final_validation.call_args.args[3]
    assert isinstance(frozen_content, FrozenVerifiedContent)
    assert frozen_content.read_verified(SOURCE_HASH) == SOURCE


def test_proof_actor_is_bound_to_the_exact_current_owner(monkeypatch):
    actor = reference()
    other_payload = actor_reference_payload(actor)
    other_payload["user_id"] = "synthetic-other-owner"
    other = actor_reference_from_payload(other_payload)
    monkeypatch.setattr(runtime_policy, "_lock_bound_actor", lambda *args: actor)
    monkeypatch.setattr(runtime_policy, "require_current_scope", lambda *args: None)
    handler = runtime_policy.make_revalidation_change_handler(MagicMock(), MagicMock(), KEY)
    assert handler.completion_guard is not None
    with pytest.raises(JobExecutionError, match="proof_identity_changed"):
        handler.completion_guard(
            MagicMock(),
            CONTEXT,
            completion_request().model_dump_json().encode(),
            VerifiedFanInResult(proof=proof(actor=other)),
        )


def test_lost_final_lease_releases_result_proof_without_a_global_cache(
    execution_trace, monkeypatch
):
    events, _active, _payload = execution_trace
    references = []

    def handler(context, received):
        verified = proof(
            job_id=context.job_id,
            worker_id=context.worker_id,
            attempt_count=context.attempt_count,
            tenant_id=context.tenant_id,
            request_sha256=hashlib.sha256(received).hexdigest(),
        )
        references.append(weakref.ref(verified))
        return VerifiedFanInResult(proof=verified)

    def require_lease(session, *args, **kwargs):
        if session.number == 3:
            raise JobLeaseLostError("fixture lease lost")

    monkeypatch.setattr(executor, "require_job_lease", require_lease)
    guard = MagicMock(side_effect=AssertionError("lost lease must not run guard"))
    assert (
        executor.execute_job(
            object(),
            CONTEXT.job_id,
            CONTEXT.worker_id,
            {"server_handler": executor.DetachedJobHandler(handler, completion_guard=guard)},
        )
        == "lease_lost"
    )
    guard.assert_not_called()
    gc.collect()
    assert references[0]() is None
    assert not any(event[0] == "complete" for event in events)
