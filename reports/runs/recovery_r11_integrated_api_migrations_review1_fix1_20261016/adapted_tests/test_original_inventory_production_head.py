"""Original SBOM and legacy inventory behavior assertions on real production 0022."""

import pytest
from tests.integration import test_t24_asset_inventory as legacy
from tests.integration import test_r11_sbom_inventory_postgres as sbom
from tests.integration import test_r11_sbom_inventory_uri_privacy as privacy
from tests.integration import test_r11_sbom_inventory_uri_privacy_followup as followup
from tests.r11_forward_fixtures import migrated_schema

pytestmark = pytest.mark.real_pg

for source in (legacy, sbom, privacy, followup):
    for name in dir(source):
        if name.startswith("test_"):
            assert name not in globals(), "original case names must not collide"
            globals()[name] = getattr(source, name)

sbom_api = sbom.sbom_api
inventory_api = legacy.inventory_api


@pytest.fixture(scope="module")
def sbom_engine():
    with migrated_schema() as (engine, _url, _schema):
        yield engine


@pytest.fixture(scope="module")
def inventory_engine():
    with migrated_schema() as (engine, _url, _schema):
        yield engine
