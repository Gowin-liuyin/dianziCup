"""Local OS DNS comparisons and explicit child fixtures exercise the projection DNS seam."""

import asyncio
import json
import socket
import threading
import time
from collections.abc import Callable, Coroutine
from contextlib import suppress
from dataclasses import dataclass, field

import pytest

from ai_intel.infrastructure import neo4j_projection as projection

DNS_PORT = 7687
DNS_ORIGIN = ("127.0.0.1", DNS_PORT)
DNS_BYTE_CAPACITY = 64 * 1024
DNS_ADDRESS_CAPACITY = 64
SECRET_FIXTURE_KEY = "R10_DNS_SECRET_SENTINEL"
CHILD_ENVIRONMENT_KEYS = {"SystemRoot", "WINDIR", "TEMP", "TMP", "PYTHONUTF8", "PYTHONIOENCODING"}
EXPECTED_IPV4 = (int(socket.AF_INET), int(socket.SOCK_STREAM), socket.IPPROTO_TCP, "", DNS_ORIGIN)
IPV4_ROW = [
    int(socket.AF_INET),
    int(socket.SOCK_STREAM),
    socket.IPPROTO_TCP,
    "",
    ["127.0.0.1", DNS_PORT],
]
IPV6_ROW = [
    int(socket.AF_INET6),
    int(socket.SOCK_STREAM),
    socket.IPPROTO_TCP,
    "localhost",
    ["::1", DNS_PORT, 0, 0],
]
WORKER_INPUT = "import sys; sys.stdin.buffer.readline();\n"
HUNG_WORKER = WORKER_INPUT + "import time; time.sleep(60)"


def address_frame(rows: list[object]) -> bytes:
    return json.dumps({"ok": True, "addresses": rows}, separators=(",", ":")).encode()


def output_worker(payload: bytes) -> str:
    return WORKER_INPUT + f"import os; os.write(1, bytes.fromhex('{payload.hex()}'))"


def run_dns_loop[LookupResult](
    work: Callable[[asyncio.AbstractEventLoop], Coroutine[object, object, LookupResult]],
    *,
    timeout_seconds: float = 2.0,
    origin: tuple[str, int] | None = DNS_ORIGIN,
) -> LookupResult:
    loop = projection._ProjectionEventLoop(timeout_seconds, origin)

    def loop_factory() -> asyncio.AbstractEventLoop:
        asyncio.set_event_loop(loop)
        return loop

    try:
        with asyncio.Runner(loop_factory=loop_factory) as runner:
            return runner.run(work(loop))
    finally:
        asyncio.set_event_loop(None)


@dataclass
class DNSChildren:
    processes: list[asyncio.subprocess.Process] = field(default_factory=list)
    created: asyncio.Event = field(default_factory=asyncio.Event)
    wait_finished: set[int] = field(default_factory=set)
    waiting_for_reap: asyncio.Event = field(default_factory=asyncio.Event)
    first_reap_gate: asyncio.Event | None = None
    starting_count: int = 0
    active_peak: int = 0
    spawned_before_previous_reap: bool = False


