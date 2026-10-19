"""The process entry point must propagate control exceptions rather than sanitize them."""

import asyncio
from unittest.mock import patch

import pytest
from ai_intel_client import mcp_stdio


@pytest.mark.parametrize("control", [KeyboardInterrupt(), SystemExit(71), asyncio.CancelledError()])
def test_stdio_main_propagates_control_exception(control):
    def controlled_runner(coroutine):
        coroutine.close()
        raise control

    with (
        patch.object(mcp_stdio.asyncio, "run", new=controlled_runner),
        pytest.raises(type(control)) as raised,
    ):
        mcp_stdio.main()
    assert raised.value is control
