"""Loopback SDK transport and native object workers; no source or MinIO live claims."""

import hashlib
import json
import subprocess
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BufferedWriter, BytesIO
from unittest.mock import Mock

import pytest
from pydantic import SecretStr
from test_r07_source_report_reader import read_case

from ai_intel.infrastructure import content_store
from ai_intel.infrastructure.content_store import ContentStore
from ai_intel.infrastructure.minio_store import MinioContentStore, ObjectStoreUnavailableError

__all__ = ["read_case"]
PAYLOAD = "原文🙂\n".encode() * 20
DIGEST = hashlib.sha256(PAYLOAD).hexdigest()


@pytest.fixture
def sdk_endpoint():
    active = {"mode": "success", "requests": 0, "delay_seconds": 1.5}
    requested = threading.Event()
    disconnected = threading.Event()

    class ObjectHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def do_GET(self):
            active["requests"] += 1
            requested.set()
            mode = active["mode"]
            try:
                if mode == "headers":
                    time.sleep(active["delay_seconds"])
                self.send_response(200)
                self.send_header("Content-Length", str(len(PAYLOAD)))
                self.end_headers()
                if mode == "chunks":
                    self.wfile.write(PAYLOAD[:1])
                    self.wfile.flush()
                    time.sleep(active["delay_seconds"])
                    self.wfile.write(PAYLOAD[1:])
                elif mode == "drip":
                    for value in PAYLOAD:
                        self.wfile.write(bytes((value,)))
                        self.wfile.flush()
                        time.sleep(0.02)
                elif mode == "broken":
                    self.wfile.write(PAYLOAD[:5])
                    self.close_connection = True
                elif mode == "corrupt":
                    self.wfile.write(b"x" * len(PAYLOAD))
                else:
                    self.wfile.write(PAYLOAD)
            except (BrokenPipeError, ConnectionResetError):
                disconnected.set()

    server = ThreadingHTTPServer(("127.0.0.1", 0), ObjectHandler)
    server.daemon_threads = False
    thread = threading.Thread(target=server.serve_forever)
    thread.start()
    store = MinioContentStore(
        f"127.0.0.1:{server.server_port}",
        "fixture-private-objects",
        SecretStr("explicit-fixture-access"),
        SecretStr("explicit-fixture-secret"),
        secure=False,
        timeout_seconds=10,
        test_mode=True,
    )
    try:
        yield store, active, requested, disconnected
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=3)
        assert not thread.is_alive()


@pytest.mark.parametrize("mode", ("headers", "chunks", "drip"))
def test_sdk_deadline_stops_slow_headers_chunks_and_drip_and_reaps_worker(
    sdk_endpoint, monkeypatch, mode
):
    store, active, requested, disconnected = sdk_endpoint
    active["mode"] = mode
    spawned = []
    real_popen = subprocess.Popen

    def capture_process(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        spawned.append(process)
        assert "explicit-fixture-secret" not in str(args)
        assert "explicit-fixture-secret" not in str(kwargs["env"])
        return process

    monkeypatch.setattr(content_store.subprocess, "Popen", capture_process)
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="content_read_deadline_exhausted"):
        store.read_verified(DIGEST, deadline_monotonic=started + 1.0)
    elapsed = time.monotonic() - started
    assert elapsed <= 1.0
    assert requested.is_set()
    assert len(spawned) == 1 and spawned[0].poll() is not None
    assert all(stream.closed for stream in (spawned[0].stdin, spawned[0].stdout))
    if mode == "drip":
        assert disconnected.wait(timeout=0.5)


def test_native_local_worker_verifies_unicode_missing_hash_and_size(tmp_path):
    store = ContentStore(tmp_path / "explicit-fixture")
    stored = store.store_bytes(PAYLOAD)
    assert (
        store.read_verified(stored.content_hash, deadline_monotonic=time.monotonic() + 3) == PAYLOAD
    )
    with pytest.raises(FileNotFoundError):
        store.read_verified("a" * 64, deadline_monotonic=time.monotonic() + 3)
    stored.object_path.write_bytes(b"corrupt")
    with pytest.raises(ValueError):
        store.read_verified(stored.content_hash, deadline_monotonic=time.monotonic() + 3)
    stored.object_path.write_bytes(PAYLOAD)
    store.read_verified(stored.content_hash)
    empty = store.store_bytes(b"")
    assert store.read_verified(empty.content_hash, deadline_monotonic=time.monotonic() + 3) == b""


