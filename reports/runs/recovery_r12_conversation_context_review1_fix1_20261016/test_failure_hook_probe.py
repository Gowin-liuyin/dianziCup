"""Expected intentional failure checks actual DSN/password report redaction."""
import os
from pydantic import SecretStr
from sqlalchemy.engine import make_url


def test_registered_actual_test_values_are_redacted(register_sensitive_failure_value):
    connection_value=os.environ['TEST_DATABASE_URL']
    password_value=make_url(connection_value).password
    register_sensitive_failure_value(SecretStr(connection_value))
    register_sensitive_failure_value(SecretStr(password_value))
    assert False, 'EXPECTED REDACTION PROBE '+connection_value+' '+password_value
