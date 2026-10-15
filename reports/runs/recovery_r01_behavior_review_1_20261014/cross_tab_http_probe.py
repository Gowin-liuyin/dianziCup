"""Confirm the frontend race uses wire responses reachable through real auth routes."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

for variable in ("DATABASE_URL", "REDIS_URL", "OPENSEARCH_URL", "AUTH_SECRET_REF", "ALLOWED_ORIGINS"):
    os.environ.pop(variable, None)
os.environ["APP_ENV"] = "test"
os.environ["DATA_MODE"] = "fixture"
candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-candidate\dianzi")
sys.path.insert(0, str(candidate / "backend" / "src"))

from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.settings import ApplicationSettings

origin = "http://127.0.0.1:25173"
service = AuthenticationSessionService(InMemoryUserDirectory(), (origin,), False)
account_a = service.create_precreated_user("synthetic-user-a", "Synthetic review input!", "synthetic-tenant-a", Role.ANALYST)
account_b = service.create_precreated_user("synthetic-user-b", "Synthetic review input!", "synthetic-tenant-b", Role.VIEWER)
settings = ApplicationSettings(app_env="test", data_mode="fixture", allowed_origins=(origin,))
with TestClient(create_application(service, settings=settings)) as client:
    login_a = client.post("/v1/auth/login", json={"username": account_a.username, "password": "Synthetic review input!"}, headers={"Origin": origin})
    me_a = client.get("/v1/auth/me").json()
    login_b = client.post("/v1/auth/login", json={"username": account_b.username, "password": "Synthetic review input!"}, headers={"Origin": origin})
    csrf_b = client.get("/v1/auth/csrf").json()
    matches_b = csrf_b["csrf_token"] == login_b.json()["csrf_token"]
    response = client.post("/v1/auth/logout", headers={"Origin": origin, "X-CSRF-Token": csrf_b["csrf_token"]})
    invalidated_b = client.get("/v1/auth/me").status_code == 401
    result = {"mode": "explicit fixture real HTTP router; shared cookie replaced in same cookie jar", "me_sampled_user_a": me_a["user_id"] == account_a.user_id, "later_csrf_b": matches_b, "csrf_response_has_user_binding": "user_id" in csrf_b or "session_id" in csrf_b, "later_logout_status": response.status_code, "user_b_invalidated": invalidated_b, "credentials_logged": False}
    print(json.dumps(result))
    assert result["me_sampled_user_a"] and matches_b and invalidated_b
    assert response.status_code == 200
