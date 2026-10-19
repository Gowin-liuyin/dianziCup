"""Adapt only the runtime ownership guard; source tests and expectations stay frozen."""

import os
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
RUN_ID = "r11_forward_review1_20261016"
DATABASE = "test_dianzi_" + RUN_ID
SCHEMA_PREFIX = "test_r11_forward_review1_"


def pytest_configure(config):
    from tests import r11_forward_fixtures

    import ai_intel
    from ai_intel.infrastructure.database import MIGRATIONS_DIR

    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, DATABASE)
    assert url.username and url.username.startswith("test_")
    assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID
    assert len(DATABASE) <= 63 and len(RUN_ID) <= 47
    assert Path(ai_intel.__file__).resolve().is_relative_to(ROOT / "backend/src")
    assert MIGRATIONS_DIR.resolve() == ROOT / "backend/migrations"
    r11_forward_fixtures.RUN_ID = RUN_ID
    r11_forward_fixtures.DATABASE = DATABASE
    r11_forward_fixtures.SCHEMA_PREFIX = SCHEMA_PREFIX


@pytest.fixture(autouse=True)
def independent_sensitive_connection(register_sensitive_failure_value):
    url = os.environ["TEST_DATABASE_URL"]
    password = make_url(url).password
    register_sensitive_failure_value(SecretStr(url))
    if password:
        register_sensitive_failure_value(SecretStr(password))