def test_original_five_second_budget_interrupts_real_sdk_io_before_5_2_second_headers(sdk_endpoint):
    store, active, requested, _ = sdk_endpoint
    active.update(mode="headers", delay_seconds=5.2)
    started = time.monotonic()
    with pytest.raises(TimeoutError):
        store.read_verified(DIGEST, deadline_monotonic=started + 5.0)
    assert requested.is_set()
    assert time.monotonic() - started <= 5.0


@pytest.mark.parametrize("deadline", (float("nan"), float("inf"), True, "deadline"))
def test_invalid_deadline_never_starts_native_or_network_io(sdk_endpoint, monkeypatch, deadline):
    store, active, _, _ = sdk_endpoint
    spawn = Mock(side_effect=AssertionError("invalid deadline started a process"))
    monkeypatch.setattr(content_store.subprocess, "Popen", spawn)
    with pytest.raises(ValueError, match="deadline must be finite"):
        store.read_verified(DIGEST, deadline_monotonic=deadline)
    assert active["requests"] == 0
    assert not spawn.called


def test_expired_and_insufficient_startup_budget_do_not_start_io(sdk_endpoint, monkeypatch):
    store, active, _, _ = sdk_endpoint
    spawn = Mock(side_effect=AssertionError("expired deadline started a process"))
    monkeypatch.setattr(content_store.subprocess, "Popen", spawn)
    for remaining in (-1, 0.01):
        with pytest.raises(TimeoutError):
            store.read_verified(DIGEST, deadline_monotonic=time.monotonic() + remaining)
    assert active["requests"] == 0 and not spawn.called


@pytest.mark.parametrize("mode", ("broken", "corrupt"))
def test_sdk_disconnect_and_checksum_failure_cannot_return_verified_content(sdk_endpoint, mode):
    store, active, _, _ = sdk_endpoint
    active["mode"] = mode
    expected = ObjectStoreUnavailableError if mode == "broken" else ValueError
    with pytest.raises(expected):
        store.read_verified(DIGEST, deadline_monotonic=time.monotonic() + 3)


def test_sdk_success_and_exact_byte_limit_are_verified(sdk_endpoint):
    store, _, _, _ = sdk_endpoint
    store._limit = len(PAYLOAD)
    assert store.read_verified(DIGEST, deadline_monotonic=time.monotonic() + 3) == PAYLOAD
    store._limit -= 1
    with pytest.raises(ValueError, match="byte limit"):
        store.read_verified(DIGEST, deadline_monotonic=time.monotonic() + 3)


def test_concurrent_sdk_reads_keep_independent_deadlines(sdk_endpoint):
    store, active, _, _ = sdk_endpoint
    active["mode"] = "chunks"

    def read_for(seconds):
        started = time.monotonic()
        try:
            payload = store.read_verified(DIGEST, deadline_monotonic=started + seconds)
        except TimeoutError:
            return "timeout", time.monotonic() - started
        return payload, time.monotonic() - started

    with ThreadPoolExecutor(max_workers=2) as executor:
        short = executor.submit(read_for, 0.8)
        long = executor.submit(read_for, 3.0)
        short_result, short_elapsed = short.result()
        long_result, long_elapsed = long.result()
    assert short_result == "timeout" and short_elapsed <= 0.8
    assert long_result == PAYLOAD and long_elapsed < 3


