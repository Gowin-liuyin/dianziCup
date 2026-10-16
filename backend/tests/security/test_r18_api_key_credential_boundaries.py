"""Pure authentication boundaries; HTTP/CSRF integration remains root-owned."""

import inspect

import pytest
from pydantic import SecretStr

from ai_intel.api.credentials import (
    ApiKeyCredential,
    CredentialParsingError,
    PgApiKeyService,
    SessionCredential,
    parse_request_credential,
)


@pytest.mark.parametrize("name", ["tenant_id", "user_id", "role", "scopes", "permissions"])
def test_identity_is_not_a_management_or_parser_argument(name: str) -> None:
    for method in (parse_request_credential, PgApiKeyService.revoke_key, PgApiKeyService.list_keys):
        assert name not in inspect.signature(method).parameters
    if name != "scopes":
        assert name not in inspect.signature(PgApiKeyService.issue_key).parameters


def test_errors_logs_and_representations_do_not_reflect_supplied_secrets(
    caplog: pytest.LogCaptureFixture,
) -> None:
    token = SecretStr("synthetic-sensitive-marker")
    with pytest.raises(CredentialParsingError) as error:
        parse_request_credential(
            ["Bearer " + token.get_secret_value()], session_cookie="synthetic-cookie-marker"
        )
    assert token.get_secret_value() not in str(error.value)
    assert token.get_secret_value() not in repr(ApiKeyCredential(token))
    assert "synthetic-cookie-marker" not in str(error.value)
    assert token.get_secret_value() not in caplog.text
    assert isinstance(parse_request_credential([], session_cookie="session"), SessionCredential)
