"""Review-only resource adaptation with the frozen backend failure-redaction hook."""

import importlib.util
import os
from pathlib import Path

import pytest
from pydantic import SecretStr
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

ROOT = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location("r11_review_fixed_backend_hook", ROOT / "backend/tests/conftest.py")
hook = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hook)
pytest_configure = hook.pytest_configure
pytest_runtest_makereport = hook.pytest_runtest_makereport
register_sensitive_failure_value = hook.register_sensitive_failure_value


@pytest.fixture(autouse=True)
def register_actual_review_secrets(register_sensitive_failure_value):
    for name in ("TEST_DATABASE_URL", "TEST_REDIS_URL", "TEST_SEARCH_TLS_PASSWORD"):
        value = os.environ.get(name, "")
        if value:
            register_sensitive_failure_value(SecretStr(value))
            if name.endswith("URL"):
                password = make_url(value).password
                if password:
                    register_sensitive_failure_value(SecretStr(password))


@pytest.fixture(scope="module")
def pg_engine():
    url = make_url(os.environ["TEST_DATABASE_URL"])
    assert url.database.startswith("test_dianzi_r11_assessment_review1_")
    assert url.host in {"127.0.0.1", "localhost"} and url.port == 25432
    assert os.environ["DIANZI_TEST_RUN_ID"] == "r11_assessment_review1_20261016"
    engine = create_engine(url, hide_parameters=True, pool_size=8)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT current_schema()")).startswith("r11_review1_")
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "0019_aggregate_observations"
    yield engine
    engine.dispose()