def test_cancellation_reaps_worker_and_releases_capacity(sdk_endpoint, monkeypatch):
    store, _, _, _ = sdk_endpoint
    spawned = []
    real_popen = subprocess.Popen

    def cancel_communication(*args, **kwargs):
        process = real_popen(*args, **kwargs)
        spawned.append(process)
        process.communicate = Mock(side_effect=KeyboardInterrupt)
        return process

    with monkeypatch.context() as cancellation_patch:
        cancellation_patch.setattr(content_store.subprocess, "Popen", cancel_communication)
        with pytest.raises(KeyboardInterrupt):
            store.read_verified(DIGEST, deadline_monotonic=time.monotonic() + 3)
    assert len(spawned) == 1 and spawned[0].poll() is not None
    assert all(stream.closed for stream in (spawned[0].stdin, spawned[0].stdout))
    assert store.read_verified(DIGEST, deadline_monotonic=time.monotonic() + 3) == PAYLOAD


def test_reader_uses_frozen_metadata_without_io_transaction_and_forwards_original_deadline(
    read_case, monkeypatch
):
    active = {"transaction": False}

    @contextmanager
    def transaction():
        assert not active["transaction"]
        active["transaction"] = True
        try:
            yield
        finally:
            active["transaction"] = False

    read_case.connection.begin.side_effect = transaction
    deadline = time.monotonic() + 3

    def observe_io(content_hash, *, deadline_monotonic=None):
        assert not active["transaction"]
        assert read_case.connection.begin.call_count == 1
        assert deadline_monotonic == deadline
        return read_case.storage.read_verified(content_hash, deadline_monotonic=deadline_monotonic)

    read_case.store.read_verified.side_effect = observe_io
    result = read_case.reader.read(read_case.request, deadline)
    assert result.status == "reported"
    assert read_case.connection.begin.call_count == 2
    assert not read_case.connection.execute.called


def test_storage_timeout_is_not_wrapped_as_missing_or_partial(read_case):
    read_case.store.read_verified.side_effect = TimeoutError("transport total deadline exhausted")
    with pytest.raises(TimeoutError, match="fact_proof_deadline_exhausted"):
        read_case.reader.read(read_case.request, time.monotonic() + 3)
    assert read_case.connection.begin.call_count == 1


@pytest.mark.parametrize("request_bytes", (b"x" * 8365, "汉".encode() * 1400))
def test_final_utf8_request_limit_fails_before_pipe_or_process_creation(monkeypatch, request_bytes):
    spawn = Mock(side_effect=AssertionError("oversized request started native IO"))
    monkeypatch.setattr(content_store.subprocess, "Popen", spawn)
    with pytest.raises(ValueError, match="content_read_request_byte_limit_exceeded"):
        content_store._read_with_deadline(request_bytes, time.monotonic() + 0.15, 1024)
    assert not spawn.called


def test_short_deadline_interrupts_small_native_request_before_guard_startup(tmp_path):
    request = json.dumps(
        {
            "storage": "local",
            "root_directory": str(tmp_path),
            "content_hash": DIGEST,
            "remaining_seconds": 0.15,
            "byte_limit": 1024,
        }
    ).encode()
    started = time.monotonic()
    with pytest.raises(TimeoutError, match="content_read_deadline_exhausted"):
        content_store._read_with_deadline(request, started + 0.15, 1024)
    assert time.monotonic() - started <= 0.15


