"""Independent real process exit observation and exception-family boundary checks."""

import asyncio
import json
import sys
from unittest.mock import patch

import pytest
from ai_intel_client import mcp_stdio
from anyio.abc import ByteReceiveStream
from mcp.client import stdio as stdio_module
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from r18_test_paths import FIXTURES
from test_independent_native import CACHE, KEY, ROOT, RUN, TcpEvidence, record

SAFE_ERROR = {"error": {"code": "backend_internal_error"}}


class RecordingStream(ByteReceiveStream):
    def __init__(self, native_stream, chunks):
        self.native_stream = native_stream
        self.chunks = chunks

    async def receive(self, max_bytes=65536):
        raw = await self.native_stream.receive(max_bytes)
        self.chunks.append(raw)
        return raw

    async def aclose(self):
        await self.native_stream.aclose()


class ObservedProcess:
    def __init__(self, native_process, chunks):
        self.native_process = native_process
        self.stdout = RecordingStream(native_process.stdout, chunks)

    def __getattr__(self, name):
        return getattr(self.native_process, name)


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("protocol", ["handshake", "modern"])
async def test_native_finalizer_fault_real_process_exit_three_and_exact_stderr(protocol):
    async with TcpEvidence() as tcp:
        processes = []
        stdout_chunks = []
        native_spawn = stdio_module._create_platform_compatible_process

        async def observe_real_spawn(*args, **kwargs):
            process = await native_spawn(*args, **kwargs)
            processes.append(process)
            return ObservedProcess(process, stdout_chunks)

        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(FIXTURES / "close_fault_stdio_fixture.py")],
            cwd=ROOT,
            env={
                "PYTHONPATH": str(ROOT / "sdk/python"),
                "PYTHONDONTWRITEBYTECODE": "1",
                "DIANZI_API_BASE_URL": tcp.origin,
                "DIANZI_API_KEY": KEY,
                "DIANZI_MCP_ENCODING_CACHE_FILE": CACHE,
            },
        )
        stderr_path = RUN / ("independent_process_" + protocol + "_stderr.log")
        with (
            patch.object(stdio_module, "_create_platform_compatible_process", observe_real_spawn),
            stderr_path.open("w", encoding="utf-8") as stderr,
        ):
            async with (
                stdio_client(parameters, errlog=stderr) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream) as session,
            ):
                if protocol == "modern":
                    await session.discover()
                else:
                    await session.initialize()
                result = await session.call_tool("ask", {"question": "idle", "mode": "library"})
                wire = result.model_dump(mode="json", by_alias=True, exclude_none=True)
                assert not result.is_error
                assert "synthetic-independent-close-marker" not in json.dumps(wire)
                record("independent_process_" + protocol + "_wire", wire)
        await tcp.wait(lambda: len(tcp.eof) == 1)
        assert len(processes) == 1 and processes[0].returncode == 3
        stdout_raw = b"".join(stdout_chunks)
        (RUN / ("independent_process_" + protocol + "_stdout.log")).write_bytes(stdout_raw)
        assert b"synthetic-independent-close-marker" not in stdout_raw
        stdout_messages = [json.loads(line) for line in stdout_raw.splitlines() if line]
        assert len(stdout_messages) >= 2
        assert all(message["jsonrpc"] == "2.0" for message in stdout_messages)
        raw = stderr_path.read_bytes()
        assert len(raw) == 45
        assert json.loads(raw) == SAFE_ERROR
        assert raw.replace(b"\r\n", b"\n") == (b'{"error":{"code":"backend_internal_error"}}\n')
        record(
            "independent_process_" + protocol,
            {
                "actual_subprocess_returncode": processes[0].returncode,
                "actual_tcp_requests": tcp.requests,
                "peer_eof": tcp.eof,
                "stderr_bytes": len(raw),
                "stderr_fixed_error": json.loads(raw),
                "exception_fields_or_trace": False,
                "wire_marker": False,
                "entire_stdout_bytes": len(stdout_raw),
                "entire_stdout_jsonrpc_messages": len(stdout_messages),
                "entire_stdout_marker": False,
                "spawn_observer": "same real official subprocess; no process or network mock",
                "finalizer_fault": "explicit synthetic fault after native close",
            },
        )


class NeverStringifyError(RuntimeError):
    def __str__(self):
        raise AssertionError("the error boundary must not stringify exception objects")

    def __repr__(self):
        raise AssertionError("the error boundary must not repr exception objects")


@pytest.mark.parametrize(
    "failure",
    [
        NeverStringifyError("synthetic-only 机密🙂\x1b[31m\nmarker"),
        ExceptionGroup("synthetic-group-marker", [ValueError("synthetic-child-marker")]),
    ],
    ids=["hostile-error-string", "ordinary-exception-group"],
)
def test_ordinary_exceptions_sanitized_without_stringification(failure, capsys):
    def injected_runner(coroutine):
        coroutine.close()
        raise failure

    with patch.object(mcp_stdio.asyncio, "run", injected_runner):
        assert mcp_stdio.main() == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    assert json.loads(captured.err) == SAFE_ERROR
    assert captured.err == '{"error":{"code":"backend_internal_error"}}\n'


@pytest.mark.parametrize("control", [KeyboardInterrupt(), asyncio.CancelledError()])
def test_base_exception_group_propagates_identity(control):
    group = BaseExceptionGroup("synthetic-control-group", [control])

    def injected_runner(coroutine):
        coroutine.close()
        raise group

    with (
        patch.object(mcp_stdio.asyncio, "run", injected_runner),
        pytest.raises(BaseExceptionGroup) as raised,
    ):
        mcp_stdio.main()
    assert raised.value is group and raised.value.exceptions[0] is control