@pytest.fixture
def dns_children(monkeypatch, request):
    observed = DNSChildren()
    create_subprocess_exec = asyncio.create_subprocess_exec

    async def record_child(*arguments: str, **options: object) -> asyncio.subprocess.Process:
        environment = options.get("env")
        if not isinstance(environment, dict) or SECRET_FIXTURE_KEY in environment:
            raise AssertionError("DNS child inherited the secret fixture variable")
        if set(environment) - CHILD_ENVIRONMENT_KEYS:
            raise AssertionError("DNS child environment exceeds its fixed allowlist")
        assert "-I" in arguments and "-S" in arguments
        assert "-X" in arguments and arguments[arguments.index("-X") + 1] == "utf8"
        assert not options.get("shell", False)
        if any(id(process) not in observed.wait_finished for process in observed.processes):
            observed.spawned_before_previous_reap = True
        observed.starting_count += 1
        active_count = sum(process.returncode is None for process in observed.processes)
        observed.active_peak = max(observed.active_peak, active_count + observed.starting_count)
        try:
            process = await create_subprocess_exec(*arguments, **options)
            observed.processes.append(process)
            wait = process.wait

            async def record_wait() -> int:
                returncode = await wait()
                if process is observed.processes[0] and observed.first_reap_gate is not None:
                    observed.waiting_for_reap.set()
                    await observed.first_reap_gate.wait()
                observed.wait_finished.add(id(process))
                return returncode

            monkeypatch.setattr(process, "wait", record_wait)
            observed.created.set()
            return process
        finally:
            observed.starting_count -= 1

    monkeypatch.setattr(asyncio, "create_subprocess_exec", record_child)
    try:
        yield observed
    finally:
        observation = {
            "nodeid": request.node.nodeid,
            "owned_children": [
                {
                    "pid": process.pid,
                    "returncode": process.returncode,
                    "waited": id(process) in observed.wait_finished,
                }
                for process in observed.processes
            ],
            "active_peak": observed.active_peak,
            "pending_creations": observed.starting_count,
            "spawned_before_previous_reap": observed.spawned_before_previous_reap,
        }
        print(json.dumps({"dns_child_observation": observation}, separators=(",", ":")))


async def reap_fixture_children(observed: DNSChildren) -> None:
    """A failed cleanup assertion must still leave the test's own child processes stopped."""
    for process in observed.processes:
        if process.returncode is None:
            with suppress(ProcessLookupError):
                process.kill()
        await asyncio.wait_for(process.wait(), timeout=1.0)


def assert_children_reaped(observed: DNSChildren) -> None:
    assert observed.processes
    assert all(process.returncode is not None for process in observed.processes)
    assert all(id(process) in observed.wait_finished for process in observed.processes)
    assert observed.starting_count == 0


@pytest.mark.parametrize(
    ("host", "family", "socket_type", "protocol", "flags"),
    [
        ("localhost", socket.AF_UNSPEC, socket.SOCK_STREAM, 0, 0),
        ("localhost", socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP, socket.AI_CANONNAME),
        ("localhost", socket.AF_INET6, socket.SOCK_DGRAM, socket.IPPROTO_UDP, 0),
        (
            "127.0.0.1",
            socket.AF_INET,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
        ),
        (
            "::1",
            socket.AF_INET6,
            socket.SOCK_STREAM,
            socket.IPPROTO_TCP,
            socket.AI_NUMERICHOST | socket.AI_NUMERICSERV,
        ),
        (
            b"127.0.0.1",
            socket.AF_INET,
            socket.SOCK_DGRAM,
            socket.IPPROTO_UDP,
            socket.AI_NUMERICHOST,
        ),
        ("127.0.0.1", socket.AF_INET6, socket.SOCK_STREAM, 0, socket.AI_NUMERICHOST),
        (
            "not-a-numeric-address-fixture",
            socket.AF_INET,
            socket.SOCK_STREAM,
            0,
            socket.AI_NUMERICHOST,
        ),
    ],
)
def test_fixed_origin_matches_the_same_os_getaddrinfo(
    monkeypatch, dns_children, host, family, socket_type, protocol, flags
):
    expected_error = None
    expected_addresses = None
    try:
        expected_addresses = socket.getaddrinfo(
            host, DNS_PORT, family, socket_type, protocol, flags
        )
    except socket.gaierror as error:
        expected_error = error

    def reject_executor(*args, **kwargs):
        raise AssertionError("Projection DNS must not enter the asyncio DNS executor")

    async def lookup(loop):
        monkeypatch.setattr(loop, "run_in_executor", reject_executor)
        try:
            if expected_error is not None:
                with pytest.raises(socket.gaierror) as caught:
                    await loop.getaddrinfo(
                        host,
                        DNS_PORT,
                        family=family,
                        type=socket_type,
                        proto=protocol,
                        flags=flags,
                    )
                assert caught.value.errno == expected_error.errno
                assert caught.value.strerror == expected_error.strerror
                assert str(caught.value) == str(expected_error)
            else:
                addresses = await loop.getaddrinfo(
                    host,
                    DNS_PORT,
                    family=family,
                    type=socket_type,
                    proto=protocol,
                    flags=flags,
                )
                assert addresses == expected_addresses
            assert_children_reaped(dns_children)
        finally:
            await reap_fixture_children(dns_children)

    origin_host = host.decode("ascii") if isinstance(host, bytes) else host
    run_dns_loop(lookup, origin=(origin_host, DNS_PORT))
    assert len(dns_children.processes) == 1


