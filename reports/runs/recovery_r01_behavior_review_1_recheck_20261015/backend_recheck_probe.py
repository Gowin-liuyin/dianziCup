"""Independent fixed-root probes; synthetic accounts only and no database writes."""

from __future__ import annotations

import os
import sys
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event, Lock
from unittest.mock import patch

for variable in ("DATABASE_URL", "REDIS_URL", "OPENSEARCH_URL", "AUTH_SECRET_REF", "ALLOWED_ORIGINS"):
    os.environ.pop(variable, None)
os.environ["APP_ENV"] = "test"
os.environ["DATA_MODE"] = "fixture"
candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-recheck\dianzi")
sys.path.insert(0, str(candidate / "backend" / "src"))

from fastapi.testclient import TestClient

from ai_intel.api.app import create_application
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure.settings import ApplicationSettings

origin = "http://127.0.0.1:25173"
settings = ApplicationSettings(app_env="test", data_mode="fixture", allowed_origins=(origin,))


def fixture_service() -> AuthenticationSessionService:
    service = AuthenticationSessionService(InMemoryUserDirectory(), (origin,), False)
    service.create_precreated_user("independent-user-a", "Synthetic review input!", "review-tenant-a", Role.ANALYST)
    return service


def login(client: TestClient, username: str = "independent-user-a"):
    return client.post("/v1/auth/login", json={"username": username, "password": "Synthetic review input!"}, headers={"Origin": origin})


class FixedBehaviorProbe(unittest.TestCase):
    def test_concurrent_requests_are_denied_before_directory_io(self) -> None:
        service = fixture_service()
        directory = service._user_directory
        actual_lookup = directory.find_by_username
        entered = 0
        entered_lock = Lock()
        five_entered = Event()
        release_lookup = Event()

        def delayed_lookup(username: str):
            nonlocal entered
            with entered_lock:
                entered += 1
                if entered == 5:
                    five_entered.set()
            if not release_lookup.wait(timeout=5):
                raise AssertionError("review lookup was not released")
            return actual_lookup(username)

        with patch.object(directory, "find_by_username", delayed_lookup):
            with TestClient(create_application(service, settings=settings)) as client:
                with ThreadPoolExecutor(max_workers=8) as executor:
                    futures = [executor.submit(lambda: client.post("/v1/auth/login", json={"username": "independent-user-a", "password": "incorrect"}, headers={"Origin": origin}).status_code) for _ in range(8)]
                    try:
                        self.assertTrue(five_entered.wait(timeout=3))
                        self.assertEqual(entered, 5)
                    finally:
                        release_lookup.set()
                    codes = [future.result(timeout=5) for future in futures]
        self.assertEqual(sorted(codes), [401] * 5 + [429] * 3)
        self.assertEqual(entered, 5)
        print({"case": "same-client-eight-delayed-http-logins", "codes": codes, "directory_reads": entered})

    def test_non_ascii_csrf_is_403_and_does_not_revoke(self) -> None:
        service = fixture_service()
        with TestClient(create_application(service, settings=settings), raise_server_exceptions=False) as client:
            self.assertEqual(login(client).status_code, 200)
            response = client.post("/v1/auth/logout", headers=[(b"origin", origin.encode()), (b"x-csrf-token", b"\xff")])
            self.assertEqual(response.status_code, 403)
            self.assertEqual(response.headers["content-type"], "application/problem+json")
            self.assertEqual(response.json()["error"]["code"], "csrf_rejected")
            self.assertEqual(client.get("/v1/auth/me").status_code, 200)

    def test_404_and_405_have_problem_fields_and_allow(self) -> None:
        with TestClient(create_application(fixture_service(), settings=settings)) as client:
            for path, status, code in (("/v1/auth/missing", 404, "not_found"), ("/v1/auth/login", 405, "method_not_allowed")):
                with self.subTest(path=path):
                    response = client.get(path)
                    self.assertEqual(response.status_code, status)
                    self.assertEqual(response.headers["content-type"], "application/problem+json")
                    self.assertEqual(response.json()["error"]["code"], code)
                    self.assertTrue(response.json()["trace_id"])
                    self.assertTrue({"type", "title", "status", "detail", "instance"}.issubset(response.json()))
                    if status == 405:
                        self.assertEqual(response.headers["Allow"], "POST")

    def test_single_me_snapshot_cannot_revoke_replacement_user(self) -> None:
        service = fixture_service()
        account_b = service.create_precreated_user("independent-user-b", "Synthetic review input!", "review-tenant-b", Role.VIEWER)
        directory = service._user_directory
        with TestClient(create_application(service, settings=settings)) as client:
            first_login = login(client)
            with patch.object(directory, "find_by_id", wraps=directory.find_by_id) as reads:
                snapshot_a = client.get("/v1/auth/me").json()
                self.assertEqual(reads.call_count, 1)
            self.assertEqual(snapshot_a["user_id"], first_login.json()["user_id"])
            self.assertEqual(snapshot_a["csrf_token"], first_login.json()["csrf_token"])
            self.assertEqual(snapshot_a["role"], "analyst")
            self.assertEqual(snapshot_a["tenant_id"], "review-tenant-a")
            self.assertEqual(login(client, account_b.username).status_code, 200)
            response = client.post("/v1/auth/logout", headers={"Origin": origin, "X-CSRF-Token": snapshot_a["csrf_token"]})
            self.assertEqual(response.status_code, 403)
            current = client.get("/v1/auth/me").json()
            self.assertEqual(current["user_id"], account_b.user_id)
            self.assertEqual(current["tenant_id"], "review-tenant-b")
            self.assertEqual(current["role"], "viewer")
            print({"case": "cookie-replaced-after-atomic-me", "old_snapshot_logout": response.status_code, "replacement_user_remains_authenticated": True})


if __name__ == "__main__":
    unittest.main(verbosity=2)
