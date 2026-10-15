"""独立响应元数据百分号编码反射探针；仅合成secret与socket fixture。"""

import json
import socket
import ssl
from datetime import datetime
from unittest.mock import patch
from urllib.parse import quote, unquote

from pydantic import SecretStr

from ai_intel.infrastructure import http_transport
from ai_intel.infrastructure.network import NetworkPolicy, OriginCredentials, create_network_gateway
from review_network_probes import SocketFixture


secret = "review/synthetic+credential=="
encoded_secret = quote(secret, safe="")
wire = (
    "HTTP/1.1 200 OK\r\nContent-Type: text/plain\r\nContent-Length: 2\r\n"
    f"Content-Location: https://registered.example/document?renamed={encoded_secret}\r\n"
    f"X-Trace-Echo: {encoded_secret}\r\n\r\nok"
).encode()
connection = SocketFixture(wire)
records = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]


def wrap(context, connection_socket, **options):
    assert context.verify_mode == ssl.CERT_REQUIRED and context.check_hostname
    connection_socket.sni = options["server_hostname"]
    return connection_socket


with (
    patch.object(http_transport.socket, "socket", lambda *args: connection),
    patch.object(http_transport.socket, "getaddrinfo", lambda *args, **kwargs: records),
    patch.object(http_transport.ssl.SSLContext, "wrap_socket", wrap),
):
    result = create_network_gateway(
        NetworkPolicy(("registered.example",)),
        OriginCredentials("https://registered.example", {"api-key": SecretStr(secret)}),
    ).fetch("https://registered.example/document")

print(json.dumps({
    "observed_at": datetime.now().astimezone().isoformat(),
    "fixture_only": True,
    "status_code": result.status_code,
    "connection_closed": connection.closed,
    "body_unchanged": result.body == b"ok",
    "content_location_fully_redacted": result.redacted_headers["Content-Location"] == "REDACTED",
    "trace_header_fully_redacted": result.redacted_headers["X-Trace-Echo"] == "REDACTED",
    "raw_secret_in_headers": secret in str(result.redacted_headers),
    "encoded_secret_recoverable_in_content_location": secret in unquote(result.redacted_headers["Content-Location"]),
    "encoded_secret_recoverable_in_trace_header": secret in unquote(result.redacted_headers["X-Trace-Echo"]),
}, indent=2))