def test_decoder_preserves_ipv4_and_ipv6_rows_and_exact_capacity_boundaries():
    expected_ipv4 = (
        int(socket.AF_INET),
        int(socket.SOCK_STREAM),
        socket.IPPROTO_TCP,
        "",
        ("127.0.0.1", DNS_PORT),
    )
    expected_ipv6 = (
        int(socket.AF_INET6),
        int(socket.SOCK_STREAM),
        socket.IPPROTO_TCP,
        "localhost",
        ("::1", DNS_PORT, 0, 0),
    )
    assert projection._decode_address_info(address_frame([IPV4_ROW, IPV6_ROW])) == [
        expected_ipv4,
        expected_ipv6,
    ]
    row_limit_frame = address_frame([IPV4_ROW] * DNS_ADDRESS_CAPACITY)
    assert (
        projection._decode_address_info(row_limit_frame) == [expected_ipv4] * DNS_ADDRESS_CAPACITY
    )
    byte_limit_frame = address_frame([IPV4_ROW]).ljust(DNS_BYTE_CAPACITY, b" ")
    assert len(byte_limit_frame) == DNS_BYTE_CAPACITY
    assert projection._decode_address_info(byte_limit_frame) == [expected_ipv4]


@pytest.mark.parametrize("error_type", ["gaierror", "OSError"])
def test_decoder_preserves_os_error_errno_and_message(error_type):
    message = "explicit OS error fixture"
    payload = json.dumps(
        {
            "ok": False,
            "error_type": error_type,
            "errno": socket.EAI_NONAME,
            "message": message,
        }
    ).encode()
    expected_type = socket.gaierror if error_type == "gaierror" else OSError
    with pytest.raises(expected_type) as caught:
        projection._decode_address_info(payload)
    assert caught.value.errno == socket.EAI_NONAME
    assert caught.value.strerror == message


@pytest.mark.parametrize("error_type", [TypeError, ValueError, OverflowError, UnicodeError])
def test_decoder_preserves_the_other_declared_error_types(error_type):
    message = "explicit resolver input error fixture"
    payload = json.dumps(
        {
            "ok": False,
            "error_type": error_type.__name__,
            "errno": None,
            "message": message,
        }
    ).encode()
    with pytest.raises(error_type) as caught:
        projection._decode_address_info(payload)
    assert type(caught.value) is error_type
    assert str(caught.value) == message


