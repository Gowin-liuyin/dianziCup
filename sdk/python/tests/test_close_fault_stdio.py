"""Observe real official stdio shutdown when an explicit pool finalizer fault occurs."""

import json
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from r18_test_paths import FIXTURES
from test_independent_native import CACHE, KEY, ROOT, RUN, TcpEvidence, record

MARKER = "synthetic-independent-close-marker-no-product-secret"


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("protocol", ["handshake", "modern"])
async def test_pool_close_fault_real_stdio_stderr_has_no_marker(protocol):
    async with TcpEvidence() as tcp:
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
        stderr_path = RUN / ("pool_close_fault_" + protocol + "_stderr.log")
        with stderr_path.open("w", encoding="utf-8") as stderr:
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
                assert result.is_error is False
                record("pool_close_fault_" + protocol + "_wire", wire)
        await tcp.wait(lambda: len(tcp.eof) == 1)
        stderr_value = stderr_path.read_text(encoding="utf-8")
        record(
            "pool_close_fault_" + protocol + "_observation",
            {
                "explicit_finalizer_fault_after_real_native_close": True,
                "actual_tcp_requests": tcp.requests,
                "actual_peer_eof": tcp.eof,
                "wire_marker": MARKER in json.dumps(wire),
                "stderr_marker": MARKER in stderr_value,
                "stderr_bytes": stderr_path.stat().st_size,
                "no_product_credentials_or_paid_calls": True,
            },
        )
        assert MARKER not in json.dumps(wire)
        assert MARKER not in stderr_value
        assert json.loads(stderr_value) == {"error": {"code": "backend_internal_error"}}
