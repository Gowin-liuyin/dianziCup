"""Actual alias HTTP routes share the same canonical enrichment scheduling identity."""

import pytest
from test_r07_enrichment_api_pg import (
    ORIGIN,
    application_client,
)
from test_r07_enrichment_api_pg import (
    execution_engine as execution_engine,
)
from test_r07_job_execution_pg import setup

from ai_intel.api.auth_routes import CSRF_HEADER_NAME

pytestmark = pytest.mark.real_pg


def test_v1_and_api_v1_post_aliases_reuse_one_operation(execution_engine, tmp_path):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    headers = {
        "origin": ORIGIN,
        CSRF_HEADER_NAME: "synthetic-csrf",
        "Idempotency-Key": "same-alias-route-key",
    }
    payload = {"expected_event_version": 1, "dimensions": ["cvss"]}
    with application_client(execution_engine, tmp_path, scope) as client:
        first = client.post(f"/v1/events/{event_id}/enrichment-jobs", json=payload, headers=headers)
        second = client.post(
            f"/api/v1/events/{event_id}/enrichment-jobs", json=payload, headers=headers
        )
    assert first.status_code == second.status_code == 202
    assert first.json()["reused"] is False and second.json()["reused"] is True
    assert first.json()["parent_job_id"] == second.json()["parent_job_id"]