@pytest.mark.parametrize(
    "payload",
    [
        b"\xff",
        address_frame([IPV4_ROW]).decode("utf-8").encode("utf-16"),
        address_frame([IPV4_ROW]).decode("utf-8").encode("utf-32"),
        b"{",
        b"[]",
        b"{}",
        b'{"ok":1,"addresses":[]}',
        b'{"ok":true,"addresses":[],"extra":0}',
        b'{"ok":true,"addresses":[],"ok":true}',
        b'{"ok":true,"addresses":[]}{}',
        b'{"ok":true,"addresses":NaN}',
        b'{"ok":true,"addresses":{}}',
        address_frame([[int(socket.AF_INET), int(socket.SOCK_STREAM), socket.IPPROTO_TCP, ""]]),
        address_frame(
            [
                [
                    int(socket.AF_INET),
                    int(socket.SOCK_STREAM),
                    socket.IPPROTO_TCP,
                    "",
                    ["127.0.0.1", DNS_PORT],
                    0,
                ]
            ]
        ),
        address_frame([[True, 1, 6, "", ["127.0.0.1", DNS_PORT]]]),
        address_frame([[int(socket.AF_INET), True, 6, "", ["127.0.0.1", DNS_PORT]]]),
        address_frame([[int(socket.AF_INET), 1, True, "", ["127.0.0.1", DNS_PORT]]]),
        address_frame([[99999, 1, 6, "", ["127.0.0.1", DNS_PORT]]]),
        address_frame([[int(socket.AF_INET), 1, 6, None, ["127.0.0.1", DNS_PORT]]]),
        address_frame([[int(socket.AF_INET), 1, 6, "", ["127.0.0.1", True]]]),
        address_frame([[int(socket.AF_INET), 1, 6, "", ["127.0.0.1", -1]]]),
        address_frame([[int(socket.AF_INET), 1, 6, "", ["127.0.0.1", 65536]]]),
        address_frame([[int(socket.AF_INET), 1, 6, "", ["127.0.0.1", DNS_PORT, 0, 0]]]),
        address_frame([[int(socket.AF_INET6), 1, 6, "", ["::1", DNS_PORT]]]),
        address_frame([[int(socket.AF_INET6), 1, 6, "", ["::1", DNS_PORT, True, 0]]]),
        address_frame([[int(socket.AF_INET6), 1, 6, "", ["::1", DNS_PORT, 0, True]]]),
        b'{"ok":false,"error_type":"KeyError","errno":null,"message":"fixture"}',
        b'{"ok":false,"error_type":"gaierror","errno":true,"message":"fixture"}',
        b'{"ok":false,"error_type":"gaierror","errno":1,"message":1}',
        b'{"ok":false,"error_type":"gaierror","errno":1,"message":"fixture","extra":0}',
    ],
)
def test_decoder_rejects_invalid_or_extra_frames(payload):
    with pytest.raises(OSError, match="invalid"):
        projection._decode_address_info(payload)


@pytest.mark.parametrize(
    "payload",
    [
        address_frame([IPV4_ROW] * (DNS_ADDRESS_CAPACITY + 1)),
        address_frame([IPV4_ROW]).ljust(DNS_BYTE_CAPACITY + 1, b" "),
    ],
    ids=["row_count_65", "byte_count_65537"],
)
def test_decoder_rejects_oversize_frames_without_truncating(payload):
    with pytest.raises(OSError, match="capacity"):
        projection._decode_address_info(payload)


@pytest.mark.parametrize(
    ("host", "port", "origin"),
    [
        ("other-origin-fixture", DNS_PORT, DNS_ORIGIN),
        ("127.0.0.1", DNS_PORT + 1, DNS_ORIGIN),
        ("127.0.0.1", None, DNS_ORIGIN),
        ("127.0.0.1", str(DNS_PORT), DNS_ORIGIN),
        ("127.0.0.1", True, ("127.0.0.1", 1)),
        ("127.0.0.1", DNS_PORT, None),
    ],
)
def test_other_origin_or_invalid_port_is_denied_before_starting_child(
    dns_children, host, port, origin
):
    async def lookup(loop):
        try:
            with pytest.raises(OSError):
                await loop.getaddrinfo(host, port)
        finally:
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup, origin=origin)
    assert not dns_children.processes
    assert dns_children.starting_count == 0


def test_actual_child_environment_does_not_inherit_secret_fixture(monkeypatch, dns_children):
    monkeypatch.setenv(SECRET_FIXTURE_KEY, "synthetic-secret-fixture-only")
    valid_payload = address_frame([IPV4_ROW])
    child_code = (
        WORKER_INPUT + "import os; "
        f"payload = b'invalid-inherited-fixture' if '{SECRET_FIXTURE_KEY}' in os.environ "
        f"else bytes.fromhex('{valid_payload.hex()}'); os.write(1, payload)"
    )
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", child_code)

    async def lookup(loop):
        try:
            assert await loop.getaddrinfo(*DNS_ORIGIN) == [
                (int(socket.AF_INET), int(socket.SOCK_STREAM), socket.IPPROTO_TCP, "", DNS_ORIGIN)
            ]
            assert_children_reaped(dns_children)
        finally:
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup)
    assert len(dns_children.processes) == 1


