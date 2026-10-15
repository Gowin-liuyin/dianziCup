"""Standard-library HTTP transport connects exclusively to an already checked numeric IP."""

from __future__ import annotations

import http.client
import ipaddress
import queue
import socket
import ssl
import threading
from collections.abc import Iterable
from contextlib import suppress
from typing import Literal
from urllib.parse import urlsplit

from ai_intel.infrastructure.network import (
    NetworkPolicyViolation,
    NetworkRequestError,
    NetworkResolutionError,
    NetworkTimeoutError,
    NetworkTlsError,
    RequestDeadline,
    is_private_or_local,
)


class _PinnedConnection(http.client.HTTPConnection):
    def __init__(
        self,
        hostname: str,
        port: int,
        address: str,
        deadline: RequestDeadline,
        tls_context: ssl.SSLContext | None,
    ) -> None:
        super().__init__(hostname, port, timeout=deadline.remaining_seconds())
        self._address = address
        self._deadline = deadline
        self._tls_context = tls_context
        self._active_socket: socket.socket | None = None
        self._deadline_expired = False

    def connect(self) -> None:
        if is_private_or_local(self._address):
            raise NetworkPolicyViolation("connection address is private or local")
        family = (
            socket.AF_INET6 if ipaddress.ip_address(self._address).version == 6 else socket.AF_INET
        )
        connection_socket = socket.socket(family, socket.SOCK_STREAM)
        self.sock = connection_socket
        self._active_socket = connection_socket
        connection_socket.settimeout(self._deadline.remaining_seconds())
        connection_socket.connect((self._address, self.port))
        self._verify_peer(connection_socket)
        if self._tls_context:
            tls_socket = self._tls_context.wrap_socket(
                connection_socket,
                server_hostname=self.host,
                do_handshake_on_connect=False,
            )
            self.sock = tls_socket
            self._active_socket = tls_socket
            tls_socket.settimeout(self._deadline.remaining_seconds())
            tls_socket.do_handshake()
            self._verify_peer(tls_socket)

    def _verify_peer(self, connection_socket: socket.socket) -> None:
        peer = str(connection_socket.getpeername()[0])
        if is_private_or_local(peer) or ipaddress.ip_address(peer) != ipaddress.ip_address(
            self._address
        ):
            raise NetworkPolicyViolation("connection peer differs from checked address")

    def abort(self) -> None:
        """Shutdown also interrupts blocking header reads and TLS handshakes on deadline."""
        connection_socket = self._active_socket
        if connection_socket is not None:
            with suppress(OSError):
                connection_socket.shutdown(socket.SHUT_RDWR)
            connection_socket.close()
        self.close()

    def expire(self) -> None:
        self._deadline_expired = True
        self.abort()

    def check_deadline(self) -> None:
        if self._deadline_expired:
            raise NetworkTimeoutError("request total time limit exceeded") from None
        self._deadline.remaining_seconds()


class _HttpResponse:
    def __init__(
        self,
        response: http.client.HTTPResponse,
        connection: _PinnedConnection,
        deadline_timer: threading.Timer,
        deadline: RequestDeadline,
        max_response_bytes: int,
    ) -> None:
        self.status_code = response.status
        response_headers = response.getheaders()
        guarded_headers = {
            "content-length",
            "content-type",
            "content-encoding",
            "location",
            "link",
            "transfer-encoding",
        }
        seen: set[str] = set()
        for key, _value in response_headers:
            name = key.lower()
            if name in guarded_headers and name in seen:
                raise NetworkRequestError("ambiguous duplicate response headers")
            seen.add(name)
        self.headers = dict(response_headers)
        self._response = response
        self._connection = connection
        self._deadline_timer = deadline_timer
        self._deadline = deadline
        self._max_response_bytes = max_response_bytes

    def iter_bytes(self) -> Iterable[bytes]:
        consumed = 0
        while True:
            self._connection.check_deadline()
            try:
                chunk = self._response.read(min(65536, self._max_response_bytes + 1 - consumed))
            except TimeoutError:
                raise NetworkTimeoutError("HTTP response read timed out") from None
            except (OSError, http.client.HTTPException):
                self._connection.check_deadline()
                raise NetworkRequestError("HTTP response read failed") from None
            if not chunk:
                return
            consumed += len(chunk)
            yield chunk

    def close(self) -> None:
        self._deadline_timer.cancel()
        try:
            self._response.close()
        finally:
            self._connection.close()


