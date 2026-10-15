"""Independent R01 probes. Synthetic input only; no live database mutation."""

from __future__ import annotations

import json
import os
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Barrier
from unittest.mock import patch

for variable in ("DATABASE_URL", "REDIS_URL", "OPENSEARCH_URL", "AUTH_SECRET_REF", "ALLOWED_ORIGINS"):
    os.environ.pop(variable, None)
os.environ["APP_ENV"] = "test"
os.environ["DATA_MODE"] = "live"

candidate = Path(r"C:\Users\yinha\.codex\worktrees\recovery-r01-candidate\dianzi")
sys.path.insert(0, str(candidate / "backend" / "src"))
sys.path.insert(0, str(candidate))

from fastapi.testclient import TestClient
from pydantic import SecretStr
from sqlalchemy import create_engine

from ai_intel.api.app import app, create_application
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.domain.access import Role
from ai_intel.infrastructure import database
from ai_intel.infrastructure.settings import ApplicationSettings
from scripts import dev

origin = "http://127.0.0.1:25173"
settings = ApplicationSettings(app_env="test", data_mode="fixture", allowed_origins=(origin,))
results: list[dict[str, object]] = []


def observe(name: str, expected: object, actual: object, kind: str = "behavior") -> None:
    entry = {"probe": name, "kind": kind, "expected": expected, "actual": actual, "matched": expected == actual}
    results.append(entry)
    print(json.dumps(entry, ensure_ascii=False))


def configured_service() -> tuple[AuthenticationSessionService, list[datetime]]:
    clock = [datetime(2026, 10, 14, 16, 0, tzinfo=UTC)]
    service = AuthenticationSessionService(InMemoryUserDirectory(), (origin,), False, clock=lambda: clock[0])
    service.create_precreated_user("independent-reviewer", "Synthetic review input!", "review-tenant-a", Role.ANALYST)
    return service, clock


with TestClient(app, raise_server_exceptions=False) as client:
    for prefix in ("", "/v1"):
        observe(prefix + "/health/live default entry", 200, client.get(prefix + "/health/live").status_code)
        response = client.get(prefix + "/health/ready")
        observe(prefix + "/health/ready no resource", (503, "not_ready"), (response.status_code, response.json()["status"]))
        response = client.post(prefix + "/auth/login", json={"username": "synthetic", "password": "synthetic"}, headers={"Origin": origin})
        observe(prefix + "/auth/login unconfigured", (503, "authentication_unavailable"), (response.status_code, response.json()["error"]["code"]))
    response = client.get("/v1/auth/missing")
    observe("unknown API route RFC9457", "application/problem+json", response.headers.get("content-type"))
    response = client.get("/v1/auth/login")
    observe("wrong HTTP method RFC9457", "application/problem+json", response.headers.get("content-type"))