@pytest.mark.parametrize(
    "worker",
    [
        output_worker(b"\xff"),
        output_worker(b"{}"),
        output_worker(address_frame([IPV4_ROW]) + b"{}"),
        WORKER_INPUT + "import os; os.write(1, b'x' * 65537)",
        WORKER_INPUT + "raise SystemExit(7)",
    ],
)
def test_child_bad_extra_oversize_or_nonzero_output_is_rejected_and_reaped(
    monkeypatch, dns_children, worker
):
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", worker)

    async def lookup(loop):
        try:
            with pytest.raises(OSError) as caught:
                await loop.getaddrinfo(*DNS_ORIGIN)
            assert not isinstance(caught.value, TimeoutError)
            assert_children_reaped(dns_children)
            monkeypatch.setattr(
                projection, "_DNS_WORKER_CODE", output_worker(address_frame([IPV4_ROW]))
            )
            assert await loop.getaddrinfo(*DNS_ORIGIN) == [EXPECTED_IPV4]
            assert len(dns_children.processes) == 2
            assert not dns_children.spawned_before_previous_reap
            assert_children_reaped(dns_children)
        finally:
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup)


def test_hung_lookup_expires_at_point_two_seconds_reaps_child_and_creates_no_dns_threads(
    monkeypatch, dns_children
):
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", HUNG_WORKER)
    baseline_threads = {thread.ident for thread in threading.enumerate()}
    started = time.monotonic()

    async def lookup(loop):
        try:
            with pytest.raises(TimeoutError):
                await loop.getaddrinfo(*DNS_ORIGIN)
            assert_children_reaped(dns_children)
        finally:
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup, timeout_seconds=0.2)
    assert time.monotonic() - started < 0.75
    assert not [
        thread
        for thread in threading.enumerate()
        if thread.ident not in baseline_threads and thread.name.startswith("asyncio")
    ]


def test_simultaneous_hung_lookups_include_lock_wait_in_their_deadline(monkeypatch, dns_children):
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", HUNG_WORKER)

    async def lookup(loop):
        try:
            outcomes = await asyncio.gather(
                loop.getaddrinfo(*DNS_ORIGIN),
                loop.getaddrinfo(*DNS_ORIGIN),
                return_exceptions=True,
            )
            assert all(isinstance(outcome, TimeoutError) for outcome in outcomes)
            assert len(dns_children.processes) == 1
            assert dns_children.active_peak == 1
            assert_children_reaped(dns_children)
        finally:
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup, timeout_seconds=0.2)


def test_concurrent_successful_lookups_never_own_more_than_one_child(monkeypatch, dns_children):
    child_code = WORKER_INPUT + "import time; time.sleep(0.04);\n"
    child_code += output_worker(address_frame([IPV4_ROW])).removeprefix(WORKER_INPUT)
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", child_code)

    async def lookup(loop):
        try:
            outcomes = await asyncio.gather(*(loop.getaddrinfo(*DNS_ORIGIN) for _ in range(3)))
            assert all(
                outcome
                == [
                    (
                        int(socket.AF_INET),
                        int(socket.SOCK_STREAM),
                        socket.IPPROTO_TCP,
                        "",
                        DNS_ORIGIN,
                    )
                ]
                for outcome in outcomes
            )
            assert len(dns_children.processes) == 3
            assert dns_children.active_peak == 1
            assert not dns_children.spawned_before_previous_reap
            assert_children_reaped(dns_children)
        finally:
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup)


