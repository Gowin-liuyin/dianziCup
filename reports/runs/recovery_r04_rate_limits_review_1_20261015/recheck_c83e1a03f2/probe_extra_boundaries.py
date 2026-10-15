"""记录标准库头解析上限及RFC850整日期边界；不是live响应。"""

import json
import sys
from pathlib import Path
from datetime import UTC, datetime
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_reviewer_probes import install_wire, raw_response, classify, URL
from ai_intel.infrastructure.network import NetworkPolicy, create_network_gateway

results = []
for count in [65500, 65536]:
    monkeypatch = pytest.MonkeyPatch()
    try:
        sockets = install_wire(monkeypatch, raw_response(429, b"Retry-After: " + b"9" * count + b"\r\n"))
        try:
            response = create_network_gateway(NetworkPolicy(("api.github.com",))).fetch(URL)
            failure = classify(response.status_code, response.redacted_headers)
            results.append({"case": "raw-line-size", "value_length": count, "error_code": failure.error_code, "blocked": failure.blocked, "retry": failure.retry_after_seconds})
        except Exception as error:
            results.append({"case": "raw-line-size", "value_length": count, "exception_type": type(error).__name__, "safe_code": getattr(error, "code", None)})
        assert sockets[0].closed
    finally:
        monkeypatch.undo()
for header in ["Thursday, 15-Oct-76 12:35:05 GMT", "Thursday, 15-Oct-70 12:35:05 GMT"]:
    failure = classify(429, {"Retry-After": header}, datetime(2026, 10, 15, 12, 34, 56, tzinfo=UTC))
    results.append({"case": "rfc850-boundary", "synthetic_header": header, "blocked": failure.blocked, "retry": failure.retry_after_seconds})
print(json.dumps({"synthetic": True, "external_network_requests": 0, "observations": results}, ensure_ascii=False))
