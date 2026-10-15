"""Real default factory exposes only authenticated PG graph and private asset readers."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_r07_enrichment_api_pg import ORIGIN, application_client
from test_r07_enrichment_api_pg import execution_engine as execution_engine
from test_r07_job_execution_pg import setup

from ai_intel.api.app import create_application
from ai_intel.api.auth_routes import CSRF_HEADER_NAME
from ai_intel.infrastructure.settings import ApplicationSettings
from ai_intel.knowledge.models import users

pytestmark = pytest.mark.real_pg


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
def test_unconfigured_default_reader_requires_authentication(prefix):
    with TestClient(
        create_application(settings=ApplicationSettings(app_env="test", data_mode="fixture"))
    ) as client:
        for path in ("/assets", "/assets/" + str(uuid4()), "/events/" + str(uuid4()) + "/graph"):
            assert client.get(prefix + path).status_code == 401


@pytest.mark.parametrize("prefix", ["/v1", "/api/v1"])
def test_default_graph_reads_seeded_current_pg_evidence_and_rejects_body_identity(
    execution_engine, tmp_path, prefix
):
    _, scope, _, event_id, _, _ = setup(execution_engine, tmp_path)
    with application_client(execution_engine, tmp_path, scope) as client:
        response = client.get(prefix + f"/events/{event_id}/graph")
        assert response.status_code == 200
        result = response.json()
        assert result["rule_version"] == "r10-graph-1.2.0" and result["event_id"] == str(event_id)
        assert len(result["nodes"]) == 1 and result["nodes"][0]["kind"] == "event"
        assert result["edges"] == []
        assert client.get(prefix + f"/events/{event_id}/graph?tenant_id=forged").status_code == 422
        assert client.get(prefix + "/events/" + str(uuid4()) + "/graph").status_code == 404


def test_default_inventory_import_history_and_current_tenant_isolation(execution_engine, tmp_path):
    _, scope, _, _, _, _ = setup(execution_engine, tmp_path)
    with execution_engine.begin() as connection:
        connection.execute(
            update(users)
            .where(users.c.user_id == scope.user_id)
            .values(role="tenant_admin", tenant_id="synthetic-default-owner")
        )
    with application_client(execution_engine, tmp_path, scope) as client:
        headers = {
            "origin": ORIGIN,
            CSRF_HEADER_NAME: "synthetic-csrf",
            "Idempotency-Key": "default-inventory",
        }
        response = client.post(
            "/v1/asset-imports",
            params={
                "display_name": "Synthetic default asset",
                "source_version": "synthetic-1",
                "observed_at": datetime.now(UTC).isoformat(),
                "manifest_format": "json_manifest_v1",
            },
            content=b'{"format_version":1,"components":[{"ecosystem":"pypi","package_name":"langchain","version":"1.0"}]}',
            headers=headers,
        )
        assert response.status_code == 201
        identity = response.json()["asset_id"]
        snapshot_id = response.json()["snapshot"]["snapshot_id"]
        assert client.get("/api/v1/assets/" + identity).json()["current_snapshot_id"] == snapshot_id
        history = client.get("/v1/assets/" + identity + "/snapshots").json()
        assert len(history["items"]) == 1
        assert client.get(f"/v1/assets/{identity}/snapshots/{snapshot_id}").status_code == 200
        assert "raw_input" not in client.get("/v1/assets/" + identity).text
        with execution_engine.begin() as connection:
            connection.execute(
                update(users)
                .where(users.c.user_id == scope.user_id)
                .values(tenant_id="synthetic-default-other")
            )
        assert client.get("/v1/assets/" + identity).status_code == 404
        assert client.get("/v1/assets").json()["items"] == []
