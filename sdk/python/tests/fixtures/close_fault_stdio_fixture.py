"""Explicit synthetic close fault; native HTTPX requests and pool close remain real."""

from ai_intel_client.client import DianziClient
from ai_intel_client.mcp_stdio import main

original_from_environment = DianziClient.from_environment


def fixture_from_environment(environment=None):
    client = original_from_environment(environment)
    native_close = client._async_http.aclose

    async def synthetic_close_fault():
        await native_close()
        raise RuntimeError("synthetic-independent-close-marker-no-product-secret")

    client._async_http.aclose = synthetic_close_fault
    return client


DianziClient.from_environment = staticmethod(fixture_from_environment)

if __name__ == "__main__":
    raise SystemExit(main())
