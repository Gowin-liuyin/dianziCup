"""Probe the environment-loaded production module entry with isolated TLS inputs."""

import json
import os

from fastapi.testclient import TestClient

for variable_name, fixture_name in (
    ("OPENSEARCH_URL", "TEST_SEARCH_TLS_URL"),
    ("OPENSEARCH_USERNAME", "TEST_SEARCH_TLS_USERNAME"),
    ("OPENSEARCH_PASSWORD", "TEST_SEARCH_TLS_PASSWORD"),
    ("OPENSEARCH_CA_FILE", "TEST_SEARCH_TLS_CA_FILE"),
):
    os.environ[variable_name] = os.environ[fixture_name]
os.environ["APP_ENV"] = "test"
os.environ["DATA_MODE"] = "live"

from ai_intel.api.app import app

with TestClient(app) as client:
    response = client.get("/v1/health/ready")
payload = response.json()
if os.environ["TEST_SEARCH_TLS_PASSWORD"] in response.text:
    raise AssertionError("health response exposed a random test credential")
assert response.status_code == 503, "unconfigured core must remain not ready"
assert payload["dependencies"]["search"] == {"state": "ready"}, "secure search must be ready"
assert payload["dependencies"]["database"] == {"state": "not_configured"}
assert payload["dependencies"]["cache"] == {"state": "not_configured"}
print(json.dumps({"status_code": response.status_code, "payload": payload}))
