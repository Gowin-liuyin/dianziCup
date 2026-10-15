"""校验失败审计的PG故障不能变500或回退内存。"""

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from ai_intel.api.app import create_application
from ai_intel.api.authentication import AuthenticationSessionService, InMemoryUserDirectory
from ai_intel.infrastructure.settings import ApplicationSettings


class UnavailableAuditService(AuthenticationSessionService):
    def record_identity_spoof_attempt(self, submitted_fields: dict[str, str]) -> None:
        raise SQLAlchemyError("synthetic database diagnostic must not reach response")


def test_identity_spoof_audit_unavailable_is_safe_retryable_503() -> None:
    service = UnavailableAuditService(InMemoryUserDirectory(), ("http://localhost:5173",), False)
    with TestClient(
        create_application(service, settings=ApplicationSettings(app_env="test"))
    ) as client:
        response = client.post("/v1/auth/login", json={"tenant_id": "synthetic-untrusted-tenant"})
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "authentication_unavailable"
    assert "diagnostic" not in response.text and "synthetic-untrusted-tenant" not in response.text
