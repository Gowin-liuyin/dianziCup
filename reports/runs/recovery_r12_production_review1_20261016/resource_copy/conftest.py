"""Explicitly reuse the project hooks, including registered secret-value redaction."""

import os
from urllib.parse import unquote, urlsplit

import pytest
from pydantic import SecretStr
from tests.conftest import *


@pytest.fixture(autouse=True)
def register_review_credentials(register_sensitive_failure_value):
    value = os.environ.get('TEST_DATABASE_URL', '')
    register_sensitive_failure_value(SecretStr(value))
    register_sensitive_failure_value(SecretStr(unquote(urlsplit(value).password or '')))