def test_cancelled_waiter_does_not_kill_another_lookup_or_prevent_the_next_request(
    monkeypatch, dns_children
):
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", HUNG_WORKER)

    async def lookup(loop):
        first = asyncio.create_task(loop.getaddrinfo(*DNS_ORIGIN))
        waiter = None
        try:
            await asyncio.wait_for(dns_children.created.wait(), timeout=1.0)
            waiter = asyncio.create_task(loop.getaddrinfo(*DNS_ORIGIN))
            await asyncio.sleep(0)
            waiter.cancel()
            with pytest.raises(asyncio.CancelledError):
                await waiter
            assert len(dns_children.processes) == 1
            assert not first.done()
            assert dns_children.processes[0].returncode is None
            first.cancel()
            with pytest.raises(asyncio.CancelledError):
                await first
            assert_children_reaped(dns_children)
            monkeypatch.setattr(
                projection, "_DNS_WORKER_CODE", output_worker(address_frame([IPV4_ROW]))
            )
            assert await loop.getaddrinfo(*DNS_ORIGIN) == [EXPECTED_IPV4]
            assert len(dns_children.processes) == 2
            assert dns_children.active_peak == 1
            assert not dns_children.spawned_before_previous_reap
            assert_children_reaped(dns_children)
        finally:
            tasks = [first]
            first.cancel()
            if waiter is not None:
                waiter.cancel()
                tasks.append(waiter)
            await asyncio.gather(*tasks, return_exceptions=True)
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup)


def test_next_child_cannot_spawn_before_the_previous_wait_has_completed(monkeypatch, dns_children):
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", output_worker(address_frame([IPV4_ROW])))

    async def lookup(loop):
        dns_children.first_reap_gate = asyncio.Event()
        first = asyncio.create_task(loop.getaddrinfo(*DNS_ORIGIN))
        second = asyncio.create_task(loop.getaddrinfo(*DNS_ORIGIN))
        try:
            await asyncio.wait_for(dns_children.waiting_for_reap.wait(), timeout=1.0)
            await asyncio.sleep(0)
            assert not first.done() and not second.done()
            assert len(dns_children.processes) == 1
            dns_children.first_reap_gate.set()
            assert await asyncio.gather(first, second) == [[EXPECTED_IPV4], [EXPECTED_IPV4]]
            assert len(dns_children.processes) == 2
            assert not dns_children.spawned_before_previous_reap
            assert_children_reaped(dns_children)
        finally:
            dns_children.first_reap_gate.set()
            first.cancel()
            second.cancel()
            await asyncio.gather(first, second, return_exceptions=True)
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup)


def test_initial_child_identity_failure_still_reaps_the_owned_process(monkeypatch, dns_children):
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", HUNG_WORKER)

    def identity_unavailable(pid: int) -> int:
        raise OSError("explicit initial identity lookup failure fixture")

    monkeypatch.setattr(projection, "_dns_process_birth", identity_unavailable)

    async def lookup(loop):
        try:
            with pytest.raises(OSError) as caught:
                await loop.getaddrinfo(*DNS_ORIGIN)
            assert not isinstance(caught.value, TimeoutError)
            assert_children_reaped(dns_children)
        finally:
            await reap_fixture_children(dns_children)

    run_dns_loop(lookup)


@pytest.mark.parametrize(
    "termination", ["cancel_active_lookup", "close_runner_with_pending_lookup"]
)
def test_explicit_task_cancel_or_runner_close_reaps_a_pending_lookup(
    monkeypatch, dns_children, termination
):
    monkeypatch.setattr(projection, "_DNS_WORKER_CODE", HUNG_WORKER)
    baseline_threads = {thread.ident for thread in threading.enumerate()}

    async def lookup(loop):
        task = asyncio.create_task(loop.getaddrinfo(*DNS_ORIGIN))
        try:
            await asyncio.wait_for(dns_children.created.wait(), timeout=1.0)
            assert len(dns_children.processes) == 1
            assert dns_children.processes[0].returncode is None
            if termination == "cancel_active_lookup":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
                assert_children_reaped(dns_children)
            return task
        except BaseException:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await reap_fixture_children(dns_children)
            raise

    task = run_dns_loop(lookup)
    assert task.cancelled()
    assert_children_reaped(dns_children)
    assert not [
        thread
        for thread in threading.enumerate()
        if thread.ident not in baseline_threads and thread.name.startswith("asyncio")
    ]
