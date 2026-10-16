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
MCP adapter modules. The package includes the current two-operation MCP adapter
and stdio module, with no separate MCP console entry point. Preparing that extra
does not establish the remaining six public tools or an authenticated HTTP
transport. The tokenizer additionally requires the separately prepared official
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
