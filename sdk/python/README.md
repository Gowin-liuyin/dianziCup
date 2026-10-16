# AI intelligence Python client

The local R18 distribution is **ai-intel-client** version **0.1.0**, for
Python >=3.12,<3.13. It imports as ai_intel_client and installs the
**dianzi-intel** console command. This candidate has not been published to a
package index.

## Local installation

Install a reviewed wheel or source distribution in a virtual environment:

    python -m venv .venv
    .venv/Scripts/python -m pip install /path/to/ai_intel_client-0.1.0-py3-none-any.whl

On POSIX, use .venv/bin/python. An sdist can be installed with the same pip
command and /path/to/ai_intel_client-0.1.0.tar.gz; pip also prepares the pinned
setuptools build backend. Runtime dependencies are httpx and Pydantic and their
normal transitive dependencies. The base installation excludes MCP, tiktoken,
PostgreSQL drivers, Celery, semantic model runtimes and weights.

The optional **mcp** extra declares mcp==2.3.0 and tiktoken==0.14.0, matching
the repository's approved protocol dependencies. Install it only when using the
MCP adapter modules. The stdio module keeps its default two-tool profile; the
HTTP ASGI entry point explicitly exposes six tools. There is no separate MCP
console entry point. Installing the extra does not configure a backend or prove
live tool availability. The tokenizer requires the separately prepared official
o200k_base bytes, validated against the pinned SHA256 by the SDK. The vocabulary
cache is outside the distribution; missing or damaged bytes remain
**not_configured**. The 8,000-token protocol budget is not model billing usage.

## SDK and CLI

The top-level typed exports are DianziClient, DianziApiError,
DianziTransportError, AskRequest, AskResult, StackCheckRequest and
StackCheckResult. The eight public DTO classes are available from
ai_intel_client.models. The package contains the PEP 561 py.typed marker.

DianziClient provides synchronous ask / check_stack and asynchronous
ask_async / check_stack_async, plus context-managed cleanup and aclose.
The default network path uses the current SDK's overall operation deadlines,
four concurrent slots, bounded responses and execution cancellation. Explicit
synchronous test transports are fixture compatibility paths and do not prove
network cancellation. Public envelopes, subscriptions, task polling and large
inventory upload remain separate implementation slices.

    dianzi-intel --help
    dianzi-intel check --input stack.json
    dianzi-intel ask --input question.json
    python -c "from importlib.metadata import version; print(version('ai-intel-client'))"

JSON may also be supplied on stdin. Credentials come from DIANZI_API_KEY;
the deployment URL comes from DIANZI_API_BASE_URL. Do not put credentials in
arguments or input files. The current CLI has no --version option; inspect
the installed distribution version with the Python command above.

The current legacy check result has no structured risk confirmation. Successful
check and ask operations return exit code **2**, preserving uncertainty.
Configuration, execution, input, authentication and network errors return **3**.
Help returns **0**. Business exits 0/1 and severity filtering require the
separately reviewed public risk envelope; a successful legacy request must not
be described as proof that an asset is safe.

## Authenticated local MCP HTTP

Create an ASGI app in your deployment module using trusted configuration:

```python
from pathlib import Path

from ai_intel_client.http_transport import create_http_app
from ai_intel_client.output_budget import McpOutputBudget

app = create_http_app(
    "http://127.0.0.1:8000",
    McpOutputBudget(Path("/trusted/offline/o200k_base.tiktoken")),
    allowed_hosts=["127.0.0.1:8765"],
    allowed_origins=["http://127.0.0.1:8765"],
)
```

The ASGI host must enter the app lifespan and bind to loopback. The endpoint is
`/mcp`; exact configured Host and optional Origin values are checked with the
official MCP DNS rebinding protection. This module does not launch a listener
or change Codex/Claude settings. The backend base URL never comes from request
headers, URL or tool arguments. Forwarded headers cannot change it.

Every protocol request needs exactly one `Authorization: Bearer` header. This
includes initialize, tool discovery, notifications and GET/DELETE. Each request
creates its own async DianziClient, first reads `/api/v1/sources?limit=1` to apply
the backend's current credential/permission/rate checks, and closes the client
on completion, cancellation or disconnect. **That probe consumes one additional
backend read quota per HTTP request**, including discovery; a tool call also
consumes its normal backend quota. Authentication failure, revocation, 403, 429
and currentness errors retain their safe backend status/code. No response body,
credential or exception detail is included in transport errors.

The six tools are ask, check_stack, search_vulns, get_vuln, get_task_result and
list_sources. They share the existing typed SDK operations and complete result
budget of 8,000 o200k_base tokens and 1 MiB. Backend failures remain errors;
discovery does not prove that ask/check producers or live data are available.
The official stateless Streamable HTTP manager owns protocol parsing and version
rules. Legacy initialize uses a supported handshake version, such as
2025-11-25; the SDK's 2026-07-28 path uses its complete request metadata rather
than a legacy initialization handshake.

At most four HTTP requests, including authentication and body reads, run at
once. Each request has a finite default 120-second deadline, a body ceiling of
1 MiB, and shielded cleanup with a separate 5-second deadline. The trusted caller
may lower the request/body limits. Cleanup failure remains an error; the entry
point does not persist tokens, sessions or business state.

Bearer API key authentication is available here. **OAuth issuer/client flow:
not_configured**. There is no authorization-server metadata or token issuance;
PostgreSQL-backed OAuth and actual Codex/Claude/browser connections still need
their separate implementation and verification.

## License and verification scope

This SDK candidate is licensed under Apache-2.0; see LICENSE. That license
applies to this distribution and does not assign a license to the repository's
other components or upstream intelligence databases. Third-party code is not
vendored; independently installed dependencies retain their own licenses.
Setuptools 80.9.0 is a build dependency and is absent from runtime requirements.

The packaging checks inspect actual archive contents, rebuild the sdist, and
install both artifacts into separate virtual environments without system
site-packages. SDK regressions use explicit synthetic fixtures and local
loopback servers. These checks do not establish a PostgreSQL-backed product,
live model/source/asset observation, browser workflow, Codex/Claude connection,
the full public protocol or the three plugin integrations.
