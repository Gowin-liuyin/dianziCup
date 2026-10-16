"""Unchanged 33+15 behavior functions run on production 0022 using owned fixtures."""

import importlib
import os
import sys

import pytest
from pydantic import SecretStr
from sqlalchemy import MetaData, Table
from sqlalchemy.engine import make_url
from tests.integration import test_r11_pg_assessments as original
from tests.r11_forward_fixtures import forbid_metadata_creation, migrated_schema

sys.modules.setdefault("test_r11_pg_assessments", original)
raw_original = importlib.import_module("tests.integration.test_r11_assessment_raw_rechecks_pg")

pytestmark = pytest.mark.real_pg

for source in (original, raw_original):
    for original_name in dir(source):
        if original_name.startswith("test_"):
            globals()[original_name] = getattr(source, original_name)


@pytest.fixture(scope="module")
def pg_engine():
    with migrated_schema() as (engine, _url, _schema):
        yield engine


@pytest.fixture(autouse=True)
def production_boundaries(monkeypatch, register_sensitive_failure_value):
    register_sensitive_failure_value(SecretStr(make_url(os.environ["TEST_DATABASE_URL"]).password))
    monkeypatch.setattr(MetaData, "create_all", forbid_metadata_creation)
    monkeypatch.setattr(Table, "create", forbid_metadata_creation)