class PinnedHttpTransport:
    """No retries or proxy discovery; outstanding DNS work is bounded even after a timeout."""

    def __init__(self, max_response_bytes: int, max_concurrent_requests: int) -> None:
        self._max_response_bytes = max_response_bytes
        self._dns_slots = threading.BoundedSemaphore(max_concurrent_requests)
        self._tls_context = ssl.create_default_context()

    def resolve_addresses(self, hostname: str, deadline: RequestDeadline) -> list[str]:
        deadline.remaining_seconds()
        try:
            numeric_address = ipaddress.ip_address(hostname)
        except ValueError:
            pass
        else:
            return [str(numeric_address)]
        if not self._dns_slots.acquire(timeout=deadline.remaining_seconds()):
            raise NetworkTimeoutError("DNS concurrency wait exceeded total time limit")
        resolved: queue.Queue[list[str] | OSError] = queue.Queue(maxsize=1)

        def resolve() -> None:
            try:
                records = socket.getaddrinfo(hostname, None, type=socket.SOCK_STREAM)
                resolved.put(list(dict.fromkeys(str(record[4][0]) for record in records)))
            except OSError as error:
                resolved.put(error)
            finally:
                self._dns_slots.release()

        threading.Thread(target=resolve, daemon=True).start()
        try:
            outcome = resolved.get(timeout=deadline.remaining_seconds())
        except queue.Empty:
            raise NetworkTimeoutError("DNS resolution exceeded total time limit") from None
        if isinstance(outcome, TimeoutError):
            raise NetworkTimeoutError("DNS resolution timed out") from None
        if isinstance(outcome, OSError):
            raise NetworkResolutionError("DNS resolution failed") from None
        return outcome

    def request(
        self,
        url: str,
        addresses: tuple[str, ...],
        deadline: RequestDeadline,
        headers: dict[str, str],
        *,
        method: Literal["GET", "POST"] = "GET",
        body: bytes | None = None,
    ) -> _HttpResponse:
        if method not in ("GET", "POST") or (method == "GET" and body is not None):
            raise ValueError("unsupported request method or body")
        if method == "POST" and (type(body) is not bytes or not 1 <= len(body) <= 1048576):
            raise ValueError("POST body must be bounded to 1 MiB")
        parts = urlsplit(url)
        hostname = parts.hostname or ""
        port = parts.port or (443 if parts.scheme == "https" else 80)
        connection = _PinnedConnection(
            hostname,
            port,
            addresses[0],
            deadline,
            self._tls_context if parts.scheme == "https" else None,
        )
        deadline_timer = threading.Timer(deadline.remaining_seconds(), connection.expire)
        deadline_timer.daemon = True
        deadline_timer.start()
        response: http.client.HTTPResponse | None = None
        handed_to_gateway = False
        try:
            request_headers = {
                "Host": hostname,
                "Accept-Encoding": "identity",
                "Connection": "close",
                "User-Agent": "AI-Intel-Source-Gateway/1.0",
                **headers,
            }
            target = parts.path or "/"
            if parts.query:
                target += "?" + parts.query
            connection.request(method, target, body=body, headers=request_headers)
            response = connection.getresponse()
            deadline.remaining_seconds()
            result = _HttpResponse(
                response, connection, deadline_timer, deadline, self._max_response_bytes
            )
            handed_to_gateway = True
            return result
        except NetworkPolicyViolation:
            raise
        except ssl.SSLCertVerificationError:
            connection.check_deadline()
            raise NetworkTlsError("HTTPS certificate verification failed") from None
        except TimeoutError:
            raise NetworkTimeoutError("HTTP request timed out") from None
        except (OSError, http.client.HTTPException):
            connection.check_deadline()
            raise NetworkRequestError("HTTP request failed") from None
        finally:
            if not handed_to_gateway:
                deadline_timer.cancel()
                if response is not None:
                    response.close()
                connection.abort()
