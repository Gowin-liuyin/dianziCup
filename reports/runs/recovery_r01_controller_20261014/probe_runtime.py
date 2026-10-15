"""实际本地HTTP/PG/Celery路径探针；不保存Cookie/密码/CSRF值。"""

import json
import os
import time
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import httpx

clock = ZoneInfo("Asia/Shanghai")
started_at = datetime.now(clock).isoformat(timespec="seconds")
checks: dict[str, object] = {}
with httpx.Client(base_url="http://127.0.0.1:28000", timeout=5, trust_env=False) as client:
    deadline = time.monotonic() + 30
    while True:
        readiness = client.get("/v1/health/ready")
        if readiness.status_code == 200 or time.monotonic() >= deadline:
            break
        time.sleep(1)
    checks["ready_status"] = readiness.status_code
    checks["readiness"] = readiness.json()
    checks["unauthenticated_status"] = client.get("/v1/auth/me").status_code
    login = client.post(
        "/v1/auth/login",
        headers={"Origin": "http://127.0.0.1:25173"},
        json={
            "username": os.environ["DIANZI_E2E_USERNAME"],
            "password": os.environ["DIANZI_E2E_PASSWORD"],
        },
    )
    checks["login_status"] = login.status_code
    assert login.status_code == 200, "actual isolated PG login failed"
    snapshot = client.get("/v1/auth/me")
    checks["snapshot_status"] = snapshot.status_code
    checks["snapshot_data_mode"] = snapshot.json()["data_mode"]
    checks["identity_csrf_bound"] = (
        snapshot.json()["csrf_token"] == login.json()["csrf_token"]
        and snapshot.json()["user_id"] == login.json()["user_id"]
        and snapshot.json()["tenant_id"] == "test-tenant-r01-root"
    )
    checks["missing_csrf_logout_status"] = client.post("/v1/auth/logout").status_code
    checks["session_preserved_on_rejection"] = client.get("/v1/auth/me").status_code == 200
    logout = client.post(
        "/v1/auth/logout",
        headers={"Origin": "http://127.0.0.1:25173", "X-CSRF-Token": snapshot.json()["csrf_token"]},
    )
    checks["logout_status"] = logout.status_code
    checks["revoked_status"] = client.get("/v1/auth/me").status_code
    checks["legacy_path_status"] = client.get("/auth/me").status_code
    checks["api_v1_alias_status"] = client.get("/api/v1/auth/me").status_code
    for path, status in [("/v1/auth/missing", 404), ("/v1/auth/login", 405)]:
        error = client.get(path)
        checks[f"problem_{status}"] = error.status_code == status and error.headers[
            "content-type"
        ].startswith("application/problem+json")
expected = {
    "ready_status": 200,
    "unauthenticated_status": 401,
    "login_status": 200,
    "snapshot_status": 200,
    "snapshot_data_mode": "live",
    "identity_csrf_bound": True,
    "missing_csrf_logout_status": 403,
    "session_preserved_on_rejection": True,
    "logout_status": 200,
    "revoked_status": 401,
    "legacy_path_status": 401,
    "api_v1_alias_status": 401,
    "problem_404": True,
    "problem_405": True,
}
failed = [name for name, value in expected.items() if checks.get(name) != value]
receipt = {
    "started_at": started_at,
    "ended_at": datetime.now(clock).isoformat(timespec="seconds"),
    "code_sha": "ca6aec29bda0c63d0451ddea41bc6f1f22a3f76e",
    "scope": "actual isolated PG/Redis/OpenSearch and local HTTP/Celery; not provider live",
    "checks": checks,
    "total": len(expected),
    "passed": len(expected) - len(failed),
    "failed": failed,
    "skipped": 0,
}
Path(__file__).with_name("runtime_probe.json").write_text(
    json.dumps(receipt, ensure_ascii=False, indent=2), encoding="utf-8"
)
print(json.dumps(receipt, ensure_ascii=False))
raise SystemExit(1 if failed else 0)