service, clock = configured_service()
with TestClient(create_application(service, settings=settings), raise_server_exceptions=False) as client:
    sentinel = "SYNTHETIC-NO-ECHO-INPUT"
    for name, value in (("number", 3), ("null", None), ("array", [sentinel]), ("object", {"nested": sentinel}), ("empty", ""), ("over_limit", sentinel * 50)):
        response = client.post("/v1/auth/login", json={"username": "independent-reviewer", "password": value}, headers={"Origin": origin})
        observe("strict password " + name, (422, False, "application/problem+json"), (response.status_code, sentinel in response.text, response.headers.get("content-type")))
    response = client.post("/v1/auth/login", json={"username": "independent-reviewer", "password": sentinel, "tenant_id": "other-tenant", "role": "system_admin", "permissions": ["*"]}, headers={"Origin": origin})
    observe("identity self report", (422, False, "identity_spoof_attempt"), (response.status_code, sentinel in response.text, service.audit_events()[-1]["event_type"]))
    for supplied_origin in (None, "http://malicious.invalid", "null"):
        headers = {} if supplied_origin is None else {"Origin": supplied_origin}
        response = client.post("/v1/auth/login", json={"username": "independent-reviewer", "password": "Synthetic review input!"}, headers=headers)
        observe("login Origin " + str(supplied_origin), 403, response.status_code)
    response = client.post("/v1/auth/login", json={"username": "independent-reviewer", "password": "Synthetic review input!"}, headers={"Origin": origin})
    csrf_value = response.json()["csrf_token"]
    observe("successful login cookie policy", (200, True, True), (response.status_code, "HttpOnly" in response.headers["set-cookie"], "SameSite=strict" in response.headers["set-cookie"]))
    response = client.get("/v1/auth/me")
    observe("server context", ("review-tenant-a", "analyst", False), (response.json()["tenant_id"], response.json()["role"], "manage:public_sources" in response.json()["permissions"]))
    for headers in ({"Origin": origin}, {"Origin": origin, "X-CSRF-Token": "wrong"}, {"X-CSRF-Token": csrf_value}, {"Origin": "http://malicious.invalid", "X-CSRF-Token": csrf_value}):
        observe("logout rejects missing/incorrect CSRF or Origin", 403, client.post("/v1/auth/logout", headers=headers).status_code)
    response = client.post("/v1/auth/logout", headers=[(b"origin", origin.encode()), (b"x-csrf-token", b"\xff")])
    observe("non-ASCII CSRF header is rejected", (403, "application/problem+json"), (response.status_code, response.headers.get("content-type")))
    observe("bad CSRF does not revoke", 200, client.get("/v1/auth/me").status_code)
    response = client.post("/v1/auth/logout", headers={"Origin": origin, "X-CSRF-Token": csrf_value})
    observe("logout clears cookie", (200, True), (response.status_code, "Max-Age=0" in response.headers["set-cookie"]))
    observe("logout immediate invalidation", 401, client.get("/v1/auth/me").status_code)
    client.post("/v1/auth/login", json={"username": "independent-reviewer", "password": "Synthetic review input!"}, headers={"Origin": origin})
    clock[0] += timedelta(minutes=31)
    observe("expired session", 401, client.get("/v1/auth/me").status_code)

unreachable = ApplicationSettings(app_env="test", data_mode="live", database_url=SecretStr("postgresql+psycopg://synthetic:synthetic@127.0.0.1:9/synthetic"), allowed_origins=(origin,), dependency_timeout_seconds=1)
with TestClient(create_application(settings=unreachable), raise_server_exceptions=False) as client:
    response = client.post("/v1/auth/login", json={"username": "synthetic", "password": "synthetic"}, headers={"Origin": origin})
    observe("actual closed loopback PG login", (503, False), (response.status_code, "synthetic" in response.text))
    response = client.get("/v1/health/ready")
    observe("actual closed loopback PG health", (503, "unavailable"), (response.status_code, response.json()["dependencies"]["database"]["state"]))

isolated = {"DIANZI_TEST_RUN_ID": "review_probe_20261014", "TEST_DATABASE_URL": "postgresql+psycopg://test_review:synthetic@127.0.0.1:29432/test_dianzi_review_probe_20261014"}
for name, url in (("development database", isolated["TEST_DATABASE_URL"].replace("test_dianzi_review_probe_20261014", "ai_intel")), ("remote host", isolated["TEST_DATABASE_URL"].replace("127.0.0.1", "192.0.2.1")), ("production user", isolated["TEST_DATABASE_URL"].replace("test_review:", "ai_intel:")), ("default port", isolated["TEST_DATABASE_URL"].replace(":29432", ":5432")), ("query pivot", isolated["TEST_DATABASE_URL"] + "?host=example.invalid")):
    try:
        dev.require_isolated_test_database({**isolated, "TEST_DATABASE_URL": url})
        rejected = False
    except dev.TestEnvironmentError:
        rejected = True
    observe("DSN guard " + name, True, rejected)