@pytest.mark.parametrize("failure", ("stop", "reap", "pipe"))
@pytest.mark.parametrize("primary", (TimeoutError, KeyboardInterrupt))
def test_cleanup_preserves_primary_exception_keeps_failed_owner_and_blocks_reuse(
    monkeypatch, failure, primary
):
    capacity = threading.BoundedSemaphore(1)
    failed_owners = {}
    stdin, stdout = BufferedWriter(BytesIO()), BytesIO()
    process = Mock(spec=subprocess.Popen)
    process.pid = 98765
    process.stdin, process.stdout = stdin, stdout
    process.poll.return_value = None
    process.communicate.side_effect = primary("original fixed diagnostic")
    if failure == "stop":
        process.kill.side_effect = OSError("fixture stop failure")
    elif failure == "reap":
        process.wait.side_effect = subprocess.TimeoutExpired("fixed worker", 0)
    else:
        stdout.close = Mock(side_effect=OSError("fixture pipe close failure"))
    monkeypatch.setattr(content_store, "_CONTENT_READ_CAPACITY", capacity)
    monkeypatch.setattr(content_store, "_FAILED_CONTENT_READS", failed_owners)
    monkeypatch.setattr(content_store, "_WindowsContentReadOwner", Mock())
    monkeypatch.setattr(content_store.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(content_store, "_require_fresh_request_pipe_capacity", lambda *args: None)
    try:
        with pytest.raises(primary, match="original fixed diagnostic") as caught:
            content_store._read_with_deadline(b"{}", time.monotonic() + 1, 1024)
        assert any("content_read_worker_cleanup_failed" in note for note in caught.value.__notes__)
        assert failed_owners[process.pid].process is process
        assert not capacity.acquire(blocking=False)
        assert process.wait.called
        if failure != "reap":
            assert stdin.closed
    finally:
        stdin.close()
        if failure != "pipe":
            stdout.close()


def test_zero_or_unknown_fresh_pipe_capacity_never_writes_config(monkeypatch):
    stdin, stdout = BufferedWriter(BytesIO()), BytesIO()
    process = Mock(spec=subprocess.Popen)
    process.pid = 87654
    process.stdin, process.stdout = stdin, stdout
    process.poll.return_value = None
    monkeypatch.setattr(content_store.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(content_store, "_WindowsContentReadOwner", Mock())
    monkeypatch.setattr(
        content_store,
        "_require_fresh_request_pipe_capacity",
        Mock(side_effect=OSError("content_read_request_pipe_capacity_unavailable")),
    )
    with pytest.raises(OSError, match="pipe_capacity_unavailable"):
        content_store._read_with_deadline(b"{}", time.monotonic() + 1, 1024)
    assert not process.communicate.called
    assert stdin.closed and stdout.closed


@pytest.mark.parametrize("failure", ("guardian", "reader"))
def test_unconfirmed_guardian_or_reader_retains_owner_without_closing_busy_stdout(
    monkeypatch, failure
):
    stdin, stdout = BufferedWriter(BytesIO()), BytesIO()
    process = Mock(spec=subprocess.Popen)
    process.pid, process.stdin, process.stdout = 76543, stdin, stdout
    process.poll.return_value = None
    process.communicate.side_effect = TimeoutError("original deadline")
    native_owner = Mock()
    if failure == "guardian":
        native_owner.confirm_terminal.side_effect = OSError("guardian still active")
    else:

        class HeldReader(threading.Thread):
            def join(self, timeout=None):
                assert timeout is not None and timeout <= 1

            def is_alive(self):
                return True

        process.stdout_thread = HeldReader()
    failed_owners = {}
    capacity = threading.BoundedSemaphore(1)
    monkeypatch.setattr(content_store, "_CONTENT_READ_CAPACITY", capacity)
    monkeypatch.setattr(content_store, "_FAILED_CONTENT_READS", failed_owners)
    monkeypatch.setattr(content_store, "_WindowsContentReadOwner", Mock(return_value=native_owner))
    monkeypatch.setattr(content_store.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(content_store, "_require_fresh_request_pipe_capacity", lambda *args: None)
    try:
        with pytest.raises(TimeoutError, match="original deadline"):
            content_store._read_with_deadline(b"{}", time.monotonic() + 1, 1024)
        assert failed_owners[process.pid].process is process
        assert not capacity.acquire(blocking=False)
        if failure == "reader":
            assert not stdout.closed
    finally:
        stdin.close()
        stdout.close()


@pytest.mark.parametrize(
    "scenario",
    ("normal", "gone", "after_exit", "enumeration", "permission", "query", "close", "held"),
)
def test_native_guardian_identity_and_terminal_checks_fail_closed(monkeypatch, scenario):
    error_state = {"value": 0}
    monkeypatch.setattr(
        content_store.ctypes, "get_last_error", lambda: error_state["value"], raising=False
    )
    monkeypatch.setattr(
        content_store.ctypes,
        "set_last_error",
        lambda value: error_state.update(value=value),
        raising=False,
    )
    kernel = Mock()

    def process_times(handle, creation, exited, *unused):
        if scenario == "query" and handle == 77:
            return False
        creation._obj.value = 10 if handle == 11 else (21 if scenario == "after_exit" else 15)
        exited._obj.value = 20 if handle == 11 else 0
        return True

    def first(snapshot, entry):
        entry._obj.parent, entry._obj.pid = 1234, 2345
        return True

    def following(snapshot, entry):
        error_state["value"] = 5 if scenario == "enumeration" else 18
        return False

    def open_process(*args):
        if scenario in {"gone", "permission"}:
            error_state["value"] = 87 if scenario == "gone" else 5
            return None
        return 77

    kernel.WaitForSingleObject.side_effect = lambda handle, timeout: (
        258 if scenario == "held" and handle == 77 else 0
    )
    kernel.GetProcessTimes.side_effect = process_times
    kernel.CreateToolhelp32Snapshot.return_value = 99
    kernel.Process32FirstW.side_effect, kernel.Process32NextW.side_effect = first, following
    kernel.OpenProcess.side_effect = open_process
    kernel.CloseHandle.side_effect = lambda handle: not (scenario == "close" and handle == 77)
    owner = object.__new__(content_store._WindowsContentReadOwner)
    owner._kernel, owner._worker_pid, owner._worker_handle, owner._handles = kernel, 1234, 11, [11]
    if scenario in {"normal", "gone"}:
        owner.confirm_terminal(time.monotonic() + 1)
        assert owner._handles == []
    else:
        with pytest.raises(OSError):
            owner.confirm_terminal(time.monotonic() + 1)
        assert owner._handles
    assert kernel.WaitForSingleObject.call_args_list[0].args == (11, 0)
    if scenario == "after_exit":
        assert kernel.WaitForSingleObject.call_count == 1


@pytest.mark.parametrize("stage", ("kill", "wait", "guardian", "reader", "stdin", "stdout"))
@pytest.mark.parametrize("primary_type", (TimeoutError, KeyboardInterrupt, None))
@pytest.mark.parametrize("cancel_type", (KeyboardInterrupt, SystemExit))
def test_cleanup_interruption_preserves_existing_error_and_retains_resource_owner(
    monkeypatch, stage, primary_type, cancel_type
):
    capacity, owners = threading.BoundedSemaphore(1), {}
    stdin, stdout = BufferedWriter(BytesIO()), BytesIO()
    close_stdin, close_stdout = stdin.close, stdout.close
    process = Mock(spec=subprocess.Popen)
    process.pid, process.stdin, process.stdout = 98765, stdin, stdout
    process.poll.return_value = None
    process.returncode = 0
    primary = primary_type("original read failure") if primary_type else None
    cancellation = cancel_type("cleanup interruption")
    if primary:
        process.communicate.side_effect = primary
    else:
        process.communicate.return_value = (b"Opayload", None)
    native = Mock()
    if stage in {"kill", "wait"}:
        getattr(process, stage).side_effect = cancellation
    elif stage == "guardian":
        native.confirm_terminal.side_effect = cancellation
    elif stage == "reader":

        class InterruptedReader(threading.Thread):
            def join(self, timeout=None):
                raise cancellation

            def is_alive(self):
                return False

        process.stdout_thread = InterruptedReader()
    else:
        (stdin if stage == "stdin" else stdout).close = Mock(side_effect=cancellation)
    monkeypatch.setattr(content_store, "_CONTENT_READ_CAPACITY", capacity)
    monkeypatch.setattr(content_store, "_FAILED_CONTENT_READS", owners)
    monkeypatch.setattr(content_store, "_WindowsContentReadOwner", Mock(return_value=native))
    monkeypatch.setattr(content_store.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(content_store, "_require_fresh_request_pipe_capacity", lambda *args: None)
    caught = None
    try:
        try:
            content_store._read_with_deadline(b"{}", time.monotonic() + 1, 1024)
        except BaseException as error:
            caught = error
        assert caught is (primary or cancellation)
        assert owners[process.pid].process is process
        assert owners[process.pid].native is native
        assert not capacity.acquire(blocking=False)
        assert process.wait.called
        if stage != "stdin":
            assert stdin.closed
    finally:
        close_stdin()
        close_stdout()
