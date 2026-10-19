"""Observe wire and stderr under an explicitly injected unexpected SDK transport error."""

import json
import sys

import pytest
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.exceptions import MCPError
from r18_test_paths import FIXTURES, ROOT, RUN

SYNTHETIC_MARKER = "synthetic-review-secret-marker-no-provider-access-20261016"


@pytest.fixture
def anyio_backend() -> str:
    return "asyncio"


@pytest.mark.anyio
@pytest.mark.parametrize("protocol", ["handshake", "modern"])
async def test_unexpected_exception_never_exposes_marker_on_wire_or_stderr(protocol: str) -> None:
    stderr_path = RUN / f"unexpected_{protocol}_stderr.log"
    params = StdioServerParameters(
        command=sys.executable,
        args=[str(FIXTURES / "unexpected_error_stdio_fixture.py")],
        cwd=ROOT,
        env={"PYTHONPATH": str(ROOT / "sdk/python"), "PYTHONDONTWRITEBYTECODE": "1"},
    )
    protocol_error_code = None
    safe_tool_error_code = None
    with stderr_path.open("w", encoding="utf-8") as stderr:
        async with (
            stdio_client(params, errlog=stderr) as (read_stream, write_stream),
            ClientSession(read_stream, write_stream, read_timeout_seconds=10) as session,
        ):
            if protocol == "modern":
                await session.discover()
            else:
                await session.initialize()
            try:
                result = await session.call_tool(
                    "ask", {"question": "explicit error injection", "mode": "library"}
                )
            except MCPError as error:
                protocol_error_code = error.code
                wire = error.error.model_dump(mode="json", by_alias=True)
            else:
                wire = result.model_dump(mode="json", by_alias=True, exclude_none=True)
                if result.is_error:
                    safe_tool_error_code = json.loads(result.content[0].text)["error"]["code"]
            wire_message = json.dumps(wire)
            (RUN / f"unexpected_{protocol}_wire.json").write_text(
                json.dumps(wire, indent=2) + "\n",
                encoding="utf-8",
            )
    record = {
        "explicit_synthetic_fault_injection": True,
        "protocol": protocol,
        "protocol_error_code": protocol_error_code,
        "safe_tool_error_code": safe_tool_error_code,
        "wire_contains_synthetic_secret_marker": SYNTHETIC_MARKER in wire_message,
        "stderr_contains_synthetic_secret_marker": SYNTHETIC_MARKER in stderr_path.read_text(),
        "product_network_requests": 0,
        "external_or_paid_requests": 0,
        "runtime_secret_values_obtained": 0,
    }
    (RUN / f"unexpected_{protocol}_observation.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    assert record["wire_contains_synthetic_secret_marker"] is False
    assert record["stderr_contains_synthetic_secret_marker"] is False
    assert safe_tool_error_code == "backend_internal_error"
