"""Review-only ownership adaptation; original tests and expected values stay frozen."""

import os
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool

RUN = Path(__file__).resolve().parent
ROOT = RUN.parents[2]
RUN_ID = "r11_sbom_locator_fix1_20261016"
DATABASE = "test_dianzi_" + RUN_ID


def pytest_configure(config):
    from tests import r11_forward_fixtures

    import ai_intel
    from ai_intel.infrastructure.database import MIGRATIONS_DIR

    assert Path(ai_intel.__file__).resolve().is_relative_to(ROOT / "backend/src")
    assert MIGRATIONS_DIR.resolve() == (ROOT / "backend/migrations").resolve()
    url = make_url(os.environ["TEST_DATABASE_URL"])
    database = DATABASE + "_mig" if os.environ["DIANZI_TEST_DB_KIND"] == "migrations" else DATABASE
    assert (url.host, url.port, url.database) == ("127.0.0.1", 25432, database)
    assert os.environ["DIANZI_TEST_RUN_ID"] == RUN_ID
    r11_forward_fixtures.RUN_ID = RUN_ID
    r11_forward_fixtures.DATABASE = database
    r11_forward_fixtures.SCHEMA_PREFIX = "test_r11_locator_fix1_"

    def owned_fixture_engine(url, **arguments):
        assert make_url(url).database == database
        arguments.pop("pool_size", None)
        arguments.pop("max_overflow", None)
        return create_engine(url, poolclass=NullPool, **arguments)

    r11_forward_fixtures.create_engine = owned_fixture_engine


@pytest.fixture(autouse=True)
def register_actual_review_secrets(register_sensitive_failure_value):
    value = os.environ["TEST_DATABASE_URL"]
    register_sensitive_failure_value(SecretStr(value))
    register_sensitive_failure_value(SecretStr(make_url(value).password))