generic_url = isolated["TEST_DATABASE_URL"].replace("postgresql+psycopg", "postgresql")
approved = dev.require_isolated_test_database({**isolated, "TEST_DATABASE_URL": generic_url})
try:
    engine = create_engine(approved)
    engine.dispose()
    result = "engine builds"
except ModuleNotFoundError as failure:
    result = f"{type(failure).__name__}: {failure.name}"
observe("accepted plain PostgreSQL DSN downstream engine", "engine builds", result)

def forbid_command(*args: object, **kwargs: object) -> None:
    raise AssertionError("resource command must not be called")

with patch.dict(os.environ, isolated | {"DIANZI_COMPOSE_PROJECT": "dianzi-dev-review_probe_20261014"}, clear=False), patch.object(dev, "_run_command", forbid_command):
    try:
        dev.stop_development_services(True)
        refused = False
    except dev.TestEnvironmentError:
        refused = True
    observe("destructive project rejects development resources before IO", True, refused)

with tempfile.TemporaryDirectory(prefix="dianzi-r01-independent-report-") as temp_directory:
    report = Path(temp_directory) / "junit.xml"
    for name, body, exit_code, expected in (("zero", "<testsuites><testsuite tests='0'/></testsuites>", 0, 3), ("skip", "<testsuites><testsuite><testcase><skipped/></testcase></testsuite></testsuites>", 0, 4), ("error", "<testsuites><testsuite><testcase><error/></testcase></testsuite></testsuites>", 0, 1), ("nonzero pass body", "<testsuites><testsuite><testcase/></testsuite></testsuites>", 7, 7)):
        report.write_text(body, encoding="utf-8")
        observe("script report " + name, expected, dev._report_result("independent_probe", report, exit_code))
    report.write_text("not XML", encoding="utf-8")
    observe("script invalid report", 1, dev._report_result("independent_probe", report, 0))

percent_url = isolated["TEST_DATABASE_URL"].replace("synthetic@", "synthetic%40part%25value@")
captured: list[str] = []
with patch.object(database.command, "upgrade", lambda config, revision: captured.append(config.get_main_option("sqlalchemy.url"))):
    database.run_migrations(percent_url)
observe("percent URL survives migration caller", [percent_url], captured)
normalized_engine = database.build_engine(ApplicationSettings(database_url=SecretStr(percent_url)))
observe("percent URL decoded by production engine", "synthetic@part%value", normalized_engine.url.password)
normalized_engine.dispose()

service, _ = configured_service()
statuses = []
with TestClient(create_application(service, settings=settings), raise_server_exceptions=False) as client:
    for _ in range(6):
        statuses.append(client.post("/v1/auth/login", json={"username": "independent-reviewer", "password": "incorrect"}, headers={"Origin": origin}).status_code)
observe("sequential invalid login limit", [401, 401, 401, 401, 401, 429], statuses)

service, _ = configured_service()
directory = service._user_directory
original_lookup = directory.find_by_username
barrier = Barrier(8, timeout=10)

def delayed_lookup(username: str):
    barrier.wait()
    return original_lookup(username)

with patch.object(directory, "find_by_username", delayed_lookup):
    with TestClient(create_application(service, settings=settings), raise_server_exceptions=False) as client:
        with ThreadPoolExecutor(max_workers=8) as executor:
            responses = list(executor.map(lambda _: client.post("/v1/auth/login", json={"username": "independent-reviewer", "password": "incorrect"}, headers={"Origin": origin}).status_code, range(8)))
observe("eight concurrent invalid logins capped at five", True, responses.count(401) <= 5)
print(json.dumps({"probe": "concurrency_observed_codes", "statuses": responses}))

summary = {"probes": len(results), "matched": sum(bool(result["matched"]) for result in results), "mismatches": [result["probe"] for result in results if not result["matched"]], "mode": "explicit fixture HTTP + closed loopback dependency; no real PG writes"}
print(json.dumps(summary, ensure_ascii=False))
Path(__file__).with_name("backend_behavior_results.json").write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
sys.exit(1 if summary["mismatches"] else 0)
