"""Explicit SQL/auth fixtures verify server-only public display and unchanged error contracts."""

from unittest.mock import MagicMock, Mock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from tests.unit.test_r06_revision_mode_reads import original

from ai_intel.api import document_routes, knowledge_routes
from ai_intel.api.auth_routes import SESSION_COOKIE_NAME
from ai_intel.api.authentication import AuthenticationSessionService
from ai_intel.domain.access import AccessScope, Role


@pytest.mark.parametrize("metadata", ({"data_mode": "fixture"}, {}, {"data_mode": "live"}))
def test_public_document_router_keeps_stored_fixture_or_returns_unavailable(monkeypatch, metadata):
    row = {**original.revision_row("fixture"), "source_metadata": metadata}
    scope = AccessScope.for_authenticated_user("explicit-mode-contract", None, Role.VIEWER)
    auth = Mock(spec=AuthenticationSessionService)
    auth.build_access_scope.return_value = scope
    session = MagicMock()
    session.execute.return_value = original.sql_result([row])
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr(document_routes, "Session", factory)
    monkeypatch.setattr(document_routes, "lock_authenticated_scope", lambda *_: scope)
    app = FastAPI()
    app.include_router(
        document_routes.build_document_router(lambda: auth, Mock(spec=Engine), "live"), prefix="/v1"
    )
    with TestClient(app) as client:
        assert client.get("/v1/documents").status_code == 401
        client.cookies.set(SESSION_COOKIE_NAME, "explicit-synthetic-contract-cookie")
        result = client.get("/v1/documents?require_expected_mode=true")
        if metadata == {"data_mode": "fixture"}:
            assert result.status_code == 200
            assert result.json()["schema_version"] == 2
            assert result.json()["data_mode"] == "fixture"
        else:
            assert result.status_code == 503
            assert result.json()["error"]["code"] == "document_unavailable"
            assert "source_metadata" not in result.text


def test_public_knowledge_router_is_the_only_explicit_display_configuration(monkeypatch):
    auth = Mock(spec=AuthenticationSessionService)
    auth.build_access_scope.return_value = original.SCOPE
    session = MagicMock()
    factory = MagicMock()
    factory.return_value.__enter__.return_value = session
    monkeypatch.setattr(knowledge_routes, "Session", factory)
    configured = []
    reader = Mock()
    reader.list_events.return_value = {
        "schema_version": 2,
        "items": [],
        "next_cursor": None,
        "data_mode": "live",
    }

    def construct(*arguments, **options):
        configured.append(options)
        return reader

    monkeypatch.setattr(knowledge_routes, "KnowledgeReadService", construct)
    app = FastAPI()
    app.include_router(
        knowledge_routes.build_knowledge_router(lambda: auth, Mock(spec=Engine), "live"),
        prefix="/v1",
    )
    with TestClient(app) as client:
        client.cookies.set(SESSION_COOKIE_NAME, "explicit-synthetic-contract-cookie")
        assert client.get("/v1/events?require_expected_mode=false").status_code == 200
    assert configured == [{"require_expected_mode": False}]
